"""Types and constructs for internal use."""
from typing import Any, Mapping, Union

import numpy as np
import pydantic
from nova.types import Pose, Vector3d


class Orientation(Vector3d):
    """An orientation (given as rotation vector)"""

    def as_quaternion(self):
        values = np.asarray(self)
        half_angle = np.linalg.norm(values) / 2
        return np.concatenate([np.cos(half_angle)[None], values * np.sinc(half_angle / np.pi) / 2])


class Position(Vector3d):
    """A position

    Example:
    >>> a = Position(10, 20, 30)
    >>> b = Position(1, 1, 1)
    >>> a + b == Position(11, 21, 31)
    True
    >>> a - b == Position(9, 19, 29)
    True
    """

    def __add__(self, other: Any) -> "Position":
        if not isinstance(other, Position):
            return NotImplemented
        return Position(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Any) -> "Position":
        if not isinstance(other, Position):
            return NotImplemented
        return Position(self.x - other.x, self.y - other.y, self.z - other.z)

    # TODO
    # def __rmatmul__(self, other) -> "Position":
    #     if not isinstance(other, Pose):
    #         return NotImplemented
    #     versor = other.to_versor()
    #     point = cga3d.Vector.from_euclid(list(self))
    #     return Position(*versor.apply(point).to_euclid())

    # TODO``
    # def as_multivector(self) -> cga3d.Vector:
    #     return cga3d.Vector.from_euclid(list(self))

    # TODO
    # @classmethod
    # def from_multivector(cls, vector: cga3d.Vector) -> Position:
    #     return cls(*vector.to_euclid())


class Record(pydantic.BaseModel, Mapping):
    """A record that stores key-value pairs"""

    model_config = pydantic.ConfigDict(frozen=True)

    data: dict[str, "ElementType"] = {}

    @staticmethod
    def from_dict(d: dict[str, "ElementType"]) -> "Record":
        return Record(
            data={key: Record.from_dict(value) if isinstance(value, dict) else value for key, value in d.items()}
        )

    def to_dict(self):
        return {key: value.to_dict() if isinstance(value, Record) else value for key, value in self.data.items()}

    def get(self, key: str, *args, **kwargs):
        return self.data.get(key, *args, **kwargs)

    # Support bracket notation: r['a']
    def __getitem__(self, key: str) -> "ElementType":
        return self.data[key]

    # Support dot notation: r.a
    def __getattr__(self, key: str) -> "ElementType":
        if key in self.data:
            return self.data[key]
        raise AttributeError(f"Record has no attribute '{key}'")

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def items(self):
        return self.data.items()


ElementType = Union[bool, int, float, Vector3d, Position, Orientation, Pose, str, Record, tuple, dict]
