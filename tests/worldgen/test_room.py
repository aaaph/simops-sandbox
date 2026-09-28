"""Rooms: the same seed gives the same room, and every free cell stays reachable."""

import xml.etree.ElementTree as ET

from typer.testing import CliRunner

from worldgen.cli import app
from worldgen.room import generate, unreachable_cells


def test_same_seed_same_room(tmp_path):
    a, b = tmp_path / "a.sdf", tmp_path / "b.sdf"
    generate(a, clearance=0.9, seed=7, size=(12.0, 9.0))
    generate(b, clearance=0.9, seed=7, size=(12.0, 9.0))
    assert a.read_bytes() == b.read_bytes()
    generate(b, clearance=0.9, seed=8, size=(12.0, 9.0))
    assert a.read_bytes() != b.read_bytes()


def test_room_is_an_empty_world(tmp_path):
    out = tmp_path / "room.sdf"
    generate(out, clearance=0.9)
    world = ET.parse(out).find("world")
    assert world is not None
    assert world.get("name") == "room"
    assert world.find("include") is None  # no robot: agents are added at runtime


def test_walled_off_cells_are_counted():
    size = (10.0, 4.0)
    assert unreachable_cells(size, [], clearance=0.9, cell=0.1) == 0
    # a row of discs across the room at x = 2: everything beyond it is cut off from the origin
    wall = [(2.0, y / 2, 0.4, False, 0.0) for y in range(-4, 5)]
    assert unreachable_cells(size, wall, clearance=0.9, cell=0.1) > 0


def test_cli_needs_clearance(tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["room", "-o", str(tmp_path / "r.sdf")]).exit_code != 0
    result = runner.invoke(app, ["room", "-o", str(tmp_path / "r.sdf"), "--clearance", "0.9", "--seed", "3"])
    assert result.exit_code == 0, result.output
    assert "verified, seed 3" in result.output
