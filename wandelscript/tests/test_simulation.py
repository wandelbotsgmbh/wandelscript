from wandelscript.simulation import SimulatedRobot
from wandelscript.types import Pose


def test_simulated_robot():
    robot = SimulatedRobot(
        configuration=SimulatedRobot.Configuration(
            type="simulated_robot", identifier="simulated_robot", initial_pose=Pose(100, 0, 0, 0, 0, 0)
        )
    )
    assert robot.configuration.type == "simulated_robot"
