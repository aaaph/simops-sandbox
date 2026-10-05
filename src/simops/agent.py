"""Agents: bodies placed in the world, and how one is put there."""

import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from simops.platform import Platform

POSE_FIELDS = ("x", "y", "z", "roll", "pitch", "yaw")


class Pose(BaseModel):
    """Where an agent starts: position in metres, ROS roll-pitch-yaw in radians."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        """Take `[x, y, z, roll, pitch, yaw]`, missing components 0."""
        if isinstance(value, (list, tuple)):
            if len(value) > len(POSE_FIELDS):
                msg = f"a pose has at most {len(POSE_FIELDS)} numbers: {', '.join(POSE_FIELDS)}"
                raise ValueError(msg)
            return dict(zip(POSE_FIELDS, value, strict=False))
        return value


class Agent(BaseModel):
    """One body in the simulation: an instance of a platform, with a start pose."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    pose: Pose = Pose()

    @field_validator("platform", mode="before")
    @classmethod
    def _platform(cls, value: Any, info: ValidationInfo) -> Any:  # noqa: ANN401 -- a path, a document or a Platform
        """Load the platform from its directory or from the document inline, relative to the environment file."""
        if isinstance(value, Platform):
            return value
        base = (info.context or {}).get("base", Path.cwd())
        if isinstance(value, dict):
            return Platform.parse(value, here=base)
        return Platform.load((base / str(value)).resolve())


def quaternion(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """Turn ROS roll-pitch-yaw (extrinsic x, then y, then z) into a quaternion (x, y, z, w)."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def entity_factory(name: str, sdf: str, pose: Pose) -> str:
    """Build the gz.msgs.EntityFactory request that puts one agent into the world."""
    qx, qy, qz, qw = quaternion(pose.roll, pose.pitch, pose.yaw)
    return (
        f'sdf_filename: "{sdf}", name: "{name}", allow_renaming: false, '
        f"pose: {{position: {{x: {pose.x}, y: {pose.y}, z: {pose.z}}}, "
        f"orientation: {{x: {qx}, y: {qy}, z: {qz}, w: {qw}}}}}"
    )
