"""What an SDF world is made of: walls, obstacles and the start marker, assembled by `SdfWorld`.

Each part renders its own SDF model through `worldgen.sdf`; where the parts go is the world
type's concern (`room`, `empty`). Spec: worldgen.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

from worldgen import sdf

WALL_H, WALL_T = 2.5, 0.15
OBSTACLE_H = WALL_H / 2  # half wall height, tall enough for any lidar plane


@dataclass(frozen=True)
class Wall:
    """A wall centred at (x, y), `length` long along `yaw`, standing on the floor."""

    name: str
    x: float
    y: float
    length: float
    yaw: float = 0.0
    thickness: float = WALL_T
    height: float = WALL_H

    @classmethod
    def from_ab(cls, name: str, a: tuple[float, float], b: tuple[float, float]) -> Wall:
        """Build the wall along the segment a -> b, half its thickness longer at each end.

        The end caps are what closes a corner: two walls sharing an end point leave no gap.
        """
        (ax, ay), (bx, by) = a, b
        length = math.hypot(bx - ax, by - ay) + WALL_T
        return cls(name, (ax + bx) / 2, (ay + by) / 2, length, math.atan2(by - ay, bx - ax))

    def sdf(self) -> str:
        """Render the wall as a static box model."""
        geom = f"<box><size>{self.length:.3f} {self.thickness:.3f} {self.height:.3f}</size></box>"
        return sdf.model(self.name, self.x, self.y, self.height / 2, self.yaw, geom, "0.7 0.7 0.7 1")


class Shape(StrEnum):
    """An obstacle's shape; every shape is inscribed in the obstacle's footprint disc."""

    BOX = "box"
    CYLINDER = "cylinder"


@dataclass(frozen=True)
class Obstacle:
    """A footprint disc at (x, y) of `radius`, and a shape inscribed in it.

    Placement and the reachability check read only the footprint, so any shape keeps a room's
    guarantees: `replace(obstacle, shape=Shape.BOX)` is always safe.
    """

    name: str
    x: float
    y: float
    radius: float
    shape: Shape
    yaw: float = 0.0
    aspect: float = math.pi / 4  # BOX only: angle of the diagonal; pi/4 is a square

    def sdf(self) -> str:
        """Render the obstacle as a static model of its shape."""
        r, h = self.radius, OBSTACLE_H
        match self.shape:
            case Shape.BOX:  # half-diagonal == r
                w, d = 2 * r * math.cos(self.aspect), 2 * r * math.sin(self.aspect)
                geom, rgba = f"<box><size>{w:.3f} {d:.3f} {h:.3f}</size></box>", "0.8 0.5 0.2 1"
            case Shape.CYLINDER:
                geom = f"<cylinder><radius>{r:.3f}</radius><length>{h:.3f}</length></cylinder>"
                rgba = "0.2 0.4 0.8 1"
        return sdf.model(self.name, self.x, self.y, h / 2, self.yaw, geom, rgba)


@dataclass(frozen=True)
class StartMarker:
    """Visual-only disc at the origin: where the robot starts and odom is zeroed."""

    clearance: float

    def sdf(self) -> str:
        """Render the marker as a visual-only model, no collision."""
        radius = self.clearance / 2 * 1.2
        return f"""    <model name="start_marker">
      <static>true</static>
      <pose>0 0 0.005 0 0 0</pose>
      <link name="link">
        <visual name="v">
          <geometry><cylinder><radius>{radius:.3f}</radius><length>0.01</length></cylinder></geometry>
          <material>
            <ambient>0.8 0.1 0.1 1</ambient>
            <diffuse>0.8 0.1 0.1 1</diffuse>
            <emissive>0.3 0.0 0.0 1</emissive>
          </material>
        </visual>
      </link>
    </model>"""


type Part = Wall | Obstacle | StartMarker


@dataclass(frozen=True)
class SdfWorld:
    """A named world holding `parts`, inside the envelope every worldgen world shares."""

    name: str
    parts: list[Part]

    def sdf(self) -> str:
        """Render the whole world as SDF text."""
        return sdf.envelope(self.name, [p.sdf() for p in self.parts])
