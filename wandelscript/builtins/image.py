from pyjectory.visiontypes import Capture, PointCloud

from wandelscript.metamodel import register_builtin_func


@register_builtin_func()
def async_take_image(camera, pose=None) -> Capture:
    result = camera()
    if pose is not None:
        result.pose = pose.to_versor()
    return result


@register_builtin_func()
def async_take_point_cloud(camera, pose=None) -> PointCloud:
    result = camera("pointcloud")
    if pose is not None:
        result.pose = pose.to_versor()
    return result
