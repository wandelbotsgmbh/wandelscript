import contextlib
import json
import pickle
import shutil
from datetime import datetime
from functools import reduce
from pathlib import Path

import numpy as np
from geometricalgebra import cga3d
from geometricalgebra.cga import project_to_flat
from PIL import Image
from pyjectory import datatypes as dts
from pyjectory import serializer
from pyjectory.pathtypes import CircularSegment, ComposedPosePath, PosePath, Slerp
from pyjectory.tensortypes import QuaternionTensor
from pyjectory.visiontypes import Body, Capture, Features, PointCloud, calibrate_camera
from pyjectory.visiontypes.handeyecalibration import refine_hand_eye_calibration as refine_hand_eye_calibration_
from pyjectory.visiontypes.poser import triangulate
from pyriphery.hardware import OmniCam, WandelcamClient
from pyriphery.hardware.aov import BaseAOV, IOValue
from pyriphery.pyrae import Robot
from pyriphery.robotics import CalibratableCamera

from wandelscript.metamodel import Connector, register_builtin_func
from wandelscript.runtime import ExecutionContext

try:
    from linedraw.linedraw import sketch_image
except ImportError:
    sketch_image = None


# TODO: SPLIT: What's this?
class Screw(Connector.Impl, func_name="screw"):
    def __call__(self, start: dts.Pose, end: dts.Pose, _args, motion_settings: dts.MotionSettings) -> PosePath:
        v = cga3d.Vector.from_motor_estimation(start.to_versor().apply(cga3d.FRAME), end.to_versor().apply(cga3d.FRAME))
        # TODO: should be
        # v = end.to_versor() & start.to_versor().invert()
        screw = v.view(cga3d.Vector).motor_to_screw()
        intermediate = cga3d.Vector.from_screw(screw[0] / 2, screw[1] / 2) & start.to_versor()

        return ComposedPosePath(
            position=CircularSegment.from_three_points(
                start.position, end.position, dts.Position.from_multivector(intermediate.apply(cga3d.e_0))
            ),
            orientation=Slerp(
                QuaternionTensor.from_rotation_vector(start.orientation),
                QuaternionTensor.from_rotation_vector(end.orientation),
            ),
        )


@register_builtin_func()
def pose_diff(body, image_a, image_b) -> dts.Pose:
    """
    Args:
        body (Body): the object which is used as reference
        image_a: the image taken in the one frame
        image_b: the target taken in the one frame

    Returns:
        The pose between the two frames
    """
    pose, residual = body.pose_difference(image_a, image_b)
    localize_guess = dts.Pose.from_versor(pose)
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
def load(filename: str, type_: str) -> dts.ElementType:
    if type_ == "pose":
        return dts.Pose.load(filename)
    if type_ == "body":
        return Body.load(filename)
    return pickle.load(open(filename, "rb"))


@register_builtin_func()
def save(value: dts.ElementType, filename: str):
    if isinstance(value, (Body, dts.Pose)):
        value.save(filename)
    else:
        with open(filename, "wb", encoding="utf-8") as f:
            pickle.dump(value, f)


@register_builtin_func()
def save_json(value: dts.ElementType, filename: str):
    encoding = serializer.encode(value)
    with open(filename, "wb") as f:
        f.write(encoding.json().encode("utf-8"))


@register_builtin_func()
def load_json(filename: str) -> dts.ElementType:
    with open(filename, "rb") as f:
        return serializer.decode(serializer.ElementType(value=json.loads(f.read())))


# @register_builtin_func()
# def calibrate(observations: List[Capture], body: Body) -> Tuple[Pose, Pose]:
#     flange2camera, roboter2object, calib_error = calibrate_camera(observations, body)
#     print(f"Calibration error {calib_error}")
#     return Pose.from_versor(flange2camera), Pose.from_versor(roboter2object)


@register_builtin_func()
def calibrate_hand2eye_and_robot2world(
    observations: list[Capture] | list[Features], poses: list[dts.Pose], world: Body
) -> tuple[dts.Pose, dts.Pose]:
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
    return dts.Pose.from_versor(flange2camera), dts.Pose.from_versor(roboter2object)


@register_builtin_func()
def absolute_pose(a: Capture, body: Body) -> dts.Pose:
    pose, (alg_error, geo_error) = body.localize(a)
    print("absolute pose", alg_error, geo_error)
    if alg_error > 25:
        raise NotImplementedError()
    return dts.Pose.from_versor(pose.inverse())


