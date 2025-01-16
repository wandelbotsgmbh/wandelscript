import contextlib
import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
from nova.actions import CombinedActions
from nova.types import Pose, Vector3d
from PIL import Image
from pyjectory import serializer
from pyjectory.tensortypes import QuaternionTensor
from pyjectory.visiontypes import Body, Capture, Features, PointCloud, calibrate_camera
from pyriphery.hardware import OmniCam, WandelcamClient
from pyriphery.hardware.aov import BaseAOV, IOValue
from pyriphery.pyrae import Robot
from pyriphery.robotics import CalibratableCamera

import wandelscript._types as t
from wandelscript.metamodel import register_builtin_func
from wandelscript.runtime import ExecutionContext

try:
    from linedraw.linedraw import sketch_image
except ImportError:
    sketch_image = None


@register_builtin_func()
def pose_diff(body, image_a, image_b) -> Pose:
    """
    Args:
        body (Body): the object which is used as reference
        image_a: the image taken in the one frame
        image_b: the target taken in the one frame

    Returns:
        The pose between the two frames
    """
    pose, residual = body.pose_difference(image_a, image_b)
    localize_guess = Pose.from_versor(pose)
    return localize_guess


# @register_builtin_func()
# def reconstruct_body(captures: List[Capture], flange2camera: Pose) -> Body:
#     if not HAS_APRILTAG:
#         raise ValueError("To use this method install apriltag")
#     raise NotImplementedError()
#     captures = update_captures(captures, flange2camera.to_versor())
#     detector = ApriltagDetector("tag36h11")
#     body = Body.from_multiview(captures, detector)
#     return body

# TODO: this plugin should be part of a special plugin package similar to the plugin.sanding package
# @register_builtin_func()
# def reconstruct_body_with_pose_reference(
#     captures: List[Capture], references: List[Capture], calibration_target: Body
# ) -> Body:
#     if not HAS_APRILTAG:
#         raise ValueError("To use this method install apriltag")
#     for c, r in zip(captures, references):
#         pose = calibration_target.localize_capture(r)[0]
#         c.pose = pose
#     detector = ApriltagDetector("tag36h11")
#     body = Body.from_multiview(captures, detector)
#     return body


@register_builtin_func()
def load(filename: str, type_: str) -> t.ElementType:
    if type_ == "pose":
        return Pose.load(filename)
    if type_ == "body":
        return Body.load(filename)
    return pickle.load(open(filename, "rb"))


@register_builtin_func()
def save(value: t.ElementType, filename: str):
    if isinstance(value, (Body, Pose)):
        value.save(filename)
    else:
        with open(filename, "wb", encoding="utf-8") as f:
            pickle.dump(value, f)


@register_builtin_func()
def save_json(value: t.ElementType, filename: str):
    encoding = serializer.encode(value)
    with open(filename, "wb") as f:
        f.write(encoding.json().encode("utf-8"))


@register_builtin_func()
def load_json(filename: str) -> t.ElementType:
    with open(filename, "rb") as f:
        return serializer.decode(serializer.ElementType(value=json.loads(f.read())))


# @register_builtin_func()
# def calibrate(observations: List[Capture], body: Body) -> Tuple[Pose, Pose]:
#     flange2camera, roboter2object, calib_error = calibrate_camera(observations, body)
#     print(f"Calibration error {calib_error}")
#     return Pose.from_versor(flange2camera), Pose.from_versor(roboter2object)


@register_builtin_func()
def calibrate_hand2eye_and_robot2world(
    observations: list[Capture] | list[Features], poses: list[Pose], world: Body
) -> tuple[Pose, Pose]:
    """The hand-eye calibration

    Args:
         observations: a list of n images
         poses: the list of n hand-to-world poses corresponding to the obervations
         world: the object which is observed

    Returns:
        the hand-to-eye pose and the robot-to-world pose
    """
    p = [i.to_versor() for i in poses]
    flange2camera, roboter2object, calib_error = calibrate_camera(observations, p, world)
    print(f"Calibration error {calib_error}")
    return Pose.from_versor(flange2camera), Pose.from_versor(roboter2object)


