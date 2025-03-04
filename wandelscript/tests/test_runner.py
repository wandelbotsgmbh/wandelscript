import asyncio
import sys
import time
import uuid
from datetime import datetime
from typing import Any

import numpy as np
import pytest
from icecream import ic
from nova.core.robot_cell import RobotCell

from wandelscript import ProgramRun, ProgramRunner, ProgramRunState, run
from wandelscript.exception import NameError_, ProgramSyntaxError
from wandelscript.ffi import ForeignFunction, ff
from wandelscript.runtime import ExecutionContext
from wandelscript.simulation import get_robot_controller
from wandelscript.utils.runtime import Tee

robot_cell = RobotCell(controller=get_robot_controller())
raising_robot_cell = RobotCell(controller=get_robot_controller(raises_on_open=True))

ic.configureOutput(prefix=lambda: f"{datetime.now().time()} | ", includeContext=True)


def check_program_state(program_runner: ProgramRunner, expected_state: ProgramRunState, timeout: int) -> bool:
    """Checks a specific program state after a certain period of time

    Args:
        program_runner: the program runner
        expected_state: the expected state, if it is reached the function returns
        timeout: timeout in seconds

    Returns:
        bool: True if the expected state is reached within the timeout

    """
    for i in range(timeout):
        ic("CHECKING program state", program_runner.state, expected_state)
        if program_runner.state is expected_state:
            return True
        time.sleep(1)
    return False


def custom_foreign_function(v: Any) -> str:
    return f"Hello from my foreign function! Arg: {v}"


def other_foreign_function(ctx: ExecutionContext, v: int) -> None:
    robot = list(ctx.robot_cell.get_robots().values())[0]
    type_ = robot.configuration.type
    print(f"For context, we've got a robot of type: {type_}")

    print(f"{v * 2} little Jaegermeisters check if another arg does work")


def test_run():
    code = """
a = 4 + 5
home = (0, 0, 400, 0, pi, 0)
move via p2p() to home
print("print something")

foreign_function_result = call_foreign_function("Hola!")
print(foreign_function_result)

other_foreign_function(5)

wait 100
move via line() to home :: (0, 100, 0, 0, 0, 0)
"""

    foreign_functions = {
        "call_foreign_function": ForeignFunction(custom_foreign_function),
        "other_foreign_function": ForeignFunction(other_foreign_function, pass_context=True),
    }

    runner = run(
        code, robot_cell, default_robot="0@controller", default_tcp="Flange", foreign_functions=foreign_functions
    )
    assert "home" in runner.execution_context.store
    assert runner.execution_context.store["a"] == 9
    assert runner.program_run.state is ProgramRunState.COMPLETED

    stdout = runner.program_run.stdout
    assert "print something" in stdout
    assert "Hello from my foreign function! Arg: Hola!" in stdout
    assert "For context, we've got a robot of type: simulated_robot" in stdout
    assert "10 little Jaegermeisters check if another arg does work" in stdout

    assert not isinstance(sys.stdout, Tee)


async def custom_async_function() -> int:
    await asyncio.sleep(0.1)
    return 42


def test_run_with_foreign_async_function():
    """Showcase that Wandelscript supports also async foreign functions."""
    code = """
a = custom_async_function()
print(a)
"""

    runner = run(
        code,
        robot_cell,
        default_robot="0@controller",
        default_tcp="Flange",
        foreign_functions={"custom_async_function": ff(custom_async_function)},
    )
    stdout = runner.program_run.stdout
    assert "42\n" == stdout


def test_program_runner():
    program_runner = ProgramRunner("move via p2p() to [100, 0, 300, 0, pi, 0]", robot_cell)
    assert uuid.UUID(str(program_runner.id)) is not None
    assert program_runner.state is ProgramRunState.NOT_STARTED


