import asyncio

import numpy as np
import pytest
from pyjectory.datatypes import MS, MotionTrajectory, lin, p2p

from wandelscript.metamodel import run_skill


@pytest.mark.parametrize(
    "code, expected",
    [
        (
            """
velocity(200)
tcp = frame("flange")
move tcp via p2p() to (150, -355, 389, 0, pi, 0)
move tcp via line() to (150, -355, 392, 0, pi, 0) with velocity(10)
move tcp via p2p() to (150, -355, 389, 0, pi, 0)
move tcp via line() to (-95, -363, 387, 0, pi, 0) with velocity(250)
move tcp via p2p() to (150, -355, 389, 0, pi, 0)
""",
            [
                MotionTrajectory(
                    items=(
                        p2p((150, -355, 389), MS(velocity=200)),
                        lin((150, -355, 392), MS(velocity=10)),
                        p2p((150, -355, 389), MS(velocity=200)),
                        lin((-95, -363, 387), MS(velocity=250)),
                        p2p((150, -355, 389), MS(velocity=200)),
                    )
                )
            ],
        ),
        (
            """
velocity(200)
move via p2p() to (150, -355, 389, 0, pi, 0)
move via line() to (150, -355, 392, 0, pi, 0) with velocity(10)
move via p2p() to (150, -355, 389, 0, pi, 0)
move via line() to (-95, -363, 387) with velocity(250)
move via p2p() to (150, -355, 389, 0, pi, 0)
""",
            [
                MotionTrajectory(
                    items=(
                        p2p((150, -355, 389), MS(velocity=200)),
                        lin((150, -355, 392), MS(velocity=10)),
                        p2p((150, -355, 389), MS(velocity=200)),
                        lin((-95, -363, 387), MS(velocity=250)),
                        p2p((150, -355, 389), MS(velocity=200)),
                    )
                )
            ],
        ),
        (
            """
move via p2p() to (150, -355, 389, 0, pi, 0)
move via line() to (150, -355, 392, 0, pi, 0) with blending(2)
move via p2p() to (150, -355, 389, 0, pi, 0) with velocity(100)
move via line() to (-95, -363, 387) with blending(4)
move via p2p() to (150, -355, 389, 0, pi, 0)
""",
            [
                MotionTrajectory(
                    items=(
                        p2p((150, -355, 389), MS(velocity=None)),
                        lin((150, -355, 392), MS(blending=2)),
                        p2p((150, -355, 389), MS(velocity=100)),
                        lin((-95, -363, 387), MS(blending=4)),
                        p2p((150, -355, 389), MS(velocity=None)),
                    )
                )
            ],
        ),
    ],
    ids=["with_tcp", "with_velocity", "with_blending"],
)
def test_move(code, expected):
    context = asyncio.run(run_skill(code, default_robot="0@controller", default_tcp="flange"))
    paths = context.action_queue._path_history  # pylint: disable=protected-access

    for path, expected_path in zip(paths, expected):
        assert len(path.motions) == len(expected_path.motions)
        for motion, expected_motion in zip(path.motions, expected_path.motions):
            target_np = np.array(motion.target) if isinstance(motion.target, tuple) else motion.target.position
            expected_target_np = (
                np.array(expected_motion.target)
                if isinstance(expected_motion.target, tuple)
                else expected_motion.target.position
            )

            assert np.allclose(target_np, expected_target_np)
            assert motion.settings == expected_motion.settings
            assert motion.type == expected_motion.type