@register_builtin_func()
def absolute_pose(a: Capture, body: Body) -> Pose:
    pose, (alg_error, geo_error) = body.localize(a)
    print("absolute pose", alg_error, geo_error)
    if alg_error > 25:
        raise NotImplementedError()
    return Pose.from_versor(pose.inverse())


# TODO: Is robotcell still a device inside the wandelscript??
@register_builtin_func()
def read_tcp(robotcell, name: str) -> Pose:
    return Pose.from_pose(robotcell.robot.get_tool_names()[name])


@register_builtin_func()
async def get_tcp_pose(robot: Robot, name: str) -> Pose:
    tcps = await robot.get_tcps()
    return tcps[name]


@register_builtin_func()
def cap_to_pose(capture) -> Pose:
    return Pose.from_versor(capture.pose)


@register_builtin_func()
def posquat_to_pose(x, y, z, rw, rx, ry, rz) -> Pose:  # pylint: disable=too-many-positional-arguments
    vec = QuaternionTensor([rw, rx, ry, rz]).to_rotation_vector()
    pose = Pose(position=Vector3d(x, y, z), orientation=Vector3d(vec[0], vec[1], vec[2]))
    return pose


@register_builtin_func()
def board_to_corner_points(board: Body) -> list[Vector3d]:
    mx = np.max(board.points, axis=0)
    return [Vector3d(0, 0, 0), Vector3d(mx[0], 0, 0), Vector3d(mx[0], mx[1], 0), Vector3d(0, mx[1], 0)]


@register_builtin_func()
def board_to_inner_corners(board: Body) -> list[Vector3d]:
    return [
        Vector3d(*board["corner_ul"]),
        Vector3d(*board["corner_ll"]),
        Vector3d(*board["corner_ur"]),
        Vector3d(*board["corner_lr"]),
    ]


@register_builtin_func()
def random_position_normal(scale=1):
    return Vector3d(*np.random.normal(scale=scale, size=3))


@register_builtin_func()
def random_normal(scale=1):
    return np.random.normal(scale=scale)


@register_builtin_func()
def random_pose_normal(pos_scale=10, rot_scale=0.1):
    return Pose(
        position=Vector3d(*np.random.normal(scale=pos_scale, size=3)),
        orientation=Vector3d(*np.random.normal(scale=rot_scale, size=3)),
    )


@register_builtin_func()
def random_pose_uniform(pos_scale=10, rot_scale=0.1):
    return Pose(
        position=Vector3d(*(pos_scale * (np.random.random(size=3) - 0.5))),
        orientation=Vector3d(*(rot_scale * (np.random.normal(scale=rot_scale, size=3) - 0.5))),
    )


@register_builtin_func()
def detect_features(detector, captures):
    return detector(captures)


@register_builtin_func()
def sketch(image: Capture) -> tuple[tuple[Vector3d, ...], ...]:
    if sketch_image is None:
        raise ValueError("Install linedraw")
    s = max(image.data.shape[:2])
    with contextlib.redirect_stdout(None):
        lines = sketch_image(Image.fromarray(image.data))
    strokes = tuple(tuple(Vector3d(x / s, y / s, 0) for (x, y) in line) for line in lines)
    return strokes


