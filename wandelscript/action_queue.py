from collections.abc import AsyncGenerator, Generator, Mapping
from functools import singledispatch
from math import inf, isinf
from typing import TYPE_CHECKING, Any

from aiostream import stream
from loguru import logger
from nova.actions import (
    CallAction,
    CombinedActions,
    Motion,
    MotionSettings,
    ReadAction,
    ReadJointsAction,
    ReadPoseAction,
    WriteAction,
)
from nova.types.state import MotionState
from pyjectory import serializer
from pyjectory.visiontypes.frames import FrameSystem

from wandelscript.datatypes import Frame
from wandelscript.exception import MotionError, NotPlannableError
from wandelscript.utils import stoppable_run

if TYPE_CHECKING:
    from nova.actions import Action, ActionLocation
    from nova.types import Pose

    from wandelscript.runtime import ExecutionContext


@singledispatch
def run_action(arg, context: ExecutionContext):
    raise NotImplementedError(f"_run not implemented for Action {type(arg)}")


@run_action.register(WriteAction)
async def _(arg: WriteAction, context: ExecutionContext) -> None:
    device = context.robot_cell.get(arg.device_id)
    return await device.write(arg.key, arg.value)


@run_action.register(ReadAction)
async def _(arg: ReadAction, context: ExecutionContext):
    device = context.robot_cell.get(arg.device_id)
    return as_builtin_type(await device.read(arg.key))


@run_action.register(ReadPoseAction)
async def _(arg: ReadPoseAction, context: ExecutionContext):
    return await context.read_pose(arg.device_id, arg.tcp)


@run_action.register(ReadJointsAction)
async def _(arg: ReadJointsAction, context: ExecutionContext):
    return await context.read_joints(arg.device_id)


@run_action.register(CallAction)
async def _(arg: CallAction, context: ExecutionContext) -> None:
    device = context.robot_cell.get(arg.device_id)
    return await device(arg.key, *arg.arguments)


class ActionQueue:
    """Collect actions from the skill and processes them

    Implementation detail:
        _record: buffer the motion between the motion pointer and program pointer

    TODO: find a better name for the class since ActionQueue is misleading and "Action" is used in different contexts
        - ProgramExecutor, Runtime, ProgramRunner, ...
    """

    MOTION_LIMIT_IN = 10000  # maximal length of motion trajectory to be used for planning
    MOTION_LIMIT_OUT = inf  # maximal length of path history to be stored

    def __init__(self, execution_context: ExecutionContext):
        self._execution_context = execution_context
        self._stop_event = execution_context.stop_event
        # A dictionary of robot identifier with corresponding TCP name
        self._tcp: dict[str, str] = {}
        # Collected motion trajectory of the corresponding robot names
        self._record: dict[str, CombinedActions] = {}
        self._last_motions: dict[str, Motion] = {}
        self._on_motion_callbacks: dict[str, Any] = {}
        self._path_history: list[CombinedActions] = []

    def reset(self):
        self._tcp.clear()
        self._record = {}
        self._path_history = []
        self._on_motion_callbacks = {}

    def is_empty(self) -> bool:
        return not any(self._record.values())

    async def trigger_actions(
        self, motion_iter: AsyncGenerator[MotionState], actions: list[ActionLocation]
    ) -> AsyncGenerator[MotionState]:
        actions = sorted(actions, key=lambda action: action.path_parameter)
        async for motion_state in motion_iter:
            logger.debug(motion_state)
            if self._stop_event.is_set():
                logger.info("Stop event set. Stopping motions...")
                break
            await self._run_callbacks(motion_state)

            last_action_index = 0
            for index, action_container in enumerate(actions):
                if action_container.path_parameter <= motion_state.path_parameter:
                    await self.run_action(action_container.action)
                    last_action_index = index + 1
                else:
                    break
            del actions[:last_action_index]
            yield motion_state

    async def _run(self):
        """The collected queue gets executed"""

        # get current collision setup
        collision_scene = await self._execution_context.robot_cell.get_current_collision_scene()

        # plan & move
        planned_motions = {}
        for motion_group_id in self._record:  # pylint: disable=consider-using-dict-items
            motion_trajectory = self._record[motion_group_id]
            if len(motion_trajectory.motions) > 0:
                if self._execution_context.debug:
                    # This can raise MotionError
                    self._update_path_history(motion_trajectory)

                motion_group = self._execution_context.get_robot(motion_group_id)
                tcp = self._tcp.get(motion_group_id, None) or await motion_group.get_active_tcp_name()

                motion_iter = motion_group.planned_motion(motion_trajectory, tcp=tcp, collision_scene=collision_scene)
                planned_motions[motion_group_id] = self.trigger_actions(motion_iter, motion_trajectory.actions.copy())
            else:
                # When the motion trajectory is empty, execute the actions
                for action_container in motion_trajectory.actions:
                    await self.run_action(action_container.action)

        if planned_motions:
            combine = stream.merge(*planned_motions.values())
            async with combine.stream() as streamer:
                async for _ in streamer:
                    pass

        self._record.clear()
        self._tcp.clear()

    async def run_action(self, action: Action):
        return await run_action(action, self._execution_context)

    async def run(self, stop_event):
        """Execute the collected motions and actions.
        This function is not reentrant.

        Args:
            stop_event: an event that can be set to stop the execution
        """

        async def stopper():
            await stop_event.wait()
            await self._execution_context.robot_cell.stop()

        self._stop_event = stop_event
        await stoppable_run(self._run(), stopper())

    async def _run_callbacks(self, motion_state):
        for callback in self._on_motion_callbacks.values():
            await callback(None, motion_state.path_parameter, motion_state.state.pose)

    def last_pose(self, robot: str) -> Pose | None:
        """Return the last pose of the collected motion trajectory

        Args:
            robot: the robot to get the last pose from

        Returns:
            The last pose of the collected motion trajectory
        """
        if last_motion := self._last_motions.get(robot, None):
            return last_motion.target
        return None

    # TODO: should be combined with push method
    def attach_action(self, action: Action, motion_group_id: str):
        """Append a new action to the queue

        Args:
            action: the action to append
            motion_group_id: the robot to append the action to
        """
        if motion_group_id not in self._record:
            self._record[motion_group_id] = CombinedActions()
        self._record[motion_group_id].append(action)

    def push(self, motions: Motion | tuple[Motion, ...], tool: str, motion_group_id: str):
        """Append a new motion to the queue.

        Args:
            motions: the motion command. If this is only a vector path, the orientation is automatically added
                based on the orientation strategy
            tool: the tool center point (TCP)
            motion_group_id: the robot to append the motion to

        Raises:
            MotionError: If motion is not possible o supported
        """
        assert isinstance(motion_group_id, str)
        if motion_group_id not in self._tcp:
            if tool is not None:
                self._tcp[motion_group_id] = tool
        else:
            if tool and self._tcp[motion_group_id] != tool:
                raise MotionError(
                    location=self._execution_context.location_in_code,
                    value=f"Changing the tcp in one motion is not supported: changed from {self._tcp[motion_group_id]} to {tool}",
                )

        if not isinstance(motions, tuple):
            motions = (motions,)

        for motion in motions:
            if motion_group_id not in self._record:
                self._record[motion_group_id] = CombinedActions()

            if len(self._record[motion_group_id]) >= self.MOTION_LIMIT_IN:
                raise MotionError(
                    location=self._execution_context.location_in_code,
                    value="Maximum motion queue size exceeded. Won't plan skill.",
                )

            self._record[motion_group_id].append(motion)
            self._last_motions[motion_group_id] = motion

    def _update_path_history(self, path: CombinedActions):
        """Update the path history for debugging

        Args:
            path: the trajectory to append to the history

        Raises:
            MotionError: If the motion queue size exceeds the limit
        """
        self._path_history.append(path)
        if len(self._path_history) > self.MOTION_LIMIT_OUT:
            raise MotionError(
                location=self._execution_context.location_in_code,
                value="Maximum motion queue size exceeded. Won't plan skill.",
            )


