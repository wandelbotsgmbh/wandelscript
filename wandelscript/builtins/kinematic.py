from pyjectory import datatypes as dts
from pyriphery.pyrae import Robot as MotionGroup

from wandelscript.metamodel import register_builtin_func


@register_builtin_func()
async def solve_point_forward(motion_group: MotionGroup, joints: list[float], tcp: str) -> dts.Pose:
    """Returns the pose of the robot based on the joint positions and TCP

    Args:
        motion_group (MotionGroup): The motion group for which the pose is calculated
        joints (list[float]): The joint positions for which the pose is calculated
        tcp (str): The tool center point name (e.g., "Flange")

    Returns:
        The calculated pose of the robot

    """
    rae_pose = await motion_group._kinematic_service_client.calculate_tcp_pose(  # pylint: disable=protected-access
        motion_group.motion_group_id, joints, tcp
    )
    pos = rae_pose.position
    ori = rae_pose.orientation

    return dts.Pose.from_tuple((pos.x, pos.y, pos.z, ori.x, ori.y, ori.z))


@register_builtin_func()
async def solve_point_inverse(
    motion_group: MotionGroup, pose: dts.Pose, tcp: str, reference_joints: list[float]
) -> list[float]:
    """Returns the joint positions of the robot based on the pose and TCP

    Args:
        motion_group (MotionGroup): The motion group for which the joints are calculated
        pose (Pose): The pose for which the joint positions are calculated
        tcp (str): The tool center point name (e.g., "Flange")
        reference_joints (list[float]): The reference joints

    Returns:
        The calculated joint positions of the robot

    """
    joints = await motion_group._kinematic_service_client.calculate_joint_position(  # pylint: disable=protected-access
        motion_group.motion_group_id, pose, tcp, tuple(reference_joints)
    )
    return joints.joints
