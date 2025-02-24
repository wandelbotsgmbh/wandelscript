"""Foreign Function Interface.

Use to register your own or 3rd party Python functions with Wandelscript
programs so that you can use those functions within your Wandelscript code.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ForeignFunction:
    """References a function that can be used inside a Wandelscript.

    Args:
        function: Handle to an arbitrary function, even an async function.
        pass_context (bool): Whether or not the function takes the current wandelscript context
            as the first parameter. Defaults to False.
    """

    function: Callable
    pass_context: bool = False

    def __post_init__(self):
        if not isinstance(self.function, Callable):
            raise TypeError(f"Function of {self} must be a Callable, got {type(self.function).__name__}")


def ff(fn: Callable, pass_context: bool = False) -> ForeignFunction:
    """Shortcut method to create a ForeignFunction.

    Args:
        function: Handle to an arbitrary function, even an async function.
        pass_context (bool): Whether or not the function takes the current wandelscript context
            as the first parameter. Defaults to False.
    """
    return ForeignFunction(function=fn, pass_context=pass_context)