class PlannableActionQueue(ActionQueue):
    """ActionQueue intended to ignore all actions. Is used for the /plan/ endpoint."""

    MOTION_LIMIT_IN = 1000  # maximal length of motion trajectory to be used for planning
    MOTION_LIMIT_OUT = 1000  # maximal length of path history to be stored

    async def run_action(self, action: Action):
        # TODO: we only want to support reading from the initial args
        # in the story https://wandelbots.atlassian.net/browse/WOS-1924 the we will update the initial arguments to be
        # a record in Wandelscript. On the long run we will work on removing the support for the etcd database.
        if isinstance(action, ReadAction):
            device = self._execution_context.robot_cell[action.device_id]
            # allow reading from initial arguments & etcd database
            if device.configuration.type in ("database",):
                return await run_action(action, self._execution_context)
        raise NotPlannableError(
            location=self._execution_context.location_in_code,
            value="Actions are not supported in the plan endpoint to avoid critical side effects.",
        )


class Store:
    """Store all variables"""

    def __init__(self, init_vars: Mapping[str, Any] | None = None, parent: Store | None = None):
        self.frame_system: FrameSystem = FrameSystem() if parent is None else parent.frame_system
        self._parent: Store | None = parent
        self._data: dict[str, Any] = {}
        # self._data.update(**self.environment.robot_cell)
        self.FLANGE = Frame("flange", self.frame_system)
        self.ROBOT = Frame("robot_", self.frame_system)

        if init_vars:
            self._data.update(init_vars)

    def __getitem__(self, name: str) -> Any:
        scope_of_name = self.scope_of_name(name)
        if scope_of_name is None:
            raise KeyError(name)

        if scope_of_name is self:
            return self._data[name]

        return scope_of_name[name]

    def __setitem__(self, name: str, value: Any):
        scope_of_name = self.scope_of_name(name)
        if scope_of_name is None or scope_of_name is self:
            self._data[name] = value
        else:
            scope_of_name[name] = value

    def __contains__(self, name: str) -> bool:
        return self.scope_of_name(name) is not None

    def contains_local(self, name: str) -> bool:
        return name in self._data

    def get(self, name: str, default=None) -> Any:
        try:
            return self[name]
        except KeyError:
            return default

    def update_local(self, other: Mapping[str, Any]):
        self._data.update(other)

    def scope_of_name(self, name: str) -> Store | None:
        return next((scope for scope in self.scope_chain() if scope.contains_local(name)), None)

    def scope_chain(self) -> Generator[Store]:
        yield self
        if self._parent:
            yield from self._parent.scope_chain()

    def descent(self, init_vars: Mapping[str, Any] | None = None) -> Store:
        return Store(init_vars=init_vars, parent=self)

    @property
    def data(self) -> dict[str, Any]:
        return self._data.copy()

    @property
    def data_dict(self) -> dict[str, serializer.ElementType]:
        serialized_store = {k: serializer.encode(v) for k, v in self.data.items() if serializer.is_encodable(v)}
        serialized_store = {k: v for k, v in serialized_store.items() if not isinstance(v, float) or not isinf(v)}
        return serialized_store

    def get_motion_settings(self) -> MotionSettings:
        """Return the motion settings from the current scope

        Returns:
            The motion settings
        """
        return MotionSettings(
            **{
                field: self[MotionSettings.field_to_varname(field)]
                for field in MotionSettings.model_fields
                if MotionSettings.field_to_varname(field) in self
            }
        )
