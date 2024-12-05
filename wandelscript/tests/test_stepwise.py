import pytest
from pyriphery.robotics import InMemoryDatabase, RobotCell, SimulatedRobot

from wandelscript.metamodel import Skill


@pytest.mark.asyncio
@pytest.mark.skip("broken")
async def test_stepwise():
    a = RobotCell(robot=SimulatedRobot(), database=InMemoryDatabase())
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
