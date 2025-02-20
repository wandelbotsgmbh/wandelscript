import pytest
from nova.core.robot_cell import RobotCell
from nova.types import Pose

import wandelscript
from wandelscript.simulation import SimulatedController, SimulatedRobot


@pytest.mark.skip(reason="TODO: Configurable robot required")
def test_two_step_execution():
    tools = {"TOOL1": Pose((0, 0, 0, 0, 0, 0)), "TOOL2": Pose((0, 0, 0, 0, 0, 0))}
    config = SimulatedRobot.Configuration(id="0@controller", tools=tools)
    controller = SimulatedController(SimulatedController.Configuration(robots=[config]))
    cell = RobotCell(controller=controller)
    code_step1 = """
tool2 = frame("TOOL2")

move tool2 via p2p() to (0, 0, 0, 0, 0, 0)
move tool2 via line() to (100, 0, 0, 0, 0, 0)
write(controller, "some_io", 1)
move tool2 via line() to (0, 0, 0, 0, 0, 0)

### path to json
json_path = motion_trajectory_to_json_string(controller[0])
"""
    runner1 = wandelscript.run(code_step1, cell)
    path_run1 = runner1.program_run.execution_results[0].paths[0]
    assert len(path_run1.poses) == 2

    code_step2 = """
motion_trajectory_from_json_string(controller[0], json_path, "TOOL2")
"""
    initial_store = {"json_path": runner1.execution_context.store["json_path"]}
    runner2 = wandelscript.run(code_step2, cell, default_robot="0@controller", initial_state=initial_store)
    path_run2 = runner2.program_run.execution_results[0].paths[0]
    assert len(path_run2.poses) == 2
