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
from pathlib import Path

import anyio
import anyio.abc
import pydantic
from exceptiongroup import ExceptionGroup
from loguru import logger
from nova.api import models
from nova.core.exceptions import PlanTrajectoryFailed
from nova.core.robot_cell import ConfigurablePeriphery, RobotCell
from nova.types import MotionState, RobotState

from wandelscript import serializer
from wandelscript.exception import NotPlannableError
from wandelscript.ffi import ForeignFunction
from wandelscript.metamodel import Program
from wandelscript.runtime import ExecutionContext, PlannableActionQueue, current_execution_context_var
from wandelscript.simulation import SimulatedRobotCell
from wandelscript.utils.runtime import Tee, stoppable_run


class ProgramRunState(Enum):
    NOT_STARTED = "not started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class PosePath(pydantic.BaseModel):
    poses: list[RobotState] = []

    @classmethod
    def from_motion_states(cls, motion_states: list[MotionState]):
        return cls(
            poses=[
                RobotState(
                    pose=motion_state.state.pose,
                    joints=motion_state.state.joints if motion_state.state.joints is not None else None,
                )
                for motion_state in motion_states
            ]
        )


class ExecutionResult(pydantic.BaseModel):
    """The ExecutionResult object contains the execution results of a robot.

    Arguments:
        motion_group_id: The unique id of the motion group
        motion_duration: The total execution duration of the motion group
        paths: The paths of the motion group as list of Path objects

    """

    motion_group_id: str
    motion_duration: float
    paths: list[PosePath]


class ProgramRun(pydantic.BaseModel):
    """Holds the state of a program run.

    Args:
        id: The unique id of the program run
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
    """Provides functionalities to manage a single program execution"""

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        code: str,
        robot_cell: RobotCell,
        default_robot: str | None = None,
        default_tcp: str | None = None,
        initial_store: dict[str, serializer.ElementType] | None = None,
        foreign_functions: dict[str, ForeignFunction] | None = None,
        use_plannable_context: bool = False,
    ):
        self._code: str = code
        self._default_robot: str | None = default_robot
        self._default_tcp: str | None = default_tcp
        # serialize the configuration of the robot cell
        self._robot_cell_config: list[ConfigurablePeriphery.Configuration] = robot_cell.to_configurations()
        # serialize the initial store dict
        self._initial_store: dict[str, serializer.ElementType] = initial_store or {}
        self._foreign_functions: dict[str, ForeignFunction] = foreign_functions or {}
        self.execution_context: ExecutionContext | None = None
        self._program_run: ProgramRun = ProgramRun(id=str(uuid.uuid4()), state=ProgramRunState.NOT_STARTED)
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._exc: Exception | None = None
        self._use_plannable_context = use_plannable_context

    @property
    def program_run(self) -> ProgramRun:
        return self._program_run

    @property
    def id(self) -> str:
        return self.program_run.id

    @property
    def state(self) -> ProgramRunState:
        return self.program_run.state

    @property
    def stopped(self):
        return self._stop_event.is_set()

    @property
    def start_time(self) -> datetime | None:
        """Datetime at which the runner started

        Returns:
            Optional[datetime]: datetime object

        """
        if self.program_run.start_time is None:
            return None
        return datetime.fromtimestamp(self.program_run.start_time)

    @property
    def execution_time(self) -> float | None:
        """Time the execution was running

        Returns:
            Optional[float]: execution time in seconds

        """
        return self.program_run.end_time

    async def _run_program(self, execution_context: ExecutionContext):
        # Try parsing the program and handle parsing error
        logger.info(f"Parse program {self.id}...")
        logger.debug(self._code)
        # TODO(async) if this is a bottleneck make it awaitable (to_thread)
        program = Program.from_code(self._code)
        # Execute Wandelscript
        logger.info(f"Run program {self.id}...")
        self._program_run.state = ProgramRunState.RUNNING
        self._program_run.start_time = time.time()
        await program(execution_context)

    def _handle_general_exception(self, exc: Exception) -> None:
        # Handle any exceptions raised during task execution
        traceback = tb.format_exc()
        logger.error(f"Program {self.id} failed")

        if isinstance(exc, PlanTrajectoryFailed):
            message = f"{type(exc)}: {exc.to_pretty_string()}"
        else:
            message = f"{type(exc)}: {str(exc)}"
            logger.error(traceback)
            self._exc = exc
        logger.error(message)
        self._program_run.error = message
        self._program_run.traceback = traceback
        self._program_run.state = ProgramRunState.FAILED

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
        The parameters that are needed for the program execution are loaded into
        the new thread and provided to the program execution

        Args:
            robot_cell_config: the serialized RobotCell configuration as dict
            stop_event: event that is set when the program execution should be stopped
            on_state_change: callback function that is called when the state of the program runner changes

        Raises:
            CancelledError: when the program execution is cancelled  # noqa: DAR402

        # noqa: DAR401
        """

        # Create a new logger sink to capture the output of the program execution
        # TODO potential memory leak if the the program is running for a long time
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
                    initial_vars=self._initial_store,  # type: ignore
                    foreign_functions=self._foreign_functions,
                )

                if self._use_plannable_context:
                    execution_context.action_queue = PlannableActionQueue(execution_context)

                current_execution_context_var.set(execution_context)

                monitoring_scope = anyio.CancelScope()
                async with anyio.create_task_group() as tg:
                    await tg.start(self.estop_handler, monitoring_scope)

                    try:
                        await self._run_program(execution_context)
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

                        self._program_run.state = ProgramRunState.STOPPED
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
                            self._program_run.state = ProgramRunState.STOPPED
                        elif self._program_run.state is ProgramRunState.RUNNING:
                            # Program was completed
                            self._program_run.state = ProgramRunState.COMPLETED
                            logger.info(f"Program {self.id} completed successfully")
                    finally:
                        # write path to output
                        self._program_run.execution_results = [
                            ExecutionResult(
                                motion_group_id=motion_group_id,
                                motion_duration=0,
                                paths=[
                                    PosePath.from_motion_states(motion_states) for motion_states in motion_state_list
                                ],
                            )
                            for motion_group_id, motion_state_list in execution_context.motion_group_recordings.items()
                        ]

                        # write store to output
                        self._program_run.store = execution_context.store.data_dict
                        logger.info(f"Program {self.id} finished. Run teardown routine...")
                        self._program_run.end_time = time.time()

                        logger.remove(sink_id)
                        self._program_run.logs = log_capture.getvalue()
                        monitoring_scope.cancel()
                        await on_state_change()
        except anyio.get_cancelled_exc_class():
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # Handle any exceptions raised during entering the robot cell context
            self._handle_general_exception(exc)

    def start(self, sync=False, on_state_change: Callable[[ProgramRun], Awaitable[None]] | None = None):
        """Create another thread and starts the program execution. If the program was executed already, is currently
        running, failed or was stopped a new program runner needs to be created.

        Args:
            sync: if True the execution is synchronous and the method blocks until the execution is finished
            on_state_change: callback function that is called when the state of the program runner changes

        Raises:
            RuntimeError: when the runner is not in IDLE state
        """
        # Check if another program execution is already in progress
        if self.state is not ProgramRunState.NOT_STARTED:
            raise RuntimeError("The runner is not in the NOT_STARTED state. Create a new runner to execute again.")

        async def _on_state_change():
            if on_state_change is not None:
                await on_state_change(self._program_run)

        def stopper(sync_stop_event, async_stop_event):
            while not sync_stop_event.wait(0.2):
                anyio.from_thread.check_cancelled()
            anyio.from_thread.run_sync(async_stop_event.set)

        async def runner():
            self._stop_event = threading.Event()
            async_stop_event = anyio.Event()

            # TODO potential memory leak if the the program is running for a long time
            with contextlib.redirect_stdout(Tee(sys.stdout)) as stdout:
                try:
                    await stoppable_run(
                        self._run(self._robot_cell_config, async_stop_event, _on_state_change),
                        anyio.to_thread.run_sync(stopper, self._stop_event, async_stop_event, abandon_on_cancel=True),
                    )
                except ExceptionGroup as eg:
                    raise eg.exceptions[0]
                self._program_run.stdout = stdout.getvalue()

        # Create new thread and runs _run
        # start a new thread
        self._thread = threading.Thread(target=anyio.run, name="ProgramRunner", args=[runner])
        self._thread.start()

        if sync:
            self.join()

    def join(self):
        """Wait for the program execution to finish

        Raises:
            _exc: Exception: when the runner is not in IDLE state
        """
        self._thread.join()
        if self._exc:
            raise self._exc

    def stop(self, sync=False):
        """Stop the program execution

        Args:
            sync: if True the call is blocking until the program execution is stopped

        Raises:
            RuntimeError: when the runner is not in IDLE state

        """
        if not self.is_running():
            raise RuntimeError("Program is not running")
        self._stop_event.set()
        if sync:
            self.join()

    def is_running(self) -> bool:
        """Check if a program is currently running

        Returns:
            bool: True if a program is running

        """
        return self._thread is not None and self.state is ProgramRunState.RUNNING


