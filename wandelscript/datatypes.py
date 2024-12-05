import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pyjectory import datatypes as dts
from pyjectory.visiontypes import FrameSystem

ElementType = TypeVar("ElementType", bound=dts.ElementType)


@dataclass(frozen=True)
class Frame:
    """A (physical) frame, i.e. coordinate system, in the space"""

    name: str
    system: FrameSystem = field(compare=False, hash=False)

    def __matmul__(self, other):
        assert False

    def __rmatmul__(self, other: dts.Pose):
        assert isinstance(other, dts.Pose)
        new_frame = Frame(uuid.uuid4().hex, self.system)
        self.system[self.name, new_frame.name] = other.to_versor()
        return new_frame


@dataclass(frozen=True)
class Closure(Generic[ElementType]):
    r"""A closure, i.e., an anonymous function together with a variable scope its implementation can refer to

    Example:
    >>> import asyncio
    >>> from wandelscript.metamodel import Store, Skill, run_skill
    >>> code = '''
    ... def foo():
    ...     def bar(u):
    ...         return 23
    ...     return bar
    ... b = foo()
    ... c = b(4)
    ... '''
    >>> context = asyncio.run(run_skill(code))
    >>> context.store['c']
    23
    """

    store: Any
    body: Callable[..., dts.ElementType]

    def __call__(self, store, *args) -> ElementType:
        return self.body(self.store, *args)

    def __matmul__(self, other):
        if isinstance(other, dts.Pose):

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
        assert isinstance(other, dts.Pose)

        async def function(store, *args):  # pylint: disable=unused-argument
            pose = await self.body(self.store, *args)
            return other @ pose

        return Closure(None, function)