@register_builtin_func()
def zip_dataset(  # pylint: disable=too-many-positional-arguments
    name: str,
    info: str,
    calibration: Pose,
    flange_poses: list[Pose],
    captures: list[Capture],
    point_clouds: list[PointCloud] | None = None,
    camera=None,
    robot=None,
):
    path = Path("datasets") / "_".join([name, datetime.now().strftime("%Y%m%d%H%M%S")])
    path.mkdir(parents=True, exist_ok=True)
    assert len(flange_poses) == len(captures)
    assert path.is_dir()

    # use decode function for generic saving ???
    save(calibration, str(path / "calibration_hand_eye.pkl"))
    for i, pose in enumerate(flange_poses):
        save(pose, str(path / f"capture_{i}_robot_pose.pkl"))
        Image.fromarray(captures[i].data).save(str(path / f"capture_{i}_image.jpeg"))
        if point_clouds is not None:
            point_clouds[i].to_ply_file(str(path / f"capture_{i}_pcd.ply"))

    description = {
        "datetime": str(datetime.now()),
        "size": str(len(flange_poses)),
        "camera": camera.__class__.__name__,
        "camera_config": camera.configuration.dict() if camera is not None else None,
        "robot_config": robot.configuration.dict() if robot is not None else None,
        "info": info,
    }

    with open(str(path / "description.json"), "w", encoding="utf-8") as description_file:
        json.dump(description, description_file)

    shutil.make_archive(str(path), "zip", root_dir=path, base_dir=None)
    shutil.rmtree(path)


@register_builtin_func()
def to_string(value) -> str:
    """
    This function is required due to a bug in wandelscript. The Fanuc TCP '3' is converted to float 3.0
    The reason is the ordering within pyjectory.serializer.FlatElementType.

    Args:
        value: to be converted to a string

    Returns:
        string without separator and trailing zeros
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@register_builtin_func()
def check_tcp_name(tcp_name: int | float | str) -> str:
    return to_string(tcp_name)


@register_builtin_func(pass_context=True)
async def motion_trajectory_to_json_string(context: ExecutionContext, robot: Robot):
    robot_name = robot.configuration.identifier
    # pylint: disable=protected-access
    return context.action_queue._record[robot_name].model_dump_json()


@register_builtin_func(pass_context=True)
def motion_trajectory_from_json_string(
    context: ExecutionContext, robot: Robot, json_string: str, tcp_name: str | None = None
):
    trajectory = CombinedActions.model_validate_json(json_string)
    context.action_queue._record[robot.configuration.identifier] = trajectory  # pylint: disable=protected-access
    if tcp_name is not None:
        context.action_queue._tcp[robot.configuration.identifier] = tcp_name  # pylint: disable=protected-access


@register_builtin_func()
def is_omnicam(camera: CalibratableCamera) -> bool:
    if isinstance(camera, WandelcamClient):
        return camera.configuration.camera_configuration.get("type") == "omnicam"
    return isinstance(camera, OmniCam)


@register_builtin_func()
def get_aov_compliance_ios(pressure: float, aov_device: BaseAOV) -> tuple[tuple[str], tuple[IOValue]]:
    io_dict = aov_device.set_compliance(pressure=pressure)
    return tuple(io_dict.keys()), tuple(io_dict.values())


@register_builtin_func()
def get_aov_compliance_ios_by_force(force: float, aov_device: BaseAOV) -> tuple[tuple[str], tuple[IOValue]]:
    io_dict = aov_device.set_force(force=force)
    return tuple(io_dict.keys()), tuple(io_dict.values())


@register_builtin_func()
def get_aov_motor_ios(state: bool, aov_device: BaseAOV) -> tuple[tuple[str], tuple[IOValue]]:
    io_dict = aov_device.set_motor(state=state)
    return tuple(io_dict.keys()), tuple(io_dict.values())


@register_builtin_func()
def add_calibration_point(camera: CalibratableCamera, robot_pose: Pose) -> bool:
    return camera.add_calibration_point(robot_pose.to_posetensor())


@register_builtin_func()
def reset_calibration(camera: CalibratableCamera) -> bool:
    return camera.reset_calibration()


@register_builtin_func()
def get_calibration_from_camera(camera: CalibratableCamera) -> Pose:
    return Pose.from_posetensor(camera.get_calibration())


@register_builtin_func()
def get_calibration_board_pose(camera: CalibratableCamera) -> Pose:
    return Pose.from_posetensor(camera.get_calibration_board_pose())