# def plane_from_poses(poses: List[Pose]) -> Pose:
#     assert len(poses) == 3
#     versors = cga3d.Vector.stack([poses.to_versor()])
#     points = versors.apply(cga3d.e_0)
#     plane = points[0] ^ points[1] ^ points[2] ^ cga3d.e_inf
#     cga3d.Vector.from_motor_estimation()


# TODO: Is robotcell still a device inside the wandelscript??
@register_builtin_func()
def read_tcp(robotcell, name: str) -> dts.Pose:
    return dts.Pose.from_pose(robotcell.robot.get_tool_names()[name])


@register_builtin_func()
async def get_tcp_pose(robot: Robot, name: str) -> dts.Pose:
    tcps = await robot.get_tcps()
    return tcps[name]


@register_builtin_func()
def cap_to_pose(capture) -> dts.Pose:
    return dts.Pose.from_versor(capture.pose)


@register_builtin_func()
def posquat_to_pose(x, y, z, rw, rx, ry, rz) -> dts.Pose:  # pylint: disable=too-many-positional-arguments
    vec = QuaternionTensor([rw, rx, ry, rz]).to_rotation_vector()
    pose = dts.Pose(position=dts.Position(x, y, z), orientation=dts.Orientation(vec[0], vec[1], vec[2]))
    return pose


@register_builtin_func()
def board_to_corner_points(board: Body) -> list[dts.Position]:
    mx = np.max(board.points, axis=0)
    return [dts.Position(0, 0, 0), dts.Position(mx[0], 0, 0), dts.Position(mx[0], mx[1], 0), dts.Position(0, mx[1], 0)]


@register_builtin_func()
def board_to_inner_corners(board: Body) -> list[dts.Position]:
    return [
        dts.Position(*board["corner_ul"]),
        dts.Position(*board["corner_ll"]),
        dts.Position(*board["corner_ur"]),
        dts.Position(*board["corner_lr"]),
    ]


@register_builtin_func()
def point_set_registration(source: list[dts.Position], target: list[dts.Position]) -> dts.Pose:
    p = cga3d.Vector.stack([a.as_multivector() for a in source])
    q = cga3d.Vector.stack([a.as_multivector() for a in target])
    return dts.Pose.from_versor(cga3d.Vector.from_motor_estimation(p, q))


@register_builtin_func()
def rectify_capture(obj2cam: dts.Pose, capture: Capture, body: Body, dpi=100, debug=False) -> Capture:
    capture.pose = None  # avoid using the default pose (flange)
    versor = obj2cam.to_versor()
    corners_in_object = [body["corner_ul"], body["corner_ur"], body["corner_ll"], body["corner_lr"]]
    corners_in_camera = versor.inverse().apply(cga3d.Vector.from_euclid(corners_in_object))
    corners_in_pixel = capture.intrinsics.direction_to_pixel(
        (corners_in_camera ^ cga3d.e_0 ^ cga3d.e_inf).line_to_point_direction()[1]
    )
    width = int(np.linalg.norm(np.asarray(body["corner_ul"]) - body["corner_ur"]) / 25.4 * dpi)
    height = int(np.linalg.norm(np.asarray(body["corner_ul"]) - body["corner_ll"]) / 25.4 * dpi)
    rectified = capture.rectified(corners_in_pixel, (height, width))

    if debug:
        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

        plt.figure()
        plt.imshow(capture.data)
        plt.scatter(*corners_in_pixel.T)
        plt.figure()
        plt.imshow(rectified.data)
        plt.scatter(*rectified.intrinsics.direction_to_pixel(corners_in_camera).T)
    return rectified


@register_builtin_func()
def rotation_axis(a: dts.Position, b: dts.Position, angle: float) -> dts.Pose:
    v = cga3d.Vector.from_screw(angle * (a.as_multivector() ^ b.as_multivector() ^ cga3d.e_inf).normed(), 0)
    return dts.Pose.from_versor(v)