def run(
    code: str,
    robot_cell: RobotCell,
    default_robot: str | None = None,
    default_tcp: str | None = None,
    initial_state: dict[str, serializer.ElementType] | None = None,
    foreign_functions: dict[str, ForeignFunction] | None = None,
    use_plannable_context: bool = False,
) -> ProgramRunner:
    """Helper function to create a ProgramRunner and start it synchronously

    Args:
        code (str): Wandelscript code
        robot_cell (RobotCell): The RobotCell where the code is executed
        default_robot (str): The default robot that is used when no robot is active
        default_tcp (str): The default TCP that is used when no TCP is explicitly selected for a motion
        initial_state (dict[str, Any], optional): Store will be initialized with this dict. Defaults to ().
        use_plannable_context (bool): If True, the program runner will use a plannable context. Defaults to False.
        foreign_functions (dict[str, ForeignFunction], optional): 3rd party functions that you can
            register into the wandelscript language. Defaults to {}.

    Returns:
        ProgramRunner: A new ProgramRunner object

    """
    runner = ProgramRunner(
        code,
        robot_cell,
        default_robot=default_robot,
        default_tcp=default_tcp,
        initial_store=initial_state,
        foreign_functions=foreign_functions,
        use_plannable_context=use_plannable_context,
    )
    runner.start(sync=True)
    return runner


def run_file(
    file_path: Path | str, cell: RobotCell | None, default_robot: str | None, default_tcp: str | None
) -> ProgramRunner:
    path = Path(file_path)
    with open(path) as f:
        program = f.read()

    if cell is None:
        cell = SimulatedRobotCell()
    return run(program, robot_cell=cell, default_robot=default_robot, default_tcp=default_tcp, initial_state=None)
