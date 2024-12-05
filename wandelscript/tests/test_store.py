from pyjectory import datatypes as dts
from pyjectory import serializer

from wandelscript import Store


def test_store():
    store = Store(init_vars={"a": 1, "b": 2, "r": dts.Record(data={"x": 1, "y": 2})})
    assert store.data_dict == {"a": 1, "b": 2, "r": serializer.Record(record={"x": 1, "y": 2})}
