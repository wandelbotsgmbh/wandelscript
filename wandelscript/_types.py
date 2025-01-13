"""Types and constructs for internal use."""

from typing import Mapping, Union

import pydantic
from nova.types import Pose, Vector3d


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


ElementType = Union[bool, int, float, Vector3d, Pose, str, Record, tuple, dict]
