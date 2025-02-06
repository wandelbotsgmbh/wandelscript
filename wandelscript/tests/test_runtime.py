import pytest
from pyriphery.robotics.simulation import SimulatedController, SimulatedRobotCell, get_simulated_robot_configs

from wandelscript import exception as wsexception
from wandelscript.exception import NameError_
from wandelscript.metamodel import register_debug_func, run_skill
from wandelscript.runner import run


@pytest.mark.asyncio
async def test_runtime_error():
    code = "a = 1\na = b"
    with pytest.raises(NameError_) as error:
        await run_skill(code)
    assert error.value.location.start.line == 2
    assert error.value.location.start.column == 4


def test_debug():
    test_a = None

    @register_debug_func
    def debug(context):
        nonlocal test_a
        test_a = context.store.data["a"]
        # Also the buffered path can be accessed via
        # print(store.environment._record)

    code = """
a = 1
b = 2
move via p2p() to (1, 2, 3, 4, 5, 6)
move via line() to (1, 0, 0, 1, 1, 1)
debug()
"""

    robot_cell = SimulatedRobotCell()
    run(code, robot_cell, default_robot="0@controller", default_tcp="flange")
    assert test_a == 1


@pytest.mark.parametrize(
    "code, num_robots, expected_exception",
    [
        (
            """
move via p2p() to (1, 2, 3, 4, 5, 6)
""",
            1,
            None,
        ),
        (
            """
move via p2p() to (1, 2, 3, 4, 5, 6)
""",
            2,
            wsexception.WrongRobotError,
        ),
        (
            """
move via p2p() to (1, 2, 3, 4, 5, 6)
do with controller[0]:
    move via p2p() to (1, 2, 3, 4, 5, 6)
""",
            1,
            None,
        ),
        (
            """
move via p2p() to (1, 2, 3, 4, 5, 6)
do with controller[0]:
    move via p2p() to (1, 2, 3, 4, 5, 6)
""",
            2,
            wsexception.WrongRobotError,
        ),
    ],
    ids=["top_level_one_robot", "top_level_multi_robot", "robot_context_one_robot", "robot_context_multi_robot"],
)
def test_robot_code_execution(code, num_robots, expected_exception):
    robot_cell = SimulatedRobotCell(
        controller=SimulatedController(
            SimulatedController.Configuration(robots=get_simulated_robot_configs(num_robots=num_robots))
        )
    )
    if expected_exception:
        with pytest.raises(expected_exception):
            run(code, robot_cell, default_tcp="flange")
    else:
        result = run(code, robot_cell, default_tcp="flange")
        assert result is not None
