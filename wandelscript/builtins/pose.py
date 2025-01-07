import math

from geometricalgebra import cga3d
from nova.types import Pose

from wandelscript.metamodel import register_builtin_func


@register_builtin_func()
def interpolate(a: Pose, b: Pose, param: float | list[float]) -> Pose | list[Pose]:
    """Interpolate between two poses"""
    va = a.to_versor()
    vb = b.to_versor()
    vc = (vb & va.inverse()).motor_interpolation(param) & va
    if isinstance(param, list):
        return [Pose.from_versor(i) for i in vc]
    return Pose.from_versor(vc)


@register_builtin_func()
def distance(a: Pose | dts.Position, b: Pose | dts.Position) -> float:
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
def to_position(pose: Pose) -> dts.Position:
    """Extract the position from a pose."""
    return pose.position


@register_builtin_func()
def to_orientation(pose: Pose) -> Pose:
    """Extract the orientation from a pose."""
    return Pose(position=dts.Position(0, 0, 0), orientation=pose.orientation)


@register_builtin_func()
def to_pose(vec: dts.Position) -> Pose:
    """Convert a position to a pose."""
    return Pose(position=vec, orientation=dts.Orientation(0, 0, 0))
