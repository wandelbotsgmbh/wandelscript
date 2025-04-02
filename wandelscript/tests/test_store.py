from wandelscript import Store
from wandelscript.types import Record


def test_store():
    store = Store(init_vars={"a": 1, "b": 2, "r": Record(data={"x": 1, "y": 2})})
    assert store.data_dict == {"a": 1, "b": 2, "r": Record(record={"x": 1, "y": 2})}
