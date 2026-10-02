"""The simops command: paths relative to where it runs, and errors as messages (spec: environment)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import simops.cli
from simops.cli import app, named

ENVIRONMENTS = Path(__file__).resolve().parent / "environments"

pytestmark = pytest.mark.usefixtures("no_network")


@pytest.mark.generating_files
def test_relative_path_from_a_subdirectory(monkeypatch, build_dir):
    monkeypatch.chdir(ENVIRONMENTS)
    result = CliRunner().invoke(app, ["build", "small_room.yaml"])
    assert result.exit_code == 0, result.output
    assert str(build_dir / "small_room") in result.output


@pytest.mark.generating_files
def test_invalid_environment_is_a_message(environment_file):
    result = CliRunner().invoke(app, ["host-env", str(environment_file("typo", namespace=True))])
    assert result.exit_code == 1
    assert "`namespace` is not a key" in result.output


def test_argument_is_an_environment_file_or_a_session_name():
    environment, name = named(str(ENVIRONMENTS / "small_room.yaml"))
    assert environment is not None
    assert name == environment.name == "small_room"
    assert named("rover_room") == (None, "rover_room")
    assert named(None) == (None, None)


def test_host_env_from_a_file_needs_no_session(build_dir):
    result = CliRunner().invoke(app, ["host-env", str(ENVIRONMENTS / "small_room.yaml")])
    assert result.exit_code == 0, result.output
    assert "export GZ_PARTITION='small_room'" in result.output
    assert f"export GZ_SIM_RESOURCE_PATH='{build_dir / 'small_room/platforms'}'" in result.output


def test_nothing_up(monkeypatch):
    monkeypatch.setattr(simops.cli, "read_sessions", dict)  # Docker answers: no container at all
    gui = CliRunner().invoke(app, ["gui", str(ENVIRONMENTS / "small_room.yaml")])
    assert gui.exit_code == 1  # at once, no gz started
    assert f"small_room is not up: pixi run simops up {ENVIRONMENTS / 'small_room.yaml'}" in gui.output
    host_env = CliRunner().invoke(app, ["host-env"])
    assert host_env.exit_code == 1
    assert "nothing is up" in host_env.output
    down = CliRunner().invoke(app, ["down"])
    assert down.exit_code == 0
    assert "nothing is up" in down.output
