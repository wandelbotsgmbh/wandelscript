# pylint: disable=protected-access
"""Test the execution of sample skills"""

import anyio
import pyjectory.pathtypes.pose as posepath
import pytest
from pyjectory import datatypes as dts
from pyjectory.pathtypes import Vector3dPath
from pyjectory.pathtypes.cga3d.segment import MultiVectorChain, continuous_path

from wandelscript.metamodel import Connector, run_skill

CODE_FUNC_DEF = """
move via p2p() to (home=(0, 0.1, 0, 0, 0, 0))
movedef circle(start >--> end):
    move via arc(start :: (0.2, 0.2, 0)) to start :: (0, 0.4, 0)
    print('action')
    move via arc(start :: (-0.2, 0.2, 0)) to start :: (0, 0, 0)
move via line() to (-1.2, 0, 0)
move via circle() to (0, 0, 0)
move via line() to (1, 0, 0)
move via circle() to (0, 0, 0)
move via line() to home
"""

CODE_SAMPLES = {
    "arc_move": "move via p2p() to (0, 0, 0, 0, 0, 0)\nmove via arc((0, 2, 0)) to (1, 1, 0)\n",
    "movedef": CODE_FUNC_DEF,
}


class Curve(Connector.Impl, func_name="arc_spline"):
    class Args(list):
        def __init__(self, *args: dts.Vector):
            super().__init__(args)

    def __call__(
        self, start: dts.Pose, end: dts.Pose, args: Args, motion_settings: dts.MotionSettings
    ) -> posepath.PosePath:
        start = start.to_posetensor()
        end = end.to_posetensor()
        args_as_points = [posepath.Vector3d(a) for a in args]
        position = Vector3dPath.from_segment_path(
            continuous_path(MultiVectorChain.from_euclid([start.position, *args_as_points, end.position]))
        )
        return posepath.SequentialPosePath(
            [
                posepath.ComposedPosePath(position=p, orientation=posepath.Slerp(start.orientation, start.orientation))
                for p in position.flatted()
            ]
        )


@pytest.mark.parametrize("sample_code_key", CODE_SAMPLES)
def test_execution(sample_code_key):
    sample_code = CODE_SAMPLES[sample_code_key]

    async def f():
        await run_skill(sample_code, default_robot="0@controller", default_tcp="flange")

    anyio.run(f)