@register_builtin_func()
def orientations(
    start1: dts.Position, end1: dts.Position, left: dts.Position, right: dts.Position
) -> tuple[dts.Pose, dts.Pose, dts.Pose]:
    """Return the orientations of the planes thought points (start, end, left), (start, end, right) and the average

    Args:
        start1: the start of the edge
        end1: the end of the edge
        left: any point of the left-hand-side plane
        right: any point of the right-hand-side plane

    Returns:
        Tuple (a, b, c)
    """
    a = left.as_multivector()
    b = right.as_multivector()
    start = start1.as_multivector()
    end = end1.as_multivector()

    planes = (start ^ end ^ cga3d.Vector.stack([a, -b]) ^ cga3d.e_inf).normed()

    plane_middle = sum(planes)

    pose_middle = cga3d.Vector.from_motor_estimation(
        cga3d.Vector.stack(
            [cga3d.e_0, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_inf, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_inf]
        ),
        cga3d.Vector.stack([start, start ^ end ^ cga3d.e_inf, plane_middle]),
    )

    center_point = pose_middle.apply((0.9 * cga3d.e_3).up())
    touching_points = project_to_flat(center_point, planes)

    pose_a = cga3d.Vector.from_motor_estimation(
        cga3d.Vector.stack(
            [cga3d.e_0, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_inf, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_inf]
        ),
        cga3d.Vector.stack([touching_points[0], start ^ end ^ cga3d.e_inf, planes[0]]),
    )

    pose_b = cga3d.Vector.from_motor_estimation(
        cga3d.Vector.stack(
            [cga3d.e_0, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_inf, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_inf]
        ),
        cga3d.Vector.stack([touching_points[1], start ^ end ^ cga3d.e_inf, planes[1]]),
    )

    # poses = cga3d.Vector.stack([pose_a, pose_b])

    return (dts.Pose.from_versor(pose_a), dts.Pose.from_versor(pose_b), dts.Pose.from_versor(pose_middle))


@register_builtin_func()
def random_position_normal(scale=1):
    return dts.Position(*np.random.normal(scale=scale, size=3))


@register_builtin_func()
def random_normal(scale=1):
    return np.random.normal(scale=scale)


@register_builtin_func()
def random_pose_normal(pos_scale=10, rot_scale=0.1):
    return dts.Pose(
        position=dts.Position(*np.random.normal(scale=pos_scale, size=3)),
        orientation=dts.Orientation(*np.random.normal(scale=rot_scale, size=3)),
    )


@register_builtin_func()
def random_pose_uniform(pos_scale=10, rot_scale=0.1):
    return dts.Pose(
        position=dts.Position(*(pos_scale * (np.random.random(size=3) - 0.5))),
        orientation=dts.Orientation(*(rot_scale * (np.random.normal(scale=rot_scale, size=3) - 0.5))),
    )


@register_builtin_func()
def equidistant_point_on_line(start: dts.Position, end: dts.Position, max_distance) -> list[dts.Position]:
    """Sample equidistant points between start and end

    Args:
        start: first point
        end: final point
        max_distance: the spacing between sampled points is maximal `max_distance'

    Returns:
        list of points interpolation from start to end
    """
    a = cga3d.Vector.from_euclid(start)
    b = cga3d.Vector.from_euclid(end)
    length = np.sqrt(np.maximum(0, -2 * a.scalar_product(b)))
    num_of_points = int(length / max_distance)
    params = np.linspace(0, 1, num_of_points + 1)
    return [dts.Position.from_multivector(a * (1 - p) + b * p) for p in params]


@register_builtin_func()
def equidistant_orientations(start: dts.Pose, end: dts.Pose, steps: int) -> list[dts.Pose]:
    """Sample equidistant points between start and end

    Args:
        start: first point
        end: final point
        steps: the number of steps

    Returns:
        list of poses interpolating from start to end

    TODO: - pose interpolation
    TODO: motor to screw from identity
    """
    v = cga3d.Vector.from_motor_estimation(
        start.to_versor().apply(cga3d.FRAME), end.to_versor().apply(cga3d.FRAME)
    ).view(cga3d.Vector)
    rotation_axis, translation = v.motor_to_screw()  # pylint: disable=redefined-outer-name
    phi = np.linspace(0, 1, steps)
    intermediates = cga3d.Vector.from_screw(rotation_axis * phi, translation * phi) & start.to_versor()
    return [dts.Pose.from_versor(i) for i in intermediates]


@register_builtin_func()
def distance_from_corner(a: dts.Pose, b: dts.Pose, radius) -> float:
    plane = cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_inf
    cos_angle = a.to_versor().apply(plane).scalar_product(b.to_versor().apply(plane))
    cos_angle = np.clip(cos_angle, -1, 1)
    angle = np.arccos(cos_angle)
    hypotenuse = radius / np.sin(angle / 2)
    return hypotenuse


