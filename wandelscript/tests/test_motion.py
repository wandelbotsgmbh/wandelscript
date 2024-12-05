import numpy as np
import pytest
from pyjectory.datatypes import P2P, JointP2P, Linear, Pose
from pyjectory.pathtypes.vector3d import CircularSegment, Line, Point
from pyriphery.robotics import RobotCell, SimulatedController, SimulatedRobot, SimulatedRobotCell, get_robot_cell

import wandelscript
from wandelscript.exception import SkillRuntimeError
from wandelscript.metamodel import run_skill


def test_forbidden_tcp_change_in_one_motion_example():
    code = """
move via p2p() to (0, 0, 0, 0, 0, 0)
move frame("flange") to (1, 2, 0)
move frame("tool") to (2, 2, 0)
"""
    robot_configuration = SimulatedRobot.Configuration(
        identifier="0@controller",
        tools={"flange": Pose.from_tuple((0, 0, 0, 0, np.pi, 0)), "tool": Pose.from_tuple((2, 0, 0, 0, np.pi, 0))},
    )
    controller = SimulatedController(SimulatedController.Configuration(robots=[robot_configuration]))
    with pytest.raises(SkillRuntimeError):
        wandelscript.run(code, SimulatedRobotCell(controller=controller), default_robot="0@controller")


def test_simple_motion():
    code = """
move via p2p() to (0, 0, 10, 0, 0, 0)
move via line() to (0, 10, 10, 0, 0, 0)
"""
    cell = get_robot_cell()
    runner = wandelscript.run(code, cell, default_robot="0@controller", default_tcp="flange")
    path = runner.skill_run.execution_results[0].paths[0]
    # The first position will be at the origin because the simulated robot assumes it as the default initial position
    assert np.allclose(path.poses[0].pose.position, [0, 0, 0])
    assert np.allclose(path.poses[-1].pose.position, [0, 10, 10])


def test_no_robot():
    code = """print("hello world")"""
    wandelscript.run(code, RobotCell())


def test_motion_type_p2p_line():
    code = """
move via p2p() to (1, 0, 626, 0, 0, 0)
move via line() to (2, 0, 1111, 0, 0, 0)
move via p2p() to (3, 0, 626, 0, 0, 0)
sync
move via p2p() to (11, 0, 626, 0, 0, 0)
move via line() to (12, 0, 1111, 0, 0, 0)
sync
move via line() to (21, 0, 1111, 0, 0, 0)
move via p2p() to (23, 0, 626, 0, 0, 0)
"""
    expected_motion_types = [[P2P, Linear, P2P], [P2P, Linear], [Linear, P2P]]

    cell = get_robot_cell()
    runner = wandelscript.run(code, cell, default_tcp="flange")

    record_of_commands = runner.execution_context.robot_cell.get_robot("0@controller").record_of_commands

    assert len(record_of_commands) == 3

    for j, path in enumerate(record_of_commands):
        for i, motion in enumerate(path):
            assert isinstance(
                motion, expected_motion_types[j][i]
            ), f"The point has a wrong motion type - {expected_motion_types[j][i]=} == {type(motion)=}"


