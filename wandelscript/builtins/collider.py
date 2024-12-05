from pyjectory import datatypes as dts
from pyriphery.pyrae import Robot

from wandelscript.metamodel import register_builtin_func
from wandelscript.runtime import ExecutionContext


# all scene modification functions need to sync first, otherwise the changes affect previous motions
@register_builtin_func(pass_context=True)
async def add_static_sphere(
    context: ExecutionContext, radius: float, center_pose: dts.Pose, identifier: str = "sphere"
):
    scene = await context.robot_cell.get_current_collision_scene()
    scene.static_colliders[identifier] = dts.Collider(shape=dts.Sphere(radius=radius), pose=center_pose)


@register_builtin_func(pass_context=True)
async def add_static_box(  # pylint: disable=too-many-positional-arguments
    context: ExecutionContext,
    size_x: float,
    size_y: float,
    size_z: float,
    center_pose: dts.Pose,
    identifier: str = "box",
):
    scene = await context.robot_cell.get_current_collision_scene()
    scene.static_colliders[identifier] = dts.Collider(
        shape=dts.Box(size_x=size_x, size_y=size_y, size_z=size_z), pose=center_pose
    )


@register_builtin_func(pass_context=True)
async def add_static_convex_hull(
    context: ExecutionContext,
    vertices: list[dts.Position],
    pose: dts.Pose = dts.Pose.from_tuple([0] * 6),
    identifier: str = "convex_hull",
):
    scene = await context.robot_cell.get_current_collision_scene()
    scene.static_colliders[identifier] = dts.Collider(shape=dts.ConvexHull(vertices=vertices), pose=pose)


@register_builtin_func(pass_context=True)
async def add_static_collider_from_json(context: ExecutionContext, collider_json: str, collider_identifier: str):
    scene = await context.robot_cell.get_current_collision_scene()
    scene.static_colliders[collider_identifier] = dts.Collider.model_validate_json(collider_json)


@register_builtin_func(pass_context=True)
async def set_collider_pose(context: ExecutionContext, collider_identifier: str, pose: dts.Pose):
    scene = await context.robot_cell.get_current_collision_scene()
    if collider_identifier in scene.static_colliders:
        scene.static_colliders[collider_identifier].pose = pose


@register_builtin_func(pass_context=True)
async def get_collider_pose(context: ExecutionContext, collider_identifier: str) -> dts.Pose:
    scene = await context.robot_cell.get_current_collision_scene()
    if collider_identifier in scene.static_colliders:
        return scene.static_colliders[collider_identifier].pose
    raise ValueError(f"Collider with identifier {collider_identifier} not found in scene")


@register_builtin_func(pass_context=True)
async def remove_collider(context: ExecutionContext, collider_identifier: str) -> None:
    scene = await context.robot_cell.get_current_collision_scene()
    scene.static_colliders.pop(collider_identifier, None)


@register_builtin_func(pass_context=True)
async def set_tool_colliders(context: ExecutionContext, robot: Robot, tool_colliders: dict[str, dts.Collider]):
    scene = await context.robot_cell.get_current_collision_scene()
    if robot.identifier in scene.robot_configurations:
        scene.robot_configurations[robot.identifier].tool = tool_colliders