@register_builtin_func()
def find_edge(  # pylint: disable=too-many-positional-arguments
    left_start: dts.Position,
    left_end: dts.Position,
    left_auxiliary: dts.Position,
    right_start: dts.Position,
    right_end: dts.Position,
    right_auxiliary: dts.Position,
) -> tuple[dts.Pose, dts.Pose]:
    # TODO: 6 points? What 6 points? Is there a typo?
    """Given 6 points, two poses describing the edge are returned

    Args:
        left_start: approximate start position at the left plane
        left_end: approximate end position at the left plane
        left_auxiliary: a third point on the left plane
        right_start: approximate start position at the right plane
        right_end: approximate end position at the right plane
        right_auxiliary: a third point on the right plane

    Returns:
        start_pose: a pose with position at the start and an orientation normal to the left plane
        end_pose: a pose with position at the start and an orientation normal to the right plane
    """
    points = cga3d.Vector.from_euclid(
        [[left_start, left_end, left_auxiliary], [right_start, right_end, right_auxiliary]]
    )
    planes = points[:, 0] ^ points[:, 1] ^ points[:, 2] ^ cga3d.e_inf * np.array([1, -1])
    edge = -planes[0].meet(planes[1])
    start_end = project_to_flat(sum(points[:, :2]), edge)
    poses = [
        cga3d.Vector.from_motor_estimation(
            cga3d.Vector.stack(
                [cga3d.e_0, -cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_0 ^ cga3d.e_inf, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_inf]
            ),
            cga3d.Vector.stack([start_end[i], planes[i], edge]),
        )
        for i in range(2)
    ]
    return dts.Pose.from_versor(poses[0]), dts.Pose.from_versor(poses[1])


@register_builtin_func()
def find_edge_from_4_poses(
    left_start: dts.Pose, left_end: dts.Pose, right_start: dts.Pose, right_end: dts.Pose
) -> tuple[dts.Pose, dts.Pose]:
    """Given 6 points, two poses describing the edge are returned

    Args:
        left_start: pose whose xy-plane is parallel to the left surface and the origin is close to start position
        left_end: pose whose xy-plane is parallel to the left surface and the origin is close to end position
        right_start: pose whose xy-plane is parallel to the right surface and the origin is close to start position
        right_end: pose whose xy-plane is parallel to the right surface and the origin is close to end position

    Returns:
        start_pose: a pose with position at the start and an orientation normal to the left plane
        end_pose: a pose with position at the end and an orientation normal to the right plane
    """
    right_start_versor = right_start.to_versor()
    right_end_versor = right_end.to_versor()
    left_start_versor = left_start.to_versor()
    left_end_versor = left_end.to_versor()

    xy_plane = cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_inf ^ cga3d.e_0
    pose_plane_right = cga3d.Vector.from_motor_estimation(
        cga3d.Vector.stack([cga3d.e_0, cga3d.e_0, xy_plane, xy_plane]),
        cga3d.Vector.stack(
            [
                right_start_versor.apply(cga3d.e_0),
                right_end_versor.apply(cga3d.e_0),
                right_start_versor.apply(xy_plane),
                right_end_versor.apply(xy_plane),
            ]
        ),
    )
    pose_plane_left = cga3d.Vector.from_motor_estimation(
        cga3d.Vector.stack([cga3d.e_0, cga3d.e_0, xy_plane, xy_plane]),
        cga3d.Vector.stack(
            [
                left_start_versor.apply(cga3d.e_0),
                left_end_versor.apply(cga3d.e_0),
                left_start_versor.apply(xy_plane),
                left_end_versor.apply(xy_plane),
            ]
        ),
    )

    points = cga3d.Vector.from_euclid(
        [
            [left_start_versor.apply(cga3d.e_0).to_euclid(), left_end_versor.apply(cga3d.e_0).to_euclid()],
            [right_start_versor.apply(cga3d.e_0).to_euclid(), right_end_versor.apply(cga3d.e_0).to_euclid()],
        ]
    )

    planes = cga3d.Vector.stack([pose_plane_left.apply(xy_plane), pose_plane_right.apply(xy_plane)])
    edge = -planes[0].meet(planes[1])
    start_end = project_to_flat(sum(points[:, :2]), edge)
    poses = [
        cga3d.Vector.from_motor_estimation(
            cga3d.Vector.stack(
                [cga3d.e_0, -cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_0 ^ cga3d.e_inf, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_inf]
            ),
            cga3d.Vector.stack([start_end[i], planes[i], edge]),
        )
        for i in range(2)
    ]
    return dts.Pose.from_versor(poses[0]), dts.Pose.from_versor(poses[1])


