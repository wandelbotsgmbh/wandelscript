from dataclasses import dataclass

from nova.actions import cir, jnt, lin, ptp
from nova.actions.motions import PTP, Circular, JointPTP, Linear
from nova.types import MotionSettings, Pose, Vector3d

from wandelscript.exception import GenericRuntimeError
from wandelscript.metamodel import Connector


@dataclass(repr=False)
class JointPointToPoint(Connector.Impl, func_name="joint_ptp"):
    def __call__(
        self, start: Pose | None, end: tuple[float, ...], args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> JointPTP:
        return jnt(end, settings=motion_settings)


@dataclass(repr=False)
class JointPoint2Point(JointPointToPoint, func_name="joint_p2p"):
    def __call__(
        self, start: Pose | None, end: tuple[float, ...], args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> JointPTP:
        return jnt(end, settings=motion_settings)


@dataclass(repr=False)
class Line(Connector.Impl, func_name="line"):
    def __call__(
        self, start: Pose | None, end: Pose, args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> Linear:
        return lin(end.to_tuple(), settings=motion_settings)


class PointToPoint(Line, func_name="ptp"):
    def __call__(
        self, start: Pose | None, end: Pose, args: Connector.Impl.Args, motion_settings: MotionSettings
    ) -> PTP:
        return ptp(end.to_tuple(), settings=motion_settings)


class Point2Point(PointToPoint, func_name="p2p"):
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
        if isinstance(args.intermediate, Pose):
            intermediate = args.intermediate
        else:
            raise GenericRuntimeError(location=None, text="Intermediate must be a pose")
        return cir(end.to_tuple(), intermediate.to_tuple(), settings=motion_settings)
