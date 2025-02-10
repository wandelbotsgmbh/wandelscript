import contextlib
import io
import sys
import threading
import time
import traceback as tb
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import field
from datetime import datetime
from enum import Enum

import anyio
import anyio.abc
import pydantic
from exceptiongroup import ExceptionGroup
from loguru import logger
from nova.api import models
from nova.core.robot_cell import ConfigurablePeriphery, RobotCell

from wandelscript import serializer
from wandelscript.exception import NotPlannableError
from wandelscript.metamodel import Skill
from wandelscript.models import Path
from wandelscript.runtime import ExecutionContext, PlannableActionQueue, current_execution_context_var
from wandelscript.utils.runtime import Tee, stoppable_run


class ProgramRunState(Enum):
    NOT_STARTED = "not started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ExecutionResult(pydantic.BaseModel):
    """The ExecutionResult object contains the execution results of a robot.

    Arguments:
        motion_group_id: The unique identifier of the motion group
        motion_duration: The total execution duration of the motion group
        paths: The paths of the motion group as list of Path objects

    """

    motion_group_id: str
    motion_duration: float
    paths: list[Path]


class ProgramRun(pydantic.BaseModel):
    """The ProgramRun object holds the state of a program run.

    Args:
        id: The unique identifier of the program run
        state: The state of the program run
        logs: The logs of the program run
        stdout: The stdout of the program run
        store: The store of the program run
        error: The error message of the program run, if any
        traceback: The traceback of the program run, if any
        start_time: The start time of the program run
        end_time: The end time of the program run
        execution_results: The robot execution results of the program run

    """

    id: str
    state: ProgramRunState
    logs: str = ""
    stdout: str = ""
    store: dict[str, serializer.ElementType] = field(default_factory=dict)
    error: str | None = None
    traceback: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    execution_results: list[ExecutionResult] = field(default_factory=list)


