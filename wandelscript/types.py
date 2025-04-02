"""Types and constructs for internal use."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
import json
from functools import singledispatch
from typing import Any, Callable, Generic, Mapping, TypeVar, Union

import numpy as np
import pydantic
from nova.types import Pose, Vector3d

from wandelscript.frames import FrameSystem
from wandelscript.utils.pose import pose_to_versor


# All types that can be used within Wandelscript
FlatElementType = Union[float, int, bool, str, bytes, Pose, Vector3d]
BoundedElementType = TypeVar("BoundedElementType", bound=FlatElementType)


@singledispatch
def encode(obj):
    """Encodes an object to a pydantic model

    Args:
        obj: the object to encode

    Returns: the pydantic model

    Examples:
    >>> encode(Pose((1, 2, 3, 4, 5, 6)))
    Pose(pose=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0))
    >>> encode(Vector3d(x=1, y=2, z=3))
    Vector3d(vector3d=(1.0, 2.0, 3.0))
    """
    raise NotImplementedError(type(obj))


@singledispatch
def decode(obj):
    """Decodes a pydantic model to an object

    Args:
        obj: the pydantic model to decode

    Returns: the object

    Examples:
    >>> decode(Pose(pose=(1, 2, 3, 4, 5, 6)))
    Pose(position=Vector3d(x=1.0, y=2.0, z=3.0), orientation=Vector3d(x=4.0, y=5.0, z=6.0))
    >>> decode(Vector3d(vector3d=(1, 2, 3)))
    Vector3d(x=1.0, y=2.0, z=3.0)
    >>> decode({ "id": "id1", "state": "stopped", "data": { "a": 1, "b": 2 } })
    Record(data={'id': 'id1', 'state': 'stopped', 'data': Record(data={'a': 1, 'b': 2})})
    >>> decode([{ "id": "id1", "state": "stopped"}, {"id": "id2", "state": "running"}])
    (Record(data={'id': 'id1', 'state': 'stopped'}), Record(data={'id': 'id2', 'state': 'running'}))
    >>> decode("Hello, World!")
    'Hello, World!'
    >>> decode(42)
    42
    """
    raise NotImplementedError(type(obj))


@dataclass(frozen=True)
class Frame:
    """A (physical) frame, i.e. coordinate system, in the space"""

    name: str
    system: FrameSystem = field(compare=False, hash=False)

    def __matmul__(self, other):
        assert False

    def __rmatmul__(self, other: Pose):
        assert isinstance(other, Pose)
        new_frame = Frame(uuid.uuid4().hex, self.system)
        self.system[self.name, new_frame.name] = pose_to_versor(other)
        return new_frame


@dataclass(frozen=True)
class Closure(Generic[BoundedElementType]):
    r"""A closure, i.e., an anonymous function together with a variable scope its implementation can refer to

    Example:
    >>> import asyncio
    >>> from wandelscript.metamodel import run_program
    >>> code = '''
    ... def foo():
    ...     def bar(u):
    ...         return 23
    ...     return bar
    ... b = foo()
    ... c = b(4)
    ... '''
    >>> context = asyncio.run(run_program(code))
    >>> context.store['c']
    23
    """

    store: Any
    body: Callable[..., ElementType]

    def __call__(self, store, *args) -> ElementType:
        return self.body(self.store, *args)

    def __matmul__(self, other):
        if isinstance(other, Pose):

            async def function(store, *args):  # pylint: disable=unused-argument
                pose = await self.body(self.store, *args)
                return pose @ other

            return Closure(self.store, function)
        if isinstance(other, Closure):

            async def function(store, *args):  # pylint: disable=unused-argument, function-redefined
                a = await self.body(self.store, *args)
                b = await other.body(other.store, *args)
                return a @ b

            return Closure(self.store, function)
        return NotImplemented

    def __rmatmul__(self, other):
        assert isinstance(other, Pose)

        async def function(store, *args):  # pylint: disable=unused-argument
            pose = await self.body(self.store, *args)
            return other @ pose

        return Closure(None, function)


@singledispatch
def as_builtin_type(data: Any) -> ElementType:
    raise TypeError(f"Datatype is not supported {type(data)}")


@as_builtin_type.register
def _(data: bool):
    return data


@as_builtin_type.register
def _(data: tuple):
    return data


@as_builtin_type.register
def _(data: float):
    return data


@as_builtin_type.register
def _(data: int):
    return data


@as_builtin_type.register
def _(data: np.float64):
    return float(data)


@as_builtin_type.register
def _(data: str):
    return data


@as_builtin_type.register
def _(data: Pose):
    return data


class Record(pydantic.BaseModel, Mapping):
    """A record that stores key-value pairs"""

    model_config = pydantic.ConfigDict(frozen=True)

    type: str = "record"
    record: dict[str, ElementType] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, ElementType]) -> Record:
        return Record(
            record={key: Record.from_dict(value) if isinstance(value, dict) else value for key, value in d.items()}
        )

    def to_dict(self):
        return {key: value.to_dict() if isinstance(value, Record) else value for key, value in self.data.items()}

    def get(self, key: str, *args, **kwargs):
        return self.record.get(key, *args, **kwargs)

    # Support bracket notation: r['a']
    def __getitem__(self, key: str) -> ElementType:
        return self.record[key]

    # Support dot notation: r.a
    def __getattr__(self, key: str) -> ElementType:
        if key in self.record:
            return self.record[key]
        raise AttributeError(f"Record has no attribute '{key}'")

    def __iter__(self):
        return iter(self.record)

    def __len__(self):
        return len(self.record)

    def items(self):
        return self.record.items()


class Array(pydantic.BaseModel):
    """A list of elements"""

    model_config = pydantic.ConfigDict(frozen=True)

    type: str = "array"
    array: list[Union[FlatElementType, "Array", "Record"]]

    def to_list(self):
        return [value.to_list() if isinstance(value, Array) else value for value in self.array]

    def __getitem__(self, key: int) -> FlatElementType:
        return self.array[key]

    def __len__(self):
        return len(self.array)

    def items(self):
        return enumerate(self.array)


@encode.register(dict)
def _(obj: dict) -> Record:
    return Record(record={k: encode(v) for k, v in obj.items()})


@encode.register(Record)
def _(obj: Record) -> Record:
    return obj


@decode.register
def _(obj: Record) -> Record:
    return obj


@decode.register
def _(obj: dict) -> Record:
    return Record(record={k: decode(v) for k, v in obj.items()})


# Necessary to resolve forward references using the new Pydantic v2 method
Array.model_rebuild()
Record.model_rebuild()

ElementType = Union[FlatElementType, Array, Record]


class Element(pydantic.BaseModel):
    value: ElementType


class Store(pydantic.BaseModel):
    items: dict[str, ElementType]


@encode.register
def _(obj: Element):
    return obj


@decode.register
def _(obj: Element):
    return decode(obj.value)


@decode.register
def _(obj: Store):
    return {k: decode(v) for k, v in obj.items.items()}


@encode.register
def _(obj: int):
    return obj


@encode.register
def _(obj: float):
    return obj


@encode.register
def _(obj: str):
    return obj


@encode.register
def _(obj: None):
    return obj


@decode.register
def _(obj: list):
    return tuple(map(decode, obj))


@decode.register
def _(obj: int):
    return obj


@decode.register
def _(obj: float):
    return obj


@decode.register
def _(obj: str):
    return obj


def encode_as_json_like_dict(data: ElementType):
    return Element(value=encode(data)).model_dump()["value"]


def dumps(data: ElementType, concise=False) -> str:
    if concise:
        return json.dumps(encode_as_json_like_dict(data))
    return Element(value=encode(data)).model_dump_json()


def loads(s: str, concise=False) -> ElementType:
    data = json.loads(s)
    if concise:
        data = {"value": data}
    return decode(Element(**data))


def loads_store(content: str) -> ElementType:
    data = json.loads(content)
    return decode(Store(items=data))


__all__ = ["Frame", "Closure", "as_builtin_type", "Record", "Array", "ElementType", "loads_store"]
