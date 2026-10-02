"""The simops command: environment -> bundle -> session."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

import simops
from simops import build_dir
from simops.bundle import build
from simops.environment import Environment, InvalidEnvironment
from simops.session import (
    DockerUnavailableError,
    NotUpError,
    RunningSession,
    Session,
    SeveralUpError,
    down,
    find,
    read_sessions,
)

app = typer.Typer(help=simops.__doc__, no_args_is_help=True, add_completion=False, rich_markup_mode=None)
EnvironmentPath = Annotated[Path, typer.Argument(help="environment YAML file", metavar="ENVIRONMENT")]
Timeout = Annotated[float, typer.Option(help="seconds to wait for the agents")]
SessionArgument = Annotated[
    str | None,
    typer.Argument(
        help="environment YAML file or session name; none: the one running session", metavar="[ENVIRONMENT]"
    ),
]


def load(path: Path) -> Environment:
    """Load the environment, or say what is wrong with it and exit 1."""
    try:
        return Environment.load(path)
    except InvalidEnvironment as e:
        print(e, file=sys.stderr)
        raise typer.Exit(1) from None


def named(argument: str | None) -> tuple[Environment | None, str | None]:
    """Load an environment file (a path that exists or ends in .yaml/.yml); anything else is a session name."""
    if argument is None:
        return None, None
    path = Path(argument)
    if path.is_file() or path.suffix in {".yaml", ".yml"}:
        environment = load(path)
        return environment, environment.name
    return None, argument


def running(argument: str | None, service: str) -> RunningSession:
    """Find the running session `argument` names, or the only one; or say why not and exit 1."""
    environment, name = named(argument)
    try:
        return find(read_sessions(), name, service)
    except NotUpError as e:
        print(f"{e}: pixi run simops up {argument if environment else '<environment>'}", file=sys.stderr)
    except (DockerUnavailableError, SeveralUpError) as e:
        print(e, file=sys.stderr)
    raise typer.Exit(1)


@app.command("build")
def build_cmd(environment: EnvironmentPath) -> None:
    """Write the bundle to build/<name>/ ($SIMOPS_BUILD_DIR/<name>/ when set)."""
    loaded = load(environment)
    print(build(loaded).write(Session(loaded).dir))


@app.command("up")
def up_cmd(environment: EnvironmentPath, timeout: Timeout = 300) -> None:
    """Start a session and wait until the agents are in the world."""
    session = Session(load(environment))
    if code := session.up(timeout):
        raise typer.Exit(code)
    name = session.environment.name
    host_env = f"pixi run simops host-env {name}"
    host_env = f"{host_env} | source" if os.environ.get("SHELL", "").endswith("fish") else f'eval "$({host_env})"'
    print(f"  gui:  pixi run simops gui {name}")
    print(f"  host: {host_env}")
    print(f"  stop: pixi run simops down {name}")


@app.command("down")
def down_cmd(environment: SessionArgument = None) -> None:
    """Stop the session: every container of it, exited ones too; nothing up is no error."""
    _, name = named(environment)
    try:
        found = read_sessions()
        name = find(found, name, None).name
    except (DockerUnavailableError, SeveralUpError) as e:
        print(e, file=sys.stderr)
        raise typer.Exit(1) from None
    except NotUpError as e:
        # a session from a bundle built before the simops labels: ours if compose ran it from build/<name>/
        if not (name in found and found[name].bundle == build_dir() / name):
            print(e)
            raise typer.Exit(0) from None
    raise typer.Exit(down(name))


@app.command("host-env")
def host_env_cmd(environment: SessionArgument = None) -> None:
    """Print exports for gz and ROS on the host: from an environment file, or from the running session."""
    loaded, _ = named(environment)
    env = Session(loaded).host_env() if loaded else running(environment, "zenoh-router").host_env()
    print("\n".join(f"export {k}='{v}'" for k, v in env.items()))


@app.command("gui")
def gui_cmd(environment: SessionArgument = None) -> None:
    """Native gz GUI attached to a running session, the agents' meshes from its bundle."""
    session = running(environment, "world")  # gz sim -g would wait for a missing world forever
    if not (session.bundle / "platforms").is_dir():
        print(
            f"warning: {session.bundle}/platforms is gone, the agents show without their meshes", file=sys.stderr
        )
    env = os.environ | session.host_env()
    raise typer.Exit(subprocess.run(["gz", "sim", "-g"], env=env, check=False).returncode)


# the command after `--` goes through untouched, whatever flags it has
@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run_cmd(ctx: typer.Context, environment: EnvironmentPath, timeout: Timeout = 300) -> None:
    """Up, run the command after --, down."""
    raise typer.Exit(Session(load(environment)).run(timeout, ctx.args))
