import sys
from datetime import datetime

from icecream import ic
from pyriphery.robotics import SimulatedRobotCell, get_robot_controller

from wandelscript import ProgramRunState, run
from wandelscript.utils import Tee

robot_cell = SimulatedRobotCell(controller=get_robot_controller())

ic.configureOutput(prefix=lambda: f"{datetime.now().time()} | ", includeContext=True)


def test_run_code_twice():
    code = """
a = 4 + 5
move via p2p() to (0, 0, 400, 0, pi, 0)
print("print something")
move via line() to (0, 100, 400, 0, pi, 0)
"""
    for i in range(2):
        runner = run(code, robot_cell, default_tcp="flange")
        assert runner.execution_context.store["a"] == 9
        assert runner.skill_run.state is ProgramRunState.COMPLETED
        assert "print something" in runner.skill_run.logs
        assert not isinstance(sys.stdout, Tee)
