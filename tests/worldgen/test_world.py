"""The parts of an SDF world: walls from segments, obstacles with a shape inside their footprint."""

import math
import re
from dataclasses import replace

import pytest

from worldgen.world import Obstacle, Shape, Wall


def test_wall_from_segment():
    wall = Wall.from_ab("w", (0, 0), (0, 4))
    assert (wall.x, wall.y) == (0, 2)
    assert wall.length == pytest.approx(4 + wall.thickness)
    assert wall.yaw == pytest.approx(math.pi / 2)
    assert Wall.from_ab("w", (-1, 3), (5, 3)).yaw == 0


def half_diagonal(obstacle: Obstacle) -> float:
    """Half-diagonal of a box, radius of a cylinder, read back from the rendered SDF."""
    xml = obstacle.sdf()
    if box := re.search(r"<box><size>(\S+) (\S+) ", xml):
        return math.hypot(float(box[1]), float(box[2])) / 2
    return float(re.search(r"<radius>(\S+)</radius>", xml)[1])


@pytest.mark.parametrize("shape", list(Shape))
def test_every_shape_is_inscribed_in_its_footprint(shape):
    assert half_diagonal(Obstacle("o", 1, 2, 0.4, shape, aspect=0.7)) == pytest.approx(0.4, abs=1e-3)


def test_changing_the_shape_keeps_the_footprint():
    cylinder = Obstacle("o", 1.0, -2.0, 0.3, Shape.CYLINDER, yaw=0.5)
    box = replace(cylinder, shape=Shape.BOX)
    assert (box.x, box.y, box.radius) == (1.0, -2.0, 0.3)
    size = re.search(r"<box><size>(\S+) (\S+) ", box.sdf())
    assert size[1] == size[2]  # no proportions given: square
    assert half_diagonal(box) == pytest.approx(0.3, abs=1e-3)
