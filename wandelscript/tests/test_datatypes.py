import numpy as np
import pytest
from pyjectory.datatypes import Orientation, Pose, Position, as_builtin_type

from wandelscript.serializer import dumps, loads


def test_pose_to_and_from_tuple():
    pose = Pose(position=Position(1, 2, 3), orientation=Orientation(4, 5, 6))
    t = pose.to_tuple()
    assert t == (1, 2, 3, 4, 5, 6)
    p = Pose.from_tuple(t)
    assert pose == p


@pytest.mark.parametrize("concise", [True, False])
@pytest.mark.parametrize(
    "data",
    [
        Pose(position=Position(1.0, 2.0, 3.0), orientation=Orientation(4.0, 5.0, 6.0)),
        Position(1.0, 2.0, 3.0),
        Orientation(4.0, 5.0, 6.0),
        (1, "asd", 2.3, Position(1.0, 2.0, 3.0)),
    ],
)
def test_pose_save_and_load(data, concise):
    s = dumps(data, concise)
    print(data, s)
    data_reloaded = loads(s, concise)
    assert data_reloaded == data


def test_as_builtin_type():
    a = Pose.from_tuple((1, 2, 3, 0.1, 0.2, 0.3))
    assert np.allclose(a.to_tuple(), as_builtin_type(a).to_tuple())
    assert np.allclose(a.to_tuple(), as_builtin_type(a.to_versor()).to_tuple())
    assert np.allclose(a.to_tuple(), as_builtin_type(a.to_posetensor()).to_tuple())


@pytest.mark.parametrize("data", [True, False, 3, 4.6, "foo"])
def test_as_builtin_type_pass_through(data):
    assert data == as_builtin_type(data)
