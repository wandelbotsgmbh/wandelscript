import json
from functools import singledispatch
from typing import Union

import pydantic
from nova import api
from nova import types as t

from wandelscript import types as ws_types


@singledispatch
def encode(obj):
    """Encodes an object to a pydantic model

    Args:
        obj: the object to encode

    Returns: the pydantic model

    Examples:
    >>> encode(t.Pose((1, 2, 3, 4, 5, 6)))
    Pose(pose=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0))
    >>> encode(t.Vector3d(x=1, y=2, z=3))
    Vector3d(vector3d=(1.0, 2.0, 3.0))
    """
    raise NotImplementedError(type(obj))


def encode_as_json_like_dict(data: ws_types.ElementType):
    return Element(value=encode(data)).model_dump()["value"]


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


def dumps(data: ws_types.ElementType, concise=False) -> str:
    if concise:
        return json.dumps(encode_as_json_like_dict(data))
    return Element(value=encode(data)).model_dump_json()


def loads(s: str, concise=False) -> ws_types.ElementType:
    data = json.loads(s)
    if concise:
        data = {"value": data}
    return decode(Element(**data))


class Pose(pydantic.BaseModel):
    """Pose [*position, *orientation] in 3D space

    Examples:
    >>> Pose(pose=(1, 2, 3, 4, 5, 6))
    Pose(pose=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0))
    >>> Pose(pose=(1, 2, 3, 4)) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    pydantic.error_wrappers.ValidationError: 1 validation error for Pose
    """

    pose: tuple[float, float, float, float, float, float]


@encode.register
def _(obj: t.Pose) -> Pose:
    return Pose(pose=obj.to_tuple())


@decode.register
def _(obj: Pose) -> t.Pose:
    return t.Pose(obj.pose)


class Vector3d(pydantic.BaseModel):
    """Position [x, y, z] in 3D space

    Examples:
    >>> Vector3d(vector3d=(1, 2, 3))
    Vector3d(vector3d=(1.0, 2.0, 3.0))
    >>> Vector3d(vector3d=(1, 2, 3, 4)) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    pydantic.error_wrappers.ValidationError: 1 validation error for Position
    """

    vector3d: tuple[float, float, float]


@encode.register
def _(obj: t.Vector3d) -> Vector3d:
    return Vector3d(vector3d=obj.to_tuple())


@decode.register
def _(obj: Vector3d) -> t.Vector3d:
    return t.Vector3d.from_tuple(obj.vector3d)


class Joints(pydantic.BaseModel):
    """Joints [j1, j2, j3, j4, j5, j6, ...]

    Examples:
    >>> Joints(joints=(1, 2, 3))
    Joints(joints=(1.0, 2.0, 3.0))
    """

    joints: tuple[float, ...]


# @encode.register
# def _(obj: dts.Joints):
#    return obj.joints


@decode.register
def _(obj: Joints):
    return tuple(obj.joints)


class CollisionScene(pydantic.BaseModel):
    """Collision scene

    Examples:
    >>> CollisionScene(collision_scene=api.models.CollisionScene())
    CollisionScene(type='collision_scene', collision_scene=CollisionScene(colliders=None, motion_groups=None))
    """

    type: str = "collision_scene"
    collision_scene: api.models.CollisionScene


@decode.register
def _(obj: CollisionScene):
    return obj.collision_scene


@encode.register
def _(obj: CollisionScene):
    return CollisionScene(collision_scene=obj)


class Capture(pydantic.BaseModel):
    image: str


"""
@encode.register
def _(obj: visiontypes.Capture):  # type: ignore
    f = BytesIO()
    if obj.data.shape[-1] == 1:
        image = Image.fromarray(obj.data[..., 0])
    else:
        image = Image.fromarray(obj.data)
    image.save(f, "png")
    base64_bytes = base64.b64encode(f.getvalue())
    return Capture(image=base64_bytes.decode("ascii"))


@decode.register
def _(obj: Capture):
    base64_string = obj.image
    base64_bytes = base64_string.encode("ascii")
    string_bytes = base64.b64decode(base64_bytes)
    image = Image.open(BytesIO(string_bytes))
    return visiontypes.Capture(data=np.asarray(image), intrinsics=None, extrinsics=None)  # type: ignore


class PointCloud(pydantic.BaseModel):
    pointcloud: str


@encode.register
def _(obj: visiontypes.PointCloud):  # type: ignore
    base64_bytes = base64.b64encode(obj.to_ply())
    return PointCloud(pointcloud=base64_bytes.decode("ascii"))


@decode.register
def _(obj: PointCloud):
    base64_string = obj.pointcloud
    base64_bytes = base64_string.encode("ascii")
    string_bytes = base64.b64decode(base64_bytes)
    return visiontypes.PointCloud.from_ply(string_bytes)  # type: ignore
"""


# ATTENTION! Order matters, e.g. putting float before str causes issues -> "3" gets converted to 3.0
FlatElementType = Union[float, int, bool, str, bytes, Pose, Vector3d, Capture, CollisionScene]  # PointCloud


class Array(pydantic.BaseModel):
    """Array data type"""

    type: str = "array"
    array: list[Union[FlatElementType, "Array", "Record"]]


@encode.register(list)
def _(obj: list) -> Array:
    return Array(array=tuple(map(encode, obj)))  # type: ignore


@encode.register(tuple)
def _(obj: tuple[ws_types.ElementType]) -> Array:
    return Array(array=tuple(map(encode, obj)))  # type: ignore


@decode.register
def _(obj: Array) -> tuple:
    return tuple(map(decode, obj.array))


class Record(pydantic.BaseModel):
    """Record data type"""

    type: str = "record"
    record: dict[str, Union[FlatElementType, Array, "Record"]]


@encode.register(dict)
def _(obj: dict) -> Record:
    return Record(record={k: encode(v) for k, v in obj.items()})


@encode.register(ws_types.Record)
def _(obj: ws_types.Record) -> Record:
    return Record(record={k: encode(v) for k, v in obj.items()})


@decode.register
def _(obj: Record) -> ws_types.Record:
    return ws_types.Record(data={k: decode(v) for k, v in obj.record.items()})


@decode.register
def _(obj: dict) -> ws_types.Record:
    return ws_types.Record(data={k: decode(v) for k, v in obj.items()})


# Necessary to resolve forward references using the new Pydantic v2 method
Array.model_rebuild()
Record.model_rebuild()


ElementType = Union[FlatElementType, Array, Record]


class Element(pydantic.BaseModel):
    value: ElementType


@encode.register
def _(obj: Element):
    return obj


@decode.register
def _(obj: Element):
    return decode(obj.value)


# TODO: Is this needed here?
class Store(pydantic.BaseModel):
    items: dict[str, ElementType]


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


def loads_store(content: str) -> ws_types.ElementType:
    data = json.loads(content)
    return decode(Store(items=data))


def is_encodable(obj):
    encodables = set(encode.registry.keys())
    encodables = [e for e in encodables if not isinstance(object, e)]
    encodables = [e for e in encodables if not isinstance(None, e)]
    return isinstance(obj, tuple(encodables))


__all__ = [
    "encode",
    "decode",
    "dumps",
    "loads",
    "loads_store",
    "Element",
    "ElementType",
    "Store",
    "Array",
    "Record",
    "FlatElementType",
    "Pose",
    "Vector3d",
    "Joints",
    "CollisionScene",
    "Capture",
]
