"""Rooms: the same seed gives the same room, and every free cell stays reachable."""

import math
import xml.etree.ElementTree as ET

import pytest
from typer.testing import CliRunner

from worldgen.cli import app
from worldgen.room import room_walls, unreachable_cells, world
from worldgen.world import WALL_T, Obstacle, Shape, StartMarker, Wall

# small rooms: 6 x 5 m generates in ~10 ms, the default 10 x 8 m in ~50 ms; what these tests
# check does not depend on the size
SMALL = {"size": (6.0, 5.0), "obstacles": 4}


@pytest.fixture(scope="module")
def room():
    """One small room for the tests that only look at it (parts are frozen, nobody changes them)."""
    return world(clearance=0.9, **SMALL)


def test_same_seed_same_room():
    room = world(clearance=0.9, seed=7, **SMALL)
    assert room == world(clearance=0.9, seed=7, **SMALL)
    assert room != world(clearance=0.9, seed=8, **SMALL)


def test_room_parts(room):
    parts = room.parts
    assert [p.name for p in parts[:4] if isinstance(p, Wall)] == ["wall_n", "wall_s", "wall_e", "wall_w"]
    assert all(isinstance(p, Obstacle) for p in parts[4:-1])
    assert len(parts) > 5
    assert parts[-1] == StartMarker(0.9)


def test_room_is_an_empty_world(room):
    sdf = ET.fromstring(room.sdf()).find("world")
    assert sdf is not None
    assert sdf.get("name") == "room"
    assert sdf.find("include") is None  # no robot: agents are added at runtime


def test_walled_off_cells_are_counted():
    size = (10.0, 4.0)
    assert unreachable_cells(size, [], clearance=0.9, cell=0.1) == 0
    # a row of discs across the room at x = 2: everything beyond it is cut off from the origin
    wall = [Obstacle(f"o{y}", 2.0, y / 2, 0.4, Shape.CYLINDER) for y in range(-4, 5)]
    assert unreachable_cells(size, wall, clearance=0.9, cell=0.1) > 0


def inside(wall: Wall, x: float, y: float) -> bool:
    """Whether (x, y) lies in the wall's footprint: its box turned by yaw."""
    dx, dy = x - wall.x, y - wall.y
    along = dx * math.cos(wall.yaw) + dy * math.sin(wall.yaw)
    across = -dx * math.sin(wall.yaw) + dy * math.cos(wall.yaw)
    return abs(along) <= wall.length / 2 + 1e-9 and abs(across) <= wall.thickness / 2 + 1e-9


def test_room_walls_are_joined_with_no_gap():
    sx, sy = 10.0, 8.0
    walls = room_walls((sx, sy))
    ox, oy, n = sx / 2 + WALL_T / 2, sy / 2 + WALL_T / 2, 400
    # points of the frame only: along each side, at its inner edge, its axis and its outer edge
    along_x = [-ox + 2 * ox * i / n for i in range(n + 1)]
    along_y = [-oy + 2 * oy * i / n for i in range(n + 1)]
    frame = [(x, s * y) for x in along_x for y in (sy / 2 - WALL_T / 2, sy / 2, oy) for s in (1, -1)]
    frame += [(s * x, y) for y in along_y for x in (sx / 2 - WALL_T / 2, sx / 2, ox) for s in (1, -1)]
    assert (ox, oy) in frame  # the outer corners, where walls without end caps leave a gap
    assert [p for p in frame if not any(inside(w, *p) for w in walls)] == []


@pytest.mark.generating_files
def test_cli_needs_clearance(tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["room", "-o", str(tmp_path / "r.sdf")]).exit_code != 0
    result = runner.invoke(app, ["room", "-o", str(tmp_path / "r.sdf"), "--clearance", "0.9", "--seed", "3"])
    assert result.exit_code == 0, result.output
    assert "verified, seed 3" in result.output
