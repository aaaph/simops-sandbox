"""An open field: no walls, no obstacles, just the ground and the start marker."""

import pytest
from typer.testing import CliRunner

from worldgen.cli import app
from worldgen.empty import world
from worldgen.world import SdfWorld, StartMarker


def test_open_field():
    assert world(clearance=0.9) == SdfWorld("field", [StartMarker(0.9)])


@pytest.mark.generating_files
def test_cli(tmp_path):
    runner = CliRunner()
    out = tmp_path / "open.sdf"
    result = runner.invoke(app, ["empty", "-o", str(out), "--clearance", "0.9"])
    assert result.exit_code == 0, result.output
    assert "open field" in result.output
    assert out.exists()
