"""Sensor frames read out of a platform's model SDF, for frame_publisher."""

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def sensor_frames(sdf: Path) -> list[tuple[str, list[str]]]:
    """base_link -> <link> for every SDF link that carries a sensor.

    Read from the model rather than restated in a URDF, so the frames cannot
    drift away from the geometry Gazebo actually simulates.
    """
    out = []
    for link in ET.parse(sdf).getroot().iter("link"):
        name, pose = link.get("name"), link.find("pose")
        if name is None or link.find("sensor") is None or pose is None:
            continue
        if pose.get("relative_to") != "base_link":
            continue
        out.append((name, (pose.text or "0 0 0 0 0 0").split()))
    return out


def frame_specs(sdf: Path) -> list[str]:
    """sensor_frames() as the "<child> x y z roll pitch yaw" strings frame_publisher takes."""
    return [f"{name} " + " ".join(pose) for name, pose in sensor_frames(sdf)]
