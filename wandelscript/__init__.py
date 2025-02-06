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
import wandelscript.plugins_addons
from wandelscript.action_queue import ActionQueue, Store
from wandelscript.metamodel import Skill
from wandelscript.runner import ProgramRun, ProgramRunner, ProgramRunState, run

# The Wandelscript language version. This is currently updated manually following the Semantic Versioning Specification.
# See: https://semver.org/
# Given a version number MAJOR.MINOR.PATCH, increment the:
# 1. MAJOR version when you make incompatible API changes
# 2. MINOR version when you add functionality in a backward compatible manner
# 3. PATCH version when you make backward compatible bug fixes
__version__ = "1.2.0"


def analyze(code: str):
    Skill.from_code(code)
