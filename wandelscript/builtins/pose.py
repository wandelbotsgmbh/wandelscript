import math

from geometricalgebra import cga3d
from pyjectory import datatypes as dts

from wandelscript.metamodel import register_builtin_func


@register_builtin_func()
def interpolate(a: dts.Pose, b: dts.Pose, param: float | list[float]) -> dts.Pose | list[dts.Pose]:
    """Interpolate between two poses"""
    va = a.to_versor()
    vb = b.to_versor()
    vc = (vb & va.inverse()).motor_interpolation(param) & va
    if isinstance(param, list):
        return [dts.Pose.from_versor(i) for i in vc]
    return dts.Pose.from_versor(vc)


@register_builtin_func()
def distance(a: dts.Pose | dts.Position, b: dts.Pose | dts.Position) -> float:
    """Distance in [mm] between two poses or positions

    Args:
        a: The first pose or position
        b: The second pose or position

    Returns:
        The distance between the two poses or positions

    """
    a = a if isinstance(a, dts.Position) else a.position
    b = b if isinstance(b, dts.Position) else b.position
    return math.sqrt((-2 * cga3d.Vector.from_euclid(a) | cga3d.Vector.from_euclid(b)).to_scalar())


@register_builtin_func()
def to_position(pose: dts.Pose) -> dts.Position:
    """Extract the position from a pose."""
    return pose.position


@register_builtin_func()
def to_orientation(pose: dts.Pose) -> dts.Pose:
    """Extract the orientation from a pose."""
    return dts.Pose(position=dts.Position(0, 0, 0), orientation=pose.orientation)


@register_builtin_func()
def to_pose(vec: dts.Position) -> dts.Pose:
    """Convert a position to a pose."""
    return dts.Pose(position=vec, orientation=dts.Orientation(0, 0, 0))
