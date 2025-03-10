#!/usr/bin/env python3
"""CLI tool to work with Wandelscript."""

import asyncio
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


async def main(code: str):
    """Main program logic."""
    async with Nova() as nova:
        cell = nova.cell()
        robot_cell = await cell.get_robot_cell()
        runner = wandelscript.run(code, robot_cell=robot_cell, default_tcp=None, default_robot=None)

    echo(f"Execution results:\n{runner.program_run.execution_results}")


@app.command()
def run(script: FileText, nova_api: str = Option(None, "--nova-api", "-n", envvar="NOVA_API", help="URL to NOVA API")):
    """Run Wandelscript programs."""

    if not nova_api:
        echo("Error: NOVA_API must be set via '--nova-api' or as an environment variable", err=True)
        raise Exit(1)
    if not _validate_url(nova_api):
        echo(f"Error: NOVA_API value {nova_api} is not a valid URL", err=True)
        raise Exit(1)

    echo(f"NOVA_API: {nova_api}")

    code = script.read()
    script.close()

    asyncio.run(main(code))


if __name__ == "__main__":
    app()
