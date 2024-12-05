from functools import singledispatch
from typing import Any, TypeVar

from pyjectory import datatypes as dts

from wandelscript.metamodel import register_builtin_func

# TODO naming. updated, updating
# TODO make a more generic version of the function
# TODO what about the type safety of the val
T = TypeVar("T")


@register_builtin_func()
@singledispatch
def assoc(_: T, key: int, val: Any) -> T:
    """Update the value at the given key in a sequence."""
    raise NotImplementedError(f"assoc is not defined for {type(_)}.")


@assoc.register
def _(vec: dts.Vector, key: int, val: float) -> dts.Vector:
    tmp = list(vec)
    tmp[key] = val
    return vec.__class__(*tmp)


@assoc.register
def _(pose: dts.Pose, key: int, val: float) -> dts.Pose:
    tmp = list(pose.to_tuple())
    tmp[key] = val
    return dts.Pose.from_tuple(tmp)


# TODO: In the future we want to improve record manipulation. For example we could use frozen keyword like:
# frozen rec_frozen = { a: 1, b: 2 }
# rec = { a: 2, b: 3 }
# rec_frozen.a = 4 # throws error
# rec.a = 4 # works
@assoc.register
def _(record: dts.Record, key: str, val: Any) -> dts.Record:
    tmp = dict(record)
    tmp[key] = val
    return dts.Record(data=tmp)
