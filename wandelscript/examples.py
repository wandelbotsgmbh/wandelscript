import json
from pathlib import Path

from loguru import logger

from wandelscript import serializer

_EXAMPLE_DIR = Path(__file__).parent / "examples"


def read_examples(cell_name: str | None = None):
    result = {}

    for a in _EXAMPLE_DIR.iterdir():
        cell = cell_name or "default"
        if a.suffix == ".ws":
            code = a.open().read()
            data = serializer.loads_store((_EXAMPLE_DIR / f"{a.stem}.json").open().read())
            try:
                cells = json.load((_EXAMPLE_DIR / f"{a.stem}.cell.json").open())
            except FileNotFoundError:
                cells = json.load((_EXAMPLE_DIR / "default.cell.json").open())
            if cell not in cells:
                logger.info(f"Cell {cell_name} not found in {a.stem}.cell.json, using default")
                cell = "default"
            result[a.stem] = code, data, cells[cell]
    return result


EXAMPLES = read_examples()

DEFAULT, _, _ = EXAMPLES["default"]
