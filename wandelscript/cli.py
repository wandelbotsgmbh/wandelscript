#!/usr/bin/env python3
"""CLI tool to work with Wandelscript."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from nova import Nova
from typer import Exit, FileText, Option, Typer, echo

import wandelscript

load_dotenv()

app = Typer()


def _validate_url(url: str) -> bool:
    """Validate the provided URL. Return True if valid, otherwise return False."""
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return True
    return False


def _load_python_files(python_files: list[Path]) -> None:
    """Load Python files before executing the Wandelscript program."""
    for file_path in python_files:
        if not file_path.exists():
            echo(f"Error: Python file {file_path} does not exist", err=True)
            raise Exit(1)

        # Import the Python file as a module
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            echo(f"Error: Could not load {file_path}", err=True)
            raise Exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules[file_path.stem] = module
        spec.loader.exec_module(module)


async def main(code: str, nova_api: str):
    """Main program logic."""
    async with Nova(host=nova_api) as nova:
        cell = nova.cell()
        robot_cell = await cell.get_robot_cell()
        # TODO: pass foreign functions
        runner = wandelscript.run(code, robot_cell=robot_cell, default_tcp=None, default_robot=None)

    echo(f"Execution results:\n{runner.program_run.execution_results}")


@app.command()
def run(
    script: FileText,
    nova_api: str = Option(None, "--nova-api", "-n", envvar="NOVA_API", help="URL to NOVA API"),
    python_files: list[Path] = Option(
        None,
        "--python-file",
        "-p",
        help="Python files to load before executing the program. Can be specified multiple times.",
    ),
):
    """Run Wandelscript programs."""

    if not nova_api:
        echo("Error: NOVA_API must be set via '--nova-api' or as an environment variable", err=True)
        raise Exit(1)
    if not _validate_url(nova_api):
        echo(f"Error: NOVA_API value {nova_api} is not a valid URL", err=True)
        raise Exit(1)

    echo(f"NOVA_API: {nova_api}")

    # Load Python files if provided
    if python_files:
        _load_python_files(python_files)

    code = script.read()
    script.close()

    asyncio.run(main(code=code, nova_api=nova_api))


if __name__ == "__main__":
    app()