class ProgramRunner:
    """The skill runner provides functionalities to manage a program execution"""

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        code: str,
        robot_cell: RobotCell,
        default_robot: str | None = None,
        default_tcp: str | None = None,
        initial_store: dict[str, serializer.ElementType] | None = None,
        use_plannable_context: bool = False,
    ):
        self._code: str = code
        self._default_robot: str | None = default_robot
        self._default_tcp: str | None = default_tcp
        # serialize the configuration of the robot cell
        self._robot_cell_config: list[ConfigurablePeriphery.Configuration] = robot_cell.to_configurations()
        # serialize the initial store dict
        self._initial_store: dict[str, serializer.ElementType] = initial_store or {}
        self.execution_context: ExecutionContext | None = None
        self._skill_run: ProgramRun = ProgramRun(id=str(uuid.uuid4()), state=ProgramRunState.NOT_STARTED)
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._exc: Exception | None = None
        self._use_plannable_context = use_plannable_context

    @property
    def skill_run(self) -> ProgramRun:
        return self._skill_run

    @property
    def id(self) -> str:
        return self.skill_run.id

    @property
    def state(self) -> ProgramRunState:
        return self.skill_run.state

    @property
    def stopped(self):
        return self._stop_event.is_set()

    @property
    def start_time(self) -> datetime | None:
        """Datetime at which the runner started

        Returns:
            Optional[datetime]: datetime object

        """
        if self.skill_run.start_time is None:
            return None
        return datetime.fromtimestamp(self.skill_run.start_time)

    @property
    def execution_time(self) -> float | None:
        """Time the execution was running

        Returns:
            Optional[float]: execution time in seconds

        """
        return self.skill_run.end_time

    async def _run_skill(self, execution_context: ExecutionContext):
        # Try parsing the skill and handle parsing error
        logger.info(f"Parse skill {self.id}...")
        logger.debug(self._code)
        # TODO(async) if this is a bottleneck make it awaitable (to_thread)
        skill = Skill.from_code(self._code)
        # Execute Wandelscript
        logger.info(f"Run skill {self.id}...")
        self._skill_run.state = ProgramRunState.RUNNING
        self._skill_run.start_time = time.time()
        await skill(execution_context)

    def _handle_general_exception(self, exc: Exception):
        # Handle any exceptions raised during task execution
        message = f"{type(exc)}: {str(exc)}"
        traceback = tb.format_exc()
        logger.error(f"Skill {self.id} failed")
        # TODO: whats the equivalent here for the generated API?
        # from pyriphery.pyrae.clients.motion import MotionException
        # if isinstance(exc, MotionException):
        #    logger.error("MotionException was raised. Suppressing output since it is too long.")
        # else:
        #    logger.error(traceback)
        #    logger.error(message)
        self._skill_run.error = message
        self._skill_run.traceback = traceback
        self._skill_run.state = ProgramRunState.FAILED
        self._exc = exc

    async def estop_handler(
        self,
        monitoring_scope: anyio.CancelScope,
        *,
        task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED,
    ):
        assert self.execution_context is not None

        def state_is_estop(state_: models.RobotControllerState):
            # See: models.RobotControllerState.safety_state
            acceptable_safety_states = ["SAFETY_NORMAL", "SAFETY_REDUCED"]
            return (
                isinstance(state_, models.RobotControllerState) and state_.safety_state not in acceptable_safety_states
            )

        with monitoring_scope:
            cell_state_stream = self.execution_context.robot_cell.state_stream(1000)
            task_status.started()

            async for state in cell_state_stream:
                if state_is_estop(state):
                    logger.info(f"ESTOP detected: {state}")
                    self.stop()  # TODO is this clean

    async def _run(  # pylint: disable=too-many-branches
        self,
        robot_cell_config: list[ConfigurablePeriphery.Configuration],
        stop_event: anyio.Event,
        on_state_change: Callable[[], Awaitable[None]],
    ):
        """This function is executed in another thread when the start method is called
        The parameters that are needed for the skill execution are loaded into
        the new thread and provided to the skill execution

        Args:
            robot_cell_config: the serialized RobotCell configuration as dict
            stop_event: event that is set when the skill execution should be stopped
            on_state_change: callback function that is called when the state of the skill runner changes

        Raises:
            CancelledError: when the skill execution is cancelled  # noqa: DAR402

        # noqa: DAR401
        """

        # Create a new logger sink to capture the output of the skill execution
        # TODO potential memory leak if the the skill is running for a long time
        log_capture = io.StringIO()
        sink_id = logger.add(log_capture)

        # Create a new robot cell from the provided robot cell configuration
        logger.info(robot_cell_config)
        robot_cell = RobotCell.from_configurations(robot_cell_config)
        logger.info("Created RobotCell from configuration")

        try:
            async with robot_cell:
                await on_state_change()

                self.execution_context = execution_context = ExecutionContext(
                    robot_cell,
                    stop_event,
                    default_robot=self._default_robot,
                    default_tcp=self._default_tcp,
                    initial_vars=self._initial_store,
                )

                if self._use_plannable_context:
                    execution_context.action_queue = PlannableActionQueue(execution_context)

                current_execution_context_var.set(execution_context)

                monitoring_scope = anyio.CancelScope()
                async with anyio.create_task_group() as tg:
                    await tg.start(self.estop_handler, monitoring_scope)

                    try:
                        await self._run_skill(execution_context)
                    except anyio.get_cancelled_exc_class() as exc:  # noqa: F841
                        # Program was stopped
                        logger.info(f"Program {self.id} cancelled")
                        try:
                            with anyio.CancelScope(shield=True):
                                await robot_cell.stop()
                        # TODO: We don't use GRPC anymore, do we need additional handling here?
                        # except ExceptionGroup as eg:
                        #    e = eg.exceptions[0]
                        #    if (
                        #        len(eg.exceptions) == 1
                        #        and isinstance(e, GRPCError)
                        #        and "is not moving currently" in str(e)
                        #    ):
                        #        logger.debug(f"Suppressed exception {e!r}; not reraising it")
                        #    else:
                        #        raise
                        except Exception as e:
                            logger.error(f"Error while stopping robot cell: {e!r}")
                            raise

                        self._skill_run.state = ProgramRunState.STOPPED
                        raise

                    except NotPlannableError as exc:
                        # Program was not plannable (aka. /plan/ endpoint)
                        self._handle_general_exception(exc)
                    except Exception as exc:  # pylint: disable=broad-except
                        self._handle_general_exception(exc)
                    else:
                        if self.stopped:
                            # Program was stopped
                            logger.info(f"Program {self.id} stopped successfully")
                            self._skill_run.state = ProgramRunState.STOPPED
                        elif self._skill_run.state is ProgramRunState.RUNNING:
                            # Program was completed
                            self._skill_run.state = ProgramRunState.COMPLETED
                            logger.info(f"Program {self.id} completed successfully")
                    finally:
                        # write path to output
                        robot_cell = execution_context.robot_cell
                        self._skill_run.execution_results = [
                            ExecutionResult(
                                motion_group_id=result.motion_group_id,
                                motion_duration=result.motion_duration,
                                paths=[
                                    Path.from_motion_states(recorded_trajectory)
                                    for recorded_trajectory in result.recorded_trajectories
                                ],
                            )
                            for result in robot_cell.get_execution_results()
                        ]

                        # write store to output
                        self._skill_run.store = execution_context.store.data_dict
                        logger.info(f"Program {self.id} finished. Run teardown routine...")
                        self._skill_run.end_time = time.time()

                        logger.remove(sink_id)
                        self._skill_run.logs = log_capture.getvalue()
                        monitoring_scope.cancel()
                        await on_state_change()
        except anyio.get_cancelled_exc_class():
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # Handle any exceptions raised during entering the robot cell context
            self._handle_general_exception(exc)

    def start(self, sync=False, on_state_change: Callable[[ProgramRun], Awaitable[None]] | None = None):
        """Create another thread and starts the skill execution. If the skill was executed already, is currently
        running, failed or was stopped a new skill runner needs to be created.

        Args:
            sync: if True the execution is synchronous and the method blocks until the execution is finished
            on_state_change: callback function that is called when the state of the skill runner changes

        Raises:
            RuntimeError: when the runner is not in IDLE state
        """
        # Check if another skill execution is already in progress
        if self.state is not ProgramRunState.NOT_STARTED:
            raise RuntimeError("The runner is not in the NOT_STARTED state. Create a new runner to execute again.")

        async def _on_state_change():
            if on_state_change is not None:
                await on_state_change(self._skill_run)

        def stopper(sync_stop_event, async_stop_event):
            while not sync_stop_event.wait(0.2):
                anyio.from_thread.check_cancelled()
            anyio.from_thread.run_sync(async_stop_event.set)

        async def runner():
            self._stop_event = threading.Event()
            async_stop_event = anyio.Event()

            # TODO potential memory leak if the the skill is running for a long time
            with contextlib.redirect_stdout(Tee(sys.stdout)) as stdout:
                try:
                    await stoppable_run(
                        self._run(self._robot_cell_config, async_stop_event, _on_state_change),
                        anyio.to_thread.run_sync(stopper, self._stop_event, async_stop_event, abandon_on_cancel=True),
                    )
                except ExceptionGroup as eg:
                    raise eg.exceptions[0]
                self._skill_run.stdout = stdout.getvalue()

        # Create new thread and runs _run
        # start a new thread
        self._thread = threading.Thread(target=anyio.run, name="ProgramRunner", args=[runner])
        self._thread.start()

        if sync:
            self.join()

    def join(self):
        """Wait for the skill execution to finish

        Raises:
            _exc: Exception: when the runner is not in IDLE state
        """
        self._thread.join()
        if self._exc:
            raise self._exc

    def stop(self, sync=False):
        """Stop the skill execution

        Args:
            sync: if True the call is blocking until the skill execution is stopped

        Raises:
            RuntimeError: when the runner is not in IDLE state

        """
        if not self.is_running():
            raise RuntimeError("Skill is not running")
        self._stop_event.set()
        if sync:
            self.join()

    def is_running(self) -> bool:
        """Check if a skill is currently running

        Returns:
            bool: True if a skill is running

        """
        return self._thread is not None and self.state is ProgramRunState.RUNNING


def run(
    code: str,
    robot_cell: RobotCell,
    default_robot: str | None = None,
    default_tcp: str | None = None,
    initial_state: dict[str, serializer.ElementType] | None = None,
    use_plannable_context: bool = False,
) -> ProgramRunner:
    """Helper function to create a ProgramRunner and start it synchronously

    Args:
        code (str): Wandelscript code
        robot_cell (RobotCell): The RobotCell where the code is executed
        default_robot (str): The default robot that is used when no robot is active
        default_tcp (str): The default TCP that is used when no TCP is explicitly selected for a motion
        initial_state (dict[str, Any], optional): Store will be initialized with this dict. Defaults to ().
        use_plannable_context (bool): If True, the skill runner will use a plannable context. Defaults to False.

    Returns:
        ProgramRunner: The skill runner object

    """
    runner = ProgramRunner(
        code,
        robot_cell,
        default_robot=default_robot,
        default_tcp=default_tcp,
        initial_store=initial_state,
        use_plannable_context=use_plannable_context,
    )
    runner.start(sync=True)
    return runner