@register_builtin_func()
def refine_hand_eye_calibration(features: list[Features], poses_hand2robot: list[dts.Pose], guess_eye2hand: dts.Pose):
    d = cga3d.Vector.from_scaling(0.02)
    ids: list[str] = list(reduce(set.union, features, set()))  # type: ignore
    result = refine_hand_eye_calibration_(
        light_rays=cga3d.Vector.stack([f.as_lightfield(ids) for f in features]),
        hand2robot=d.apply(cga3d.Vector.stack([p.to_versor().inverse() for p in poses_hand2robot])),
        guess=d.apply(guess_eye2hand.to_versor()),
    )
    return dts.Pose.from_versor(d.inverse().apply(result))


@register_builtin_func()
def detect_features(detector, captures):
    return detector(captures)


@register_builtin_func(name="body")
def body_(features, detector):
    ids = np.array(list(reduce(set.union, features, set())))
    z = cga3d.Vector.stack([f.as_lightfield(ids) for f in features])
    z._values = z._values.swapaxes(1, 0)  # pylint: disable=protected-access
    a = triangulate(z ^ cga3d.e_inf)
    mask = -a.scalar_product(cga3d.e_inf) > 1e-8
    return Body(dict(zip(ids[mask], a[mask].to_euclid())), detector)


@register_builtin_func()
def sketch(image: Capture) -> tuple[tuple[dts.Position, ...], ...]:
    if sketch_image is None:
        raise ValueError("Install linedraw")
    s = max(image.data.shape[:2])
    with contextlib.redirect_stdout(None):
        lines = sketch_image(Image.fromarray(image.data))
    strokes = tuple(tuple(dts.Position(x / s, y / s, 0) for (x, y) in line) for line in lines)
    return strokes


@register_builtin_func()
def zip_dataset(  # pylint: disable=too-many-positional-arguments
    name: str,
    info: str,
    calibration: dts.Pose,
    flange_poses: list[dts.Pose],
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
def get_mocked_pointcloud(number_points) -> PointCloud:
    points = cga3d.Vector.from_euclid(1000 * np.random.random((int(number_points), 3)))
    return PointCloud(points)


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
    trajectory = dts.MotionTrajectory.model_validate_json(json_string)
    context.action_queue._record[robot.configuration.identifier] = trajectory  # pylint: disable=protected-access
    if tcp_name is not None:
        context.action_queue._tcp[robot.configuration.identifier] = tcp_name  # pylint: disable=protected-access


@register_builtin_func()
def estimate_plane(
    origin: dts.Position, point_on_positive_x_axis: dts.Position, point_on_xy_plane: dts.Position
) -> dts.Pose:
    """
    Estimate the plane from three points

    Args:
        origin: the origin of the plane
        point_on_positive_x_axis: a point on the positive x-axis
        point_on_xy_plane: a point on the xy-plane with y>0

    Returns:
        Pose with the orientation of the plane
    """
    points = cga3d.Vector.stack(
        [
            cga3d.Vector.from_euclid(origin),
            cga3d.Vector.from_euclid(point_on_positive_x_axis),
            cga3d.Vector.from_euclid(point_on_xy_plane),
        ]
    )
    p = cga3d.Vector.stack(
        [cga3d.e_0, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_inf, cga3d.e_0 ^ cga3d.e_1 ^ cga3d.e_2 ^ cga3d.e_inf]
    )
    q = cga3d.Vector.stack(
        [
            points[0],
            (points[0] ^ points[1] ^ cga3d.e_inf).normed(),
            (points[0] ^ points[1] ^ points[2] ^ cga3d.e_inf).normed(),
        ]
    )
    m = cga3d.Vector.from_motor_estimation(p, q)
    return dts.Pose.from_versor(m)


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
def add_calibration_point(camera: CalibratableCamera, robot_pose: dts.Pose) -> bool:
    return camera.add_calibration_point(robot_pose.to_posetensor())


@register_builtin_func()
def reset_calibration(camera: CalibratableCamera) -> bool:
    return camera.reset_calibration()


@register_builtin_func()
def get_calibration_from_camera(camera: CalibratableCamera) -> dts.Pose:
    return dts.Pose.from_posetensor(camera.get_calibration())


@register_builtin_func()
def get_calibration_board_pose(camera: CalibratableCamera) -> dts.Pose:
    return dts.Pose.from_posetensor(camera.get_calibration_board_pose())
