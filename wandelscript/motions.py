from dataclasses import dataclass

from nova.actions import PTP, Circular, CombinedActions, JointPTP, Linear, MotionSettings, cir, jnt, lin, ptp, spl
from nova.types import Pose, Vector3d
from pyjectory import pathtypes
from pyjectory.datatypes.mapper import pose_path_to_motion_trajectory
from pyjectory.tensortypes.quaternion import Quaternion

import wandelscript._types as t
from wandelscript.exception import GenericRuntimeError
from wandelscript.metamodel import Connector


@dataclass(repr=False)
class JointPointToPoint(Connector.Impl, func_name="joint_p2p"):
    def __call__(
        self, start: Pose | None, end: tuple[float, ...], args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> JointPTP:
        # TODO: should be improved and streamlined with https://wandelbots.atlassian.net/browse/WP-679
        return jnt(end, settings=motion_settings)


@dataclass(repr=False)
class Line(Connector.Impl, func_name="line"):
    def __call__(
        self, start: Pose | None, end: Pose, args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> Linear:
        return lin(end.to_tuple(), settings=motion_settings)


class PointToPoint(Line, func_name="p2p"):
    def __call__(
        self, start: Pose | None, end: Pose, args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> PTP:
        return ptp(end.to_tuple(), settings=motion_settings)


@dataclass(repr=False)
class Arc(Connector.Impl, func_name="arc"):
    @dataclass
    class Args(Connector.Impl.Args):
        intermediate: Vector3d | Pose

    def __call__(self, start: Pose | None, end: Pose, args: Args, motion_settings: MotionSettings) -> Circular:
        if isinstance(args.intermediate, Vector3d):
            if start is None:
                raise GenericRuntimeError(
                    location=None,
                    text="First segment can't be an arc with an intermediate position. Use intermediate Pose or prepend another motion.",
                )
            slerp = pathtypes.Slerp(
                Quaternion(start.orientation.as_quaternion()), Quaternion(end.orientation.as_quaternion())
            )
            # NOTE: when the intermediate is a position, the intermediate orientation is computed via slerp(0.5) between start and end
            intermediate = Pose.from_position_and_quaternion(args.intermediate, slerp(0.5))
        elif isinstance(args.intermediate, Pose):
            intermediate = args.intermediate
        else:
            raise GenericRuntimeError(location=None, text="Intermediate must be a position or a pose")
        return cir(end.to_tuple(), intermediate.to_tuple(), settings=motion_settings)
