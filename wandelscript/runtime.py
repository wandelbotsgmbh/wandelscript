# pylint: disable=too-many-instance-attributes
import asyncio
import contextvars
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager

import anyio
from nova.types import Pose
from pyjectory import serializer
from pyriphery.robotics import AbstractRobot, Device, RobotCell

from wandelscript import exception as wsexception
from wandelscript.action_queue import ActionQueue, Store

DEFAULT_CALL_STACK_SIZE = 64
"""Default size of the call stack. Currently arbitrary."""

current_execution_context_var: contextvars.ContextVar = contextvars.ContextVar("current_execution_context_var")


class ExecutionContext:
    _default_robot: str | None
    _active_robot: str | None = None
    _robot_ids: list[str]

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        robot_cell: RobotCell,
        stop_event: anyio.Event,
        default_robot: str | None = None,
        default_tcp: str | None = None,
        initial_vars: dict[str, serializer.ElementType] | None = None,
        debug: bool = False,
    ):
        self.robot_cell: RobotCell = robot_cell
        self._robot_ids = robot_ids = robot_cell.get_robot_ids()

        if default_robot is None:
            # If no default robot is set
            #   1) there is only one robot in the cell: use that one
            #   2) multiple robots in the cell: no default robot is set. When trying to execute code outside of a robot
            #       context an error will be raised
            self._default_robot = robot_ids[0] if len(robot_ids) == 1 else None
        else:
            # If a default robot is set, use it
            self._default_robot = default_robot

        if initial_vars is None:
            initial_vars = {}

        initial_vars.update(__tcp__=default_tcp, **robot_cell)
        self.call_stack = CallStack(DEFAULT_CALL_STACK_SIZE)
        self.call_stack.push(Store(initial_vars))
        self.interceptors: list[Interceptor] = []
        self.stop_event: anyio.Event = stop_event
        # this will be continuously updated by the metamodel when the skill is executed
        self.location_in_code: wsexception.TextRange | None = None
        self.debug = debug
        # This holds references to the tasks created by asyncio.create_task() during skill execution.
        # This is necessary because of https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task only
        # creating weak references for the in the event loop
        # also it might be sensible to store the data in thread local storage because it is probably
        # event_loop dependent
        self.asyncio_task_handles: set[asyncio.Task] = set()
        # creating the ActionQueue last since we pass self and therefore need to be initialized properly
        self.action_queue: ActionQueue = ActionQueue(self)

    def is_in_robot_context(self) -> bool:
        return self._active_robot is not None

    @property
    def default_robot(self) -> str | None:
        return self._default_robot

    @property
    def active_robot(self) -> str:
        """Return the robot that should be used for execution.

        1. In a robot context:
            The robot that is currently active is returned.
        2: Outside of a robot context:
            The default robot is returned. If no default robot is set an error is raised.

        Returns:
            The robot that should be used for execution.

        Raises:
            WrongRobotError: If no default robot is set and the execution is outside of a robot context.

        """
        if not self._robot_ids:
            raise wsexception.WrongRobotError(text="No robot found in robot cell.", location=self.location_in_code)
        if self._active_robot is not None:
            return self._active_robot
        if self._default_robot is None:
            raise wsexception.WrongRobotError(
                text="No default robot found. Cannot execute outside of a robot context.",
                location=self.location_in_code,
            )
        return self._default_robot

    @contextmanager
    def with_robot(self, robot: str):
        if self.is_in_robot_context():
            raise ValueError(f"Cannot change to robot '{robot}' while another robot '{self.active_robot}' is active")
        self._active_robot = robot
        try:
            yield self
        finally:
            self._active_robot = None

    @property
    def store(self):
        return self.call_stack.current_frame

    @contextmanager
    def new_call_frame(self, store: Store, init_locals: dict) -> Iterator[None]:
        self.call_stack.push(store.descent(init_vars=init_locals))
        yield
        self.call_stack.pop()

    async def sync(self):
        # TODO do we maybe also want to sync more things
        if self.is_in_robot_context():
            raise wsexception.NestedSyncError(location=self.location_in_code)
        await self.action_queue.run(self.stop_event)

    async def wait(self, duration: int):
        await self.robot_cell.timer(duration)

    def get_device(self, name: str) -> Device:
        return self.robot_cell[name]

    def get_robot(self, name=None) -> AbstractRobot:
        name = name or self.active_robot
        try:
            return self.robot_cell.get_robot(name)
        except KeyError as exc:
            raise wsexception.WrongRobotError(location=self.location_in_code, text=f"Unknown robot: '{name}'") from exc

    async def read_pose(self, robot_name: str, tcp: str | None = None) -> Pose:
        tcp = tcp or await self.get_robot(robot_name).get_active_tcp_name()
        tcp_pose = await self.get_robot(robot_name).get_state(tcp)
        return tcp_pose.pose

    async def read_joints(self, robot_name: str) -> tuple:
        tcp = await self.get_robot(robot_name).get_active_tcp_name()
        robot_state = await self.get_robot(robot_name).get_state(tcp)
        return robot_state.joints


class CallStack:
    """The call stack for a wandelscript skill execution
    Attributes:
        max_frames: the maximum call depth.
    """

    def __init__(self, max_frames: int):
        self.max_frames: int = max_frames
        self._frames: list[Store] = []

    @property
    def current_frame(self):
        return self._frames[-1]

    def push(self, frame: Store) -> None:
        if len(self._frames) < self.max_frames:
            self._frames.append(frame)
        else:
            location = current_execution_context().location_in_code
            raise wsexception.GenericRuntimeError(
                location=location, text=f"Maximum call stack size of {self.max_frames} exceeded."
            )

    def pop(self) -> Store:
        return self._frames.pop()


Interceptor = Callable[[Coroutine, ExecutionContext], Coroutine]


def current_execution_context() -> ExecutionContext:
    return current_execution_context_var.get()
