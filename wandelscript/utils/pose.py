from nova.types import Pose
from geometricalgebra import cga3d
import numpy as np


def pose_to_versor(pose: Pose) -> cga3d.Vector:
    """Convert a Pose to a versor

    Args:
        pose: The pose to convert

    Returns:
        The versor

    Examples:
    >>> p = Pose((0, 0, 5, 0, 0, 1))
    >>> assert np.allclose(pose_to_versor(p).to_pos_and_rot_vector(), [0, 0, 5, 0, 0, 1])
    [('x', 0), ('y', 0), ('z', 5), ('x', 0), ('y', 0), ('z', 1)]
    """
    return cga3d.Vector.from_pos_and_rot_vector([*pose.to_tuple()])


def versor_to_pose(versor: cga3d.Vector) -> Pose:
    """Convert a versor to a Pose

    Args:
        versor: The versor to convert

    Returns:
        The Pose

    Examples:
    >>> v = cga3d.Vector.from_pos_and_rot_vector([0, 0, 5, 0, 0, 1])
    >>> versor_to_pose(v).to_tuple()
    (0.0, 0.0, 5.0, 0.0, 0.0, 1.0)
    """
    pos_rot = versor.to_pos_and_rot_vector()
    return Pose(tuple(pos_rot))


def invert(pose: Pose) -> Pose:
    """Invert the pose, i.e., if self is rigid motion from A to B, this return rigid motion from B to A

    Returns:
        The inverse of this pose

    Examples:
    >>> p = Pose((0, 0, 5, 0, 0, 1))
    >>> assert np.allclose(invert(invert(p)).to_tuple(), p.to_tuple())
    """
    return versor_to_pose(pose_to_versor(pose).inverse())
