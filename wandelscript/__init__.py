"""Wandelscript


Example:
>>> import asyncio
>>> from nova.types import Vector3d
>>> from wandelscript.metamodel import run_skill
>>> code = 'a = (0, 1, 2) + (0, 0, 3)'
>>> context = asyncio.run(run_skill(code))
>>> context.store['a']
Vector3d(x=0.0, y=1.0, z=5.0)
"""

import wandelscript.antlrvisitor  # load Skill.from_code
import wandelscript.builtins
import wandelscript.motions  # load all motion connectors
from wandelscript.metamodel import Skill
from wandelscript.runner import ProgramRun, ProgramRunner, ProgramRunState, run
from wandelscript.runtime import ActionQueue, Store


def analyze(code: str):
    Skill.from_code(code)
