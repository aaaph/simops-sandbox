"""The simops command: environment -> bundle -> session."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

import simops
from simops.bundle import build
from simops.environment import Environment, InvalidEnvironment
from simops.session import Session

app = typer.Typer(help=simops.__doc__, no_args_is_help=True, add_completion=False, rich_markup_mode=None)
EnvironmentPath = Annotated[Path, typer.Argument(help="environment YAML file", metavar="ENVIRONMENT")]
Timeout = Annotated[float, typer.Option(help="seconds to wait for the agents")]


def load(path: Path) -> Environment:
    """Load the environment, or say what is wrong with it and exit 1."""
    try:
        return Environment.load(path)
    except InvalidEnvironment as e:
        print(e, file=sys.stderr)
        raise typer.Exit(1) from None


@app.command("build")
def build_cmd(environment: EnvironmentPath) -> None:
    """Write the bundle to build/<name>/."""
    loaded = load(environment)
    print(build(loaded).write(Session(loaded).dir))


@app.command("up")
def up_cmd(environment: EnvironmentPath, timeout: Timeout = 300) -> None:
    """Start a session and wait until the agents are in the world."""
    raise typer.Exit(Session(load(environment)).up(timeout))


@app.command("down")
def down_cmd(environment: EnvironmentPath) -> None:
    """Stop the session."""
    raise typer.Exit(Session(load(environment)).down())


@app.command("host-env")
def host_env_cmd(environment: EnvironmentPath) -> None:
    """Print exports for gz and ROS on the host."""
    print("\n".join(f"export {k}='{v}'" for k, v in Session(load(environment)).host_env().items()))


@app.command("gui")
def gui_cmd(environment: EnvironmentPath) -> None:
    """Native gz GUI attached to the environment's running session."""
    env = os.environ | Session(load(environment)).host_env()
    raise typer.Exit(subprocess.run(["gz", "sim", "-g"], env=env, check=False).returncode)


# the command after `--` goes through untouched, whatever flags it has
@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run_cmd(ctx: typer.Context, environment: EnvironmentPath, timeout: Timeout = 300) -> None:
    """Up, run the command after --, down."""
    raise typer.Exit(Session(load(environment)).run(timeout, ctx.args))
