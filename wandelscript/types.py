"""Types and constructs for internal use."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from functools import singledispatch
from typing import Any, Callable, Generic, Mapping, TypeVar, Union

import numpy as np
import pydantic
from nova.types import Pose, Vector3d

from wandelscript.frames import FrameSystem
from wandelscript.utils.pose import pose_to_versor


class Record(pydantic.BaseModel, Mapping):
    """A record that stores key-value pairs"""

    model_config = pydantic.ConfigDict(frozen=True)

    data: dict[str, ElementType] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, ElementType]) -> Record:
        return Record(
            data={key: Record.from_dict(value) if isinstance(value, dict) else value for key, value in d.items()}
        )

    def to_dict(self):
        return {key: value.to_dict() if isinstance(value, Record) else value for key, value in self.data.items()}

    def get(self, key: str, *args, **kwargs):
        return self.data.get(key, *args, **kwargs)

    # Support bracket notation: r['a']
    def __getitem__(self, key: str) -> ElementType:
        return self.data[key]

    # Support dot notation: r.a
    def __getattr__(self, key: str) -> ElementType:
        if key in self.data:
            return self.data[key]
        raise AttributeError(f"Record has no attribute '{key}'")

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def items(self):
        return self.data.items()


# All types that can be used within Wandelscript
ElementType = Union[bool, int, float, Vector3d, Pose, str, Record, tuple, dict]
BoundedElementType = TypeVar("BoundedElementType", bound=ElementType)


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


"""
@as_builtin_type.register
def _(data: Capture):
    return data


@as_builtin_type.register
def _(data: Features):
    return data


@as_builtin_type.register
def _(data: PointCloud):
    return data
"""
