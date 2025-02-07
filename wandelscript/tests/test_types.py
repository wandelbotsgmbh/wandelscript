import numpy as np
import pytest
from nova.types import Pose, Vector3d

from wandelscript.serializer import dumps, loads
from wandelscript.types import as_builtin_type


def test_pose_to_and_from_tuple():
    pose = Pose((1, 2, 3, 4, 5, 6))
    t = pose.to_tuple()
    assert t == (1, 2, 3, 4, 5, 6)
    p = Pose(t)
    assert pose == p


@pytest.mark.parametrize("concise", [True, False])
@pytest.mark.parametrize(
    "data",
    [
        Pose((1, 2, 3, 4, 5, 6)),
        Vector3d.from_tuple((1.0, 2.0, 3.0)),
        Vector3d.from_tuple((4.0, 5.0, 6.0)),
        (1, "asd", 2.3, Vector3d.from_tuple((1.0, 2.0, 3.0))),
    ],
)
def test_pose_save_and_load(data, concise):
    s = dumps(data, concise)
    print(data, s)
    data_reloaded = loads(s, concise)
    assert data_reloaded == data


def test_as_builtin_type():
    a = Pose((1, 2, 3, 0.1, 0.2, 0.3))
    assert np.allclose(a.to_tuple(), as_builtin_type(a).to_tuple())


@pytest.mark.parametrize("data", [True, False, 3, 4.6, "foo"])
def test_as_builtin_type_pass_through(data):
    assert data == as_builtin_type(data)
