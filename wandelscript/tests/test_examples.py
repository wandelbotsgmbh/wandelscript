import tempfile

from wandelscript.types import Record
import numpy as np
import pytest
from loguru import logger
from nova.types import Pose, Vector3d
from nova.core.robot_cell import RobotCell
from wandelscript.simulation import SimulatedRobotCell

import wandelscript
from wandelscript.examples import EXAMPLES


def _check_record(a: Record, b: Record, keypath=""):
    for k, v in a.items():
        # For the test we may not want to check every key in the record e.g. sender IP
        if k not in b:
            logger.warning(f"Key {k} not found in b")
            continue
        if isinstance(v, Record):
            _check_record(v, b[k], f"{keypath}.{k}")
            continue
        assert v == b[k], f"{keypath}.{k}"


@pytest.mark.parametrize("example_name", EXAMPLES)
def test_example(example_name):
    # TODO: https://wandelbots.atlassian.net/browse/WP-683
    if example_name in ("spline", "interrupt"):
        return
    logger.info(f"Running example {example_name}...")
    code, data, config = EXAMPLES[example_name]
    robot_cell = RobotCell.from_dict(config)
    runner = wandelscript.run(code, robot_cell, default_tcp="flange")
    store = runner.execution_context.store
    for key, expected in data.items():
        if isinstance(expected, list):
            expected = tuple(tuple(v) if isinstance(v, list) else v for v in expected)
        if isinstance(expected, Pose):
            assert np.allclose(expected.position, store[key].position, atol=1e-3, rtol=1e-3)
            assert np.allclose(expected.orientation, store[key].orientation, atol=1e-3, rtol=1e-3)
        elif isinstance(expected, (Vector3d, Vector3d)):
            assert np.allclose(expected, store[key], atol=1e-3, rtol=1e-3)
        elif isinstance(expected, Record):
            _check_record(expected, store[key])
        else:
            assert expected == store[key], f"{key=}: got: {store[key]} expected: {expected}"


def test_save_and_load():
    with tempfile.TemporaryDirectory() as tempdir:
        code = f"""
a = (1, 2, 3, 4, 5, 6)
save(a, '{tempdir}/test.ws')
b = load('{tempdir}/test.ws', 'pose')
"""
        runner = wandelscript.run(code, SimulatedRobotCell())
        print(runner.execution_context.store["b"])
