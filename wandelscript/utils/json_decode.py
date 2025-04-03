from wandelscript.types import ElementType
import json
import pydantic
from functools import singledispatch
from nova.types import Pose, Vector3d

JsonType = float | int | bool | str | bytes | tuple | list | dict

@singledispatch
def decode(obj):
    """Decodes a plain dict to the matching pydantic model or elemental type.

    Args:
        obj: the obj to decode

    Returns: the pydantic model or elemental type

    Examples:
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


class Element(pydantic.BaseModel):
    value: ElementType


class Store(pydantic.BaseModel):
    items: dict[str, JsonType]


@decode.register
def _(obj: Element):
    return decode(obj.value)


@decode.register
def _(obj: Store):
    return {k: decode(v) for k, v in obj.items.items()}


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


@decode.register
def _(obj: dict):
    # If it has the signature of a Pose, decode it as a Pose:
    if "position" in obj and "orientation" in obj:
        return Pose(**obj)
    if "x" in obj and "y" in obj and "z" in obj:
        return Vector3d(**obj)
    # Otherwise just decode children (if needed) or leave it alone:
    return {k: decode(v) for k, v in obj.items()}


def dumps(data: ElementType) -> str:
    return Element(value=data).model_dump_json()


def loads(s: str) -> ElementType:
    data = json.loads(s)
    return decode(Element(**data))


def loads_store(content: str) -> ElementType:
    """
    Example:
    >>> json_content = '{"a": {"orientation": [1.0, 2.0, 3.0], "position": [4.0, 5.0, 6.0]}, "a_dict": {"a": 4}}'
    >>> loads_store(json_content)
    {'a': Pose(position=Vector3d(x=4.0, y=5.0, z=6.0), orientation=Vector3d(x=1.0, y=2.0, z=3.0)), 'a_dict': {'a': 4}}
    >>> json_content = '{"b": {"a": 3}, "c": [1, 2, 3]}'
    >>> loads_store(json_content)
    {'b': {'a': 3}, 'c': [1, 2, 3]}
    """
    data = json.loads(content)
    return decode(Store(items=data))
