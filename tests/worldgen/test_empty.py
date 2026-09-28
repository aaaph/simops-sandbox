"""An open field: no walls, no obstacles, just the ground and the start marker."""

import xml.etree.ElementTree as ET

from typer.testing import CliRunner

from worldgen.cli import app
from worldgen.empty import generate


def test_open_field(tmp_path):
    out = tmp_path / "open.sdf"
    generate(out, clearance=0.9)
    world = ET.parse(out).find("world")
    assert world is not None
    assert world.get("name") == "field"
    names = {m.get("name") for m in world.findall("model")}
    assert {"start_marker", "ground_plane"} <= names
    assert not any(n.startswith(("wall_", "obs_")) for n in names)


def test_cli(tmp_path):
    runner = CliRunner()
    out = tmp_path / "open.sdf"
    result = runner.invoke(app, ["empty", "-o", str(out), "--clearance", "0.9"])
    assert result.exit_code == 0, result.output
    assert "open field" in result.output
    assert out.exists()
