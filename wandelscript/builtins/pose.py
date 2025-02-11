from nova.types import Pose

from wandelscript.metamodel import register_builtin_func
from wandelscript.utils.pose import pose_to_versor, versor_to_pose


@register_builtin_func()
def interpolate(a: Pose, b: Pose, param: float | list[float]) -> Pose | list[Pose]:
    """Interpolate between two poses"""
    va = pose_to_versor(a)
    vb = pose_to_versor(b)
    vc = (vb & va.inverse()).motor_interpolation(param) & va
    if isinstance(param, list):
        return [versor_to_pose(i) for i in vc]
    return versor_to_pose(vc)