@pytest.mark.skip("JointP2P not supported by simulated robot")
def test_motion_type_joint_p2p():
    code = """
move via joint_p2p() to [1, 0, 626, 0, 0, 0]
move via line() to (2, 0, 1111, 0, 0, 0)
move via p2p() to (3, 0, 626, 0, 0, 0)
move via joint_p2p() to [4, 0, 626, 0, 0, 0]
move via joint_p2p() to [5, 0, 626, 0, 0, 0]
move via joint_p2p() to [6, 0, 626, 0, 0, 0]
sync
move via joint_p2p() to [11, 0, 626, 0, 0, 0]
move via line() to (12, 0, 1111, 0, 0, 0)
sync
move via line() to (21, 0, 1111, 0, 0, 0)
move via joint_p2p() to [23, 0, 626, 0, 0, 0]
sync
move via joint_p2p() to [31, 0, 626, 0, 0, 0]
"""
    expected_joint_values = [
        [(1, 0, 626, 0, 0, 0), None, None, (4, 0, 626, 0, 0, 0), (5, 0, 626, 0, 0, 0), (6, 0, 626, 0, 0, 0)],
        [
            # After a sync there will always first be a p2p motion added (this point has joints of a previous point)
            (6, 0, 626, 0, 0, 0),
            (11, 0, 626, 0, 0, 0),
            None,
        ],
        [
            # After a sync there will always first be a p2p motion added
            None,
            None,
            (23, 0, 626, 0, 0, 0),
        ],
        [
            # After a sync there will always first be a p2p motion added
            (23, 0, 626, 0, 0, 0),
            (31, 0, 626, 0, 0, 0),
        ],
    ]

    expected_motion_types = [
        [JointP2P, Linear, P2P, JointP2P, JointP2P, JointP2P],
        [
            # After a sync there will always first be a p2p motion added
            JointP2P,
            JointP2P,
            Linear,
        ],
        [
            # After a sync there will always first be a p2p motion added
            Linear,
            Linear,
            JointP2P,
        ],
        [
            # After a sync there will always first be a p2p motion added
            JointP2P,
            JointP2P,
        ],
    ]
    # Create a robot cell:
    cell = get_robot_cell()
    # Execute code:
    runner = wandelscript.run(code, cell)

    record_of_commands = runner.execution_context.robot_cell.get_robot("0@controller").record_of_commands

    assert len(record_of_commands) == 4

    for j, path in enumerate(record_of_commands):
        for i, motion in enumerate(path):
            # Check the motion type:
            assert isinstance(
                motion, expected_motion_types[j][i]
            ), f"The point has a wrong motion type - {expected_motion_types[j][i]=} == {type(path[i])=}"

            if isinstance(path[i], JointP2P):
                assert (
                    motion.target == expected_joint_values[j][i]
                ), f"The joint values don't match - {expected_joint_values[j][i]=} == {path[i].target=}"


@pytest.mark.skip("JointP2P not supported by simulated robot")
def test_joint_p2p_on_io_write():
    code = """
joints = read(controller[0], "joints")
print(joints)
move via joint_p2p() to joints
write(controller, "10010#0001", True)
move via joint_p2p() to joints
"""
    cell = get_robot_cell()
    runner = wandelscript.run(code, cell)
    print(runner.execution_context.store)

    path = runner.execution_context.robot_cell.robot.record_of_commands[0]
    assert path[1].callback is not None
    assert isinstance(path[1], JointP2P)


@pytest.mark.skip(
    "Maybe there is a bug in SequentialPosePath.partial and global_to_local_path_parameter in simulated robot"
)
@pytest.mark.asyncio
async def test_collapse_to_point():
    cell = get_robot_cell()
    code = """move via p2p() to (0, 0, 0, 0, 0, 0)
move via line() to (0, 0, 0, 0, pi, 0)"""

    result = await run_skill(code, cell, default_robot="0@controller")
    trajectory = result.robot_cell.get_robot("0@controller")._trajectory  # pylint: disable=protected-access
    assert isinstance(trajectory[0].position[-1], Point)
    assert isinstance(trajectory[1].position[-1], Line)


@pytest.mark.asyncio
async def test_bug_wos_1012():
    cell = get_robot_cell()
    code = """move via p2p() to (0, 0, 0, 0, pi, 0)
move via arc((1, 2, 3)) to  (3, 4, 5, 0, pi, 0)
sync
move via line() to (0, 0, 0, 0, pi, 0)"""

    result = await run_skill(code, cell, default_robot="0@controller", default_tcp="flange")
    trajectory = result.robot_cell.get_robot("0@controller")._trajectory  # pylint: disable=protected-access
    assert isinstance(trajectory[1].position[-1], CircularSegment)
    assert isinstance(trajectory[2].position[-1], Line)
