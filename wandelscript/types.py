"""Types and constructs for internal use."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
import json
from functools import singledispatch
from typing import Any, Callable, Generic, TypeVar, Union

import numpy as np
import pydantic
from nova.types import Pose, Vector3d

from wandelscript.frames import FrameSystem
from wandelscript.utils.pose import pose_to_versor


# All types that can be used within Wandelscript
ElementType = Union[float, int, bool, str, bytes, tuple, list, dict, Pose, Vector3d]
BoundedElementType = TypeVar("BoundedElementType", bound=ElementType)


@singledispatch
def encode(obj):
    """Encodes an object to a pydantic model

    Args:
        obj: the object to encode

    Returns: the pydantic model

    Examples:
    >>> encode(Pose((1, 2, 3, 4, 5, 6)))
    Pose(position=Vector3d(x=1, y=2, z=3), orientation=Vector3d(x=4, y=5, z=6))
    >>> encode(Vector3d(x=1, y=2, z=3))
    Vector3d(x=1, y=2, z=3)
    >>> encode([1, 2, 3])
    [1, 2, 3]
    >>> encode([["a", {"b": 2}], 2, 3])
    [['a', {'b': 2}], 2, 3]
    >>> encode((1, 2, 3))
    (1, 2, 3)
    >>> encode("Hello, World!")
    'Hello, World!'
    """
    raise NotImplementedError(type(obj))


@singledispatch
def decode(obj):
    """Decodes a pydantic model to an object

    Args:
        obj: the pydantic model to decode

    Returns: the object

    Examples:
    >>> decode(Pose((1, 2, 3, 4, 5, 6)))
    Pose(position=Vector3d(x=1, y=2, z=3), orientation=Vector3d(x=4, y=5, z=6))
    >>> decode(Vector3d(x=1, y=2, z=3))
    Vector3d(x=1, y=2, z=3)
    >>> decode({ "id": "id1", "state": "stopped", "data": { "a": 1, "b": 2 } })
    {'id': 'id1', 'state': 'stopped', 'data': {'a': 1, 'b': 2}}
    >>> decode([{ "id": "id1", "state": "stopped"}, {"id": "id2", "state": "running"}])
    [{'id': 'id1', 'state': 'stopped'}, {'id': 'id2', 'state': 'running'}]
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


@encode.register
def _(obj: list):
    return list(map(encode, obj))


@encode.register
def _(obj: tuple):
    return tuple(map(encode, obj))


@decode.register
def _(obj: tuple):
    return tuple(map(decode, obj))


@decode.register
def _(obj: list):
    return list(map(decode, obj))


@decode.register
def _(obj: int):
    return obj


@decode.register
def _(obj: float):
    return obj


@decode.register
def _(obj: str):
    return obj


@encode.register
def _(obj: Pose):
    return obj


@decode.register
def _(obj: Pose):
    return obj

@encode.register
def _(obj: Vector3d):
    return obj


@decode.register
def _(obj: Vector3d):
    return obj

@encode.register
def _(obj: dict):
    return obj


@decode.register
def _(obj: dict):
    # If it has the signature of a Pose, decode it as a Pose:
    if "position" in obj and "orientation" in obj:
        return Pose(**obj)
    if "x" in obj and "y" in obj and "z" in obj:
        return Vector3d(**obj)
    # Otherwise just decode children (if needed) or leave it alone:
    return {k: decode(v) for k, v in obj.items()}


def encode_as_json_like_dict(data: ElementType):
    return Element(value=encode(data)).model_dump()["value"]


def dumps(data: ElementType) -> str:
    return Element(value=encode(data)).model_dump_json()


def loads(s: str) -> ElementType:
    data = json.loads(s)
    return decode(Element(**data))


def loads_store(content: str) -> ElementType:
    """
    Example:
    >>> json_content = '{"a": {"orientation": [1.0, 2.0, 3.0], "position": [4.0, 5.0, 6.0]}}'
    >>> loads_store(json_content)
    {'a': Pose(position=Vector3d(x=4.0, y=5.0, z=6.0), orientation=Vector3d(x=1.0, y=2.0, z=3.0))}
    >>> json_content = '{"b": {"a": 3}, "c": [1, 2, 3]}'
    >>> loads_store(json_content)
    {'b': {'a': 3}, 'c': [1, 2, 3]}
    """
    data = json.loads(content)
    return decode(Store(items=data))


__all__ = ["Frame", "Closure", "as_builtin_type", "ElementType", "loads_store", "dumps", "loads"]
