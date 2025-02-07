import pytest
from nova.core.robot_cell import RobotCell
from wandelscript.simulation import SimulatedRobot
from wandelscript.metamodel import Skill


@pytest.mark.skip("broken")
@pytest.mark.asyncio
async def test_stepwise():
    a = RobotCell(robot=SimulatedRobot())
    code = """
print("That")
print("is")
print("a")
print("test")
"""
    skill = Skill.from_code(code)
    steps = 0
    async for _ in skill.stepwise(a):
        steps += 1

    assert steps > 30
