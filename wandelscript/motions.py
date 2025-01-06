from dataclasses import dataclass

from pyjectory import datatypes as dts
from pyjectory import pathtypes
from pyjectory.datatypes.mapper import pose_path_to_motion_trajectory
from pyjectory.tensortypes import QuaternionTensor
from pyjectory.tensortypes.quaternion import Quaternion

from wandelscript.exception import GenericRuntimeError
from wandelscript.metamodel import Connector


@dataclass(repr=False)
class JointPointToPoint(Connector.Impl, func_name="joint_p2p"):
    def __call__(
        self,
        start: dts.Pose | None,
        end: tuple[float, ...],
        args: Connector.Impl.Args,
        motion_settings: dts.MotionSettings,
    ) -> dts.JointP2P:
        # TODO: should be improved and streamlined with https://wandelbots.atlassian.net/browse/WP-679
        return dts.jnt(end, settings=motion_settings)


@dataclass(repr=False)
class Line(Connector.Impl, func_name="line"):
    def __call__(
        self, start: dts.Pose | None, end: dts.Pose, args: Connector.Impl.Args, motion_settings: dts.MotionSettings
    ) -> dts.Linear:
        return dts.lin(end.to_tuple(), settings=motion_settings)


class PointToPoint(Line, func_name="p2p"):
    def __call__(
        self, start: dts.Pose | None, end: dts.Pose, args: Connector.Impl.Args, motion_settings: dts.MotionSettings
    ) -> dts.P2P:
        return dts.p2p(end.to_tuple(), settings=motion_settings)


@dataclass(repr=False)
class Arc(Connector.Impl, func_name="arc"):
    @dataclass
    class Args(Connector.Impl.Args):
        intermediate: dts.Position | dts.Pose

    def __call__(
        self, start: dts.Pose | None, end: dts.Pose, args: Args, motion_settings: dts.MotionSettings
    ) -> dts.Circular:
        if isinstance(args.intermediate, dts.Position):
            if start is None:
                raise GenericRuntimeError(
                    location=None,
                    text="First segment can't be an arc with an intermediate position. Use intermediate Pose or prepend another motion.",
                )
            slerp = pathtypes.Slerp(
                Quaternion(start.orientation.as_quaternion()), Quaternion(end.orientation.as_quaternion())
            )
            # NOTE: when the intermediate is a position, the intermediate orientation is computed via slerp(0.5) between start and end
            intermediate = dts.Pose.from_position_and_quaternion(args.intermediate, slerp(0.5))
        elif isinstance(args.intermediate, dts.Pose):
            intermediate = args.intermediate
        else:
            raise GenericRuntimeError(location=None, text="Intermediate must be a position or a pose")
        return dts.cir(end.to_tuple(), intermediate.to_tuple(), settings=motion_settings)


class Spline(Connector.Impl, func_name="spline"):
    @dataclass
    class Args(Connector.Impl.Args):
        data: tuple[tuple[int | float, dts.Pose], ...]

    def __call__(
        self, start: dts.Pose | None, end: dts.Pose, args: Args, motion_settings: dts.MotionSettings
    ) -> Spline:
        def transform(geometry) -> Spline:
            motion_trajectory = pose_path_to_motion_trajectory(geometry)
            if len(motion_trajectory) == 0 or not isinstance(motion_trajectory[0], Spline):
                raise GenericRuntimeError(location=None, text="Spline motion could not be created")
            return motion_trajectory[0]

        if start is None:
            raise GenericRuntimeError(location=None, text="First segment can't be a spline")
        if isinstance(end, dts.Position) or isinstance(start, dts.Position):
            raise GenericRuntimeError(location=None, text="Spline only supports poses but positions are given")

        for p in args.data:
            if len(p) != 2 or not isinstance(p[0], (int, float)) or not isinstance(p[1], dts.Pose):
                raise GenericRuntimeError(location=None, text="Invalid data for a spline")
        times, keypoints = zip(*args.data)
        positions = [k.position for k in keypoints]
        orientations = [QuaternionTensor(k.to_posetensor().orientation).to_rotation_vector() for k in keypoints]
        orientations = [(o[0], o[1], o[2]) for o in orientations]

        path = dts.MotionTrajectory(
            items=[
                dts.spl((*p, *o), settings=motion_settings, time=t, path_parameter=i)
                for i, (t, p, o) in enumerate(zip(times, positions, orientations))
            ]
        )
        spline = pathtypes.CubicSplineTimedPosePath.fit(path, path.time, smooth=(0.5, 0.1, 0.1))
        approach = pathtypes.ComposedPosePath(
            position=pathtypes.Line(start.position, keypoints[0].position),
            orientation=pathtypes.Slerp(start.to_posetensor().orientation, keypoints[0].to_posetensor().orientation),
        )
        return transform(pathtypes.SequentialPosePath([approach, spline]))