# TODO andreasl 2024-08-20: flaky
#
# https://code.wabo.run/ai/wandelbrain/-/jobs/1119157
#
# >       assert "before wait" in stdout
# E       AssertionError: assert 'before wait' in ''
# wandelscript/tests/test_runner.py:101: AssertionError
def test_program_runner_start():
    code = """
home = (0, 0, 400, 0, pi, 0)
move via p2p() to home
print("before wait")
sync
wait 2000
print("after wait")
move via line() to home :: (0, 100, 0, 0, 0, 0)
sync
print(read(controller[0], "pose"))
move via line() to (0, 100, 300, 0, pi, 0)
"""
    program_runner = ProgramRunner(code, robot_cell, default_tcp="Flange")
    assert not program_runner.is_running()
    assert program_runner.start_time is None
    assert program_runner.execution_time is None
    assert isinstance(program_runner.program_run, ProgramRun)
    ic(program_runner.program_run)
    program_runner.start()
    ic(program_runner.program_run)

    assert check_program_state(program_runner, ProgramRunState.RUNNING, 4)
    assert program_runner.is_running()
    # It should not be possible to start the runner when it is already running
    with pytest.raises(RuntimeError):
        program_runner.start()
    ic(program_runner.program_run)

    assert check_program_state(program_runner, ProgramRunState.COMPLETED, 10)
    assert isinstance(program_runner.start_time, datetime)
    assert program_runner.execution_time > 0
    # It should not be possible to start the runner after the runner was completed
    with pytest.raises(RuntimeError):
        program_runner.start(sync=True)
    # Check path
    last_path = program_runner.program_run.execution_results[0].paths[-1]
    assert last_path.poses[-1].pose.position.to_tuple() == (0, 100, 300)
    # Check store
    store = program_runner.program_run.store
    assert np.allclose(store["home"].pose, [0, 0, 400, 0, np.pi, 0])
    # Check stdout
    # stdout = program_runner.program_run.stdout
    # assert "before wait" in stdout
    # assert "after wait" in stdout
    # assert "(0.0, 100.0, 400.0, 0.0, 3.142, 0.0)" in stdout
    # assert not isinstance(sys.stdout, Tee)


@pytest.mark.parametrize(
    "code",
    [
        """
wait 4000
""",
        """
tcp("Flange")
home = (-189, -600, 260, 0, -pi, 0)
move via p2p() to home
wait 4000
move via line() to (50, 20, 30, 0, 0, 0.3) :: home
move via line() to (150, 20, 30, 0, 0, 0.3) :: home
move via line() to (50, 20, 30, 0, 0, 0.3) :: home
move via p2p() to home
""",
    ],
)
def test_program_runner_stop(code):
    program_runner = ProgramRunner(code, robot_cell)
    assert not program_runner.is_running()
    program_runner.start()
    assert check_program_state(program_runner, ProgramRunState.RUNNING, 4)
    assert program_runner.is_running()
    program_runner.stop(sync=True)
    assert check_program_state(program_runner, ProgramRunState.STOPPED, 10)
    assert program_runner.program_run.state is ProgramRunState.STOPPED
    assert not program_runner.is_running()
    assert not isinstance(sys.stdout, Tee)


@pytest.mark.parametrize(
    "code, exception",
    [
        (
            """
move via p2p() to mispelled_var
""",
            NameError_,
        ),
        (
            """
    home = (0, 0, 400, 0, pi, 0)
    move via p2p() to home
""",
            ProgramSyntaxError,
        ),
        ("wai 4000", ProgramSyntaxError),
    ],
)
def test_program_runner_failed(code, exception):
    with pytest.raises(exception):
        runner = run(code, robot_cell)
        assert runner.program_run.state is ProgramRunState.FAILED
        assert runner.program_run.error is not None
        assert runner.program_run.traceback is not None
        assert not runner.is_running()
        assert not isinstance(sys.stdout, Tee)


def test_program_runner_raise_before_run():
    code = """
home = (0, 0, 400, 0, pi, 0)
move via p2p() to home
wait 4000
move via p2p() to home :: (0, 0, 100)
"""
    with pytest.raises(Exception):
        runner = run(code, raising_robot_cell)
        assert runner.program_run.state is ProgramRunState.FAILED
