import math

from geometricalgebra import cga3d
from nova.types import Pose, Vector3d

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
def distance(a: Pose | Vector3d, b: Pose | Vector3d) -> float:
    """Distance in [mm] between two poses or positions

    Args:
        a: The first pose or position
        b: The second pose or position

    Returns:
        The distance between the two poses or positions

    """
    a = a if isinstance(a, Vector3d) else a.position
    b = b if isinstance(b, Vector3d) else b.position
    return math.sqrt((-2 * cga3d.Vector.from_euclid(a) | cga3d.Vector.from_euclid(b)).to_scalar())


@register_builtin_func()
def to_position(pose: Pose) -> Vector3d:
    """Extract the position from a pose."""
    return pose.position


@register_builtin_func()
def to_orientation(pose: Pose) -> Pose:
    """Extract the orientation from a pose."""
    return Pose(position=Vector3d(0, 0, 0), orientation=pose.orientation)


@register_builtin_func()
def to_pose(vec: Vector3d) -> Pose:
    """Convert a position to a pose."""
    return Pose(position=vec, orientation=Vector3d(0, 0, 0))
