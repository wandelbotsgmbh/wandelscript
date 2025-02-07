import time
from typing import Any

from nova.actions import MotionSettings

import wandelscript.builtins.array
import wandelscript.builtins.assoc
import wandelscript.builtins.controller
import wandelscript.builtins.fetch
import wandelscript.builtins.math
import wandelscript.builtins.string
import wandelscript.builtins.wait
from wandelscript.metamodel import register_builtin_func
from wandelscript.types import Frame


@register_builtin_func(name="int")
def convert_to_int(value: float) -> int:
    r"""Convert float to int

    Args:
        value: the input float

    Returns:
        The input converted to an integer

    Example:
    >>> import asyncio
    >>> from wandelscript.metamodel import Store, Skill, run_skill
    >>> code = 'a = int(5.63)'
    >>> store = asyncio.run(run_skill(code)).store
    >>> store['a']
    5
    """
    return int(value)


@register_builtin_func(name="string")
def convert_to_string(value: Any) -> str:
    """Convert any value to string"""
    return str(value)


@register_builtin_func(name="time")
def time_() -> float:
    """Return the current time in milliseconds."""
    return 1000 * time.time()


@register_builtin_func()
def python_print(a):
    """Print the input value with Python builtin print."""
    print(a)


def make_settings_modifier(name):
    varname = MotionSettings.field_to_varname(name)

    def modifier(ctx, val):
        previous = ctx.store.get(varname, MotionSettings.model_fields[name].default)
        ctx.store[varname] = val

        async def on_exit(_store):
            ctx.store[varname] = previous

        return on_exit

    return modifier


for setting in MotionSettings.model_fields:
    register_builtin_func(name=setting, pass_context=True)(make_settings_modifier(setting))


@register_builtin_func(pass_context=True)
def tcp(context, tcp_: str | Frame):
    """Set the TCP

    Args:
        context: The execution context
        tcp_: The name of the TCP or a Frame object

    Returns:
        A function that can be used to restore the previous TCP
    """
    tcp_name = tcp_ if isinstance(tcp_, str) else tcp_.name
    previous = context.store.get("__tcp__", None)
    context.store["__tcp__"] = tcp_name

    async def on_exit(_store):
        context.store["__tcp__"] = previous

    return on_exit


# ### Extended functionality - still considered core, but probably not part of the language---------------------
