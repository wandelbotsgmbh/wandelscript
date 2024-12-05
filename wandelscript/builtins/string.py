from typing import SupportsIndex

from wandelscript.metamodel import register_builtin_func


@register_builtin_func()
def replace(value: str, old: str, new: str, *, count: SupportsIndex = -1) -> str:
    """Replace a substring with another substring"""
    return value.replace(old, new, count)
