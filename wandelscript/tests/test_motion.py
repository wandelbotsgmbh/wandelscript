import numpy as np
import pytest
from nova.actions.motions import PTP, JointPTP, Linear
from nova.core.robot_cell import RobotCell
from nova.types import Pose

import wandelscript
from wandelscript.exception import ProgramRuntimeError
from wandelscript.simulation import SimulatedController, SimulatedRobot, SimulatedRobotCell, get_robot_cell


def test_forbidden_tcp_change_in_one_motion_example():
    code = """
move via ptp() to (0, 0, 0, 0, 0, 0)
move frame("flange") to (1, 2, 0)
move frame("tool") to (2, 2, 0)
"""
    robot_configuration = SimulatedRobot.Configuration(
        id="0@controller", tools={"flange": Pose((0, 0, 0, 0, np.pi, 0)), "tool": Pose((2, 0, 0, 0, np.pi, 0))}
    )
    controller = SimulatedController(SimulatedController.Configuration(robots=[robot_configuration]))
    with pytest.raises(ProgramRuntimeError):
        wandelscript.run(code, SimulatedRobotCell(controller=controller), default_robot="0@controller")


def test_simple_motion():
    code = """
move via ptp() to (0, 0, 10, 0, 0, 0)
move via line() to (0, 10, 10, 0, 0, 0)
"""
    cell = get_robot_cell()
    runner = wandelscript.run(code, cell, default_robot="0@controller", default_tcp="flange")
    path = runner.program_run.execution_results[0].paths[0]
    # The first position will be at the origin because the simulated robot assumes it as the default initial position
    assert np.allclose(path.poses[0].pose.position, [0, 0, 0])
    assert np.allclose(path.poses[-1].pose.position, [0, 10, 10])


def test_no_robot():
    code = """print("hello world")"""
    wandelscript.run(code, RobotCell())


def test_motion_type_p2p_line():
    code = """
move via ptp() to (1, 0, 626, 0, 0, 0)
move via line() to (2, 0, 1111, 0, 0, 0)
move via ptp() to (3, 0, 626, 0, 0, 0)
sync
move via ptp() to (11, 0, 626, 0, 0, 0)
move via line() to (12, 0, 1111, 0, 0, 0)
sync
move via line() to (21, 0, 1111, 0, 0, 0)
move via ptp() to (23, 0, 626, 0, 0, 0)
"""
    expected_motion_types = [[PTP, Linear, PTP], [PTP, Linear], [Linear, PTP]]

    cell = get_robot_cell()
    runner = wandelscript.run(code, cell, default_tcp="flange")

    record_of_commands = runner.execution_context.robot_cell.get_robot("0@controller").record_of_commands

    assert len(record_of_commands) == 3

    for j, path in enumerate(record_of_commands):
        for i, motion in enumerate(path):
            assert isinstance(
                motion, expected_motion_types[j][i]
            ), f"The point has a wrong motion type - {expected_motion_types[j][i]=} == {type(motion)=}"


@pytest.mark.skip("JointPTP not supported by simulated robot")
def test_motion_type_joint_p2p():
    code = """
move via joint_p2p() to [1, 0, 626, 0, 0, 0]
move via line() to (2, 0, 1111, 0, 0, 0)
move via ptp() to (3, 0, 626, 0, 0, 0)
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
            # After a sync there will always first be a PTP motion added (this point has joints of a previous point)
            (6, 0, 626, 0, 0, 0),
            (11, 0, 626, 0, 0, 0),
            None,
        ],
        [
            # After a sync there will always first be a PTP motion added
            None,
            None,
            (23, 0, 626, 0, 0, 0),
        ],
        [
            # After a sync there will always first be a PTP motion added
            (23, 0, 626, 0, 0, 0),
            (31, 0, 626, 0, 0, 0),
        ],
    ]

    expected_motion_types = [
        [JointPTP, Linear, PTP, JointPTP, JointPTP, JointPTP],
        [
            # After a sync there will always first be a PTP motion added
            JointPTP,
            JointPTP,
            Linear,
        ],
        [
            # After a sync there will always first be a PTP motion added
            Linear,
            Linear,
            JointPTP,
        ],
        [
            # After a sync there will always first be a PTP motion added
            JointPTP,
            JointPTP,
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

            if isinstance(path[i], JointPTP):
                assert (
                    motion.target == expected_joint_values[j][i]
                ), f"The joint values don't match - {expected_joint_values[j][i]=} == {path[i].target=}"


@pytest.mark.skip("JointPTP not supported by simulated robot")
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
    assert isinstance(path[1], JointPTP)
