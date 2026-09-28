"""The simops command: paths relative to where it runs, and errors as messages (spec: environment)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from simops.cli import app

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.usefixtures("no_network")


def test_relative_path_from_a_subdirectory(monkeypatch):
    monkeypatch.chdir(ROOT / "environments")
    result = CliRunner().invoke(app, ["build", "rover_room.yaml"])
    assert result.exit_code == 0, result.output
    assert str(ROOT / "build/rover_room") in result.output


def test_invalid_environment_is_a_message(variant):
    result = CliRunner().invoke(app, ["host-env", str(variant("typo", namespace=True))])
    assert result.exit_code == 1
    assert "`namespace` is not a key" in result.output
