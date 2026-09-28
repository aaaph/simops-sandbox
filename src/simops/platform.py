"""Platforms: body types in platforms/<p>/ -- model.sdf, bridge.yaml, agent.yaml."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Platform(BaseModel):
    """A body type: its model, the topics the sim bridges for it, and how an autopilot drives it."""

    model_config = ConfigDict(frozen=True)

    dir: Path
    px4_airframe: int | None = None

    @classmethod
    def load(cls, platform_dir: Path) -> Platform:
        """Read a platform directory; it must hold model.sdf, bridge.yaml and agent.yaml."""
        missing = [f for f in ("model.sdf", "bridge.yaml", "agent.yaml") if not (platform_dir / f).exists()]
        if missing:
            msg = f"platform {platform_dir} has no {', '.join(missing)}"
            raise ValueError(msg)
        meta = yaml.safe_load((platform_dir / "agent.yaml").read_text()) or {}
        airframe = ((meta.get("autopilot") or {}).get("px4") or {}).get("airframe")
        return cls(dir=platform_dir, px4_airframe=airframe)

    @property
    def name(self) -> str:
        """The platform's directory name, as models refer to it (model://<name>/...)."""
        return self.dir.name

    @property
    def model(self) -> Path:
        """The platform's SDF model."""
        return self.dir / "model.sdf"

    @property
    def bridge(self) -> Path:
        """The platform's ros_gz_bridge entries."""
        return self.dir / "bridge.yaml"

    def width(self) -> float:
        """Widest Y extent of the collision shapes, in metres.

        Every geometry is treated as a box (sphere -> 2r cube, cylinder -> 2r x 2r x l),
        rotated by its link pose, so wheels sticking out past the chassis are counted.
        """

        def nums(el: ET.Element, tag: str) -> list[float]:
            """Read the numbers in <tag>, empty if it is missing -- SDF leaves plenty optional."""
            child = el.find(tag)
            return [float(x) for x in (child.text or "").split()] if child is not None else []

        def pose_of(el: ET.Element) -> list[float]:
            return (nums(el, "pose") + [0.0] * 6)[:6]

        lo = hi = 0.0
        for link in ET.parse(self.model).getroot().iter("link"):
            _lx, ly, _lz, lr, lp, lyaw = pose_of(link)
            for col in link.iter("collision"):
                _cx, cy, _cz, cr, cp, cyaw = pose_of(col)
                geom = col.find("geometry")
                if geom is None:
                    continue
                if (b := geom.find("box")) is not None:
                    ex, ey, ez = [v / 2 for v in nums(b, "size")]
                elif (c := geom.find("cylinder")) is not None:
                    ex = ey = nums(c, "radius")[0]
                    ez = nums(c, "length")[0] / 2
                elif (s := geom.find("sphere")) is not None:
                    ex = ey = ez = nums(s, "radius")[0]
                else:
                    continue  # meshes: no cheap extent, chassis boxes cover us
                row = y_row(lr + cr, lp + cp, lyaw + cyaw)
                centre = ly + cy
                reach = abs(row[0]) * ex + abs(row[1]) * ey + abs(row[2]) * ez
                lo, hi = min(lo, centre - reach), max(hi, centre + reach)
        return hi - lo


def y_row(roll: float, pitch: float, yaw: float) -> tuple[float, float, float]:
    """Row of the ROS roll-pitch-yaw rotation matrix (Rz @ Ry @ Rx) that maps body axes onto world Y."""
    sr, cr, sp, cp, sy, cy = (f(a) for a in (roll, pitch, yaw) for f in (math.sin, math.cos))
    return (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr)
