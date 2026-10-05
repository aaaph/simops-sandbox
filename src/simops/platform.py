"""Platforms: body types, one document each -- in platforms/<p>/platform.yaml or inline (spec: platform)."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from simops import describe
from simops.firmware import PX4Autopilot

PLATFORM_FILE = "platform.yaml"


class Autopilot(BaseModel):
    """`autopilot:` of a platform -- for now every platform runs PX4."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    px4: PX4Autopilot


class PlatformDocument(BaseModel):
    """A platform document once its paths are resolved and its bases laid under it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Path
    bridge: list[dict]
    autopilot: Autopilot

    @field_validator("model")
    @classmethod
    def _model_exists(cls, path: Path) -> Path:
        if not path.is_file():
            msg = f"{path} is not a file"
            raise ValueError(msg)
        return path


class Platform(BaseModel):
    """A body type: its model, the topics the sim bridges for it, and how an autopilot drives it."""

    model_config = ConfigDict(frozen=True)

    model: Path  # the SDF model; its directory is the model's directory
    bridge: list[dict]  # ros_gz_bridge entries -- shared: copy before changing them
    px4: PX4Autopilot

    @classmethod
    def load(cls, platform_dir: Path) -> Platform:
        """Read the platform in a directory, `<platform_dir>/platform.yaml`."""
        return cls.parse(read(platform_dir), here=platform_dir, origin=platform_dir / PLATFORM_FILE)

    @classmethod
    def parse(cls, document: Any, *, here: Path, origin: Path | None = None) -> Platform:  # noqa: ANN401 -- the raw YAML document
        """Validate a platform document whose paths are relative to `here`.

        Errors name `origin` (the platform.yaml, None for an inline platform) and the bases'
        platform.yaml files the document is laid over.
        """
        where = [str(origin)] if origin else []
        try:
            resolved, bases = resolve(document, here, (here,) if origin else ())
        except ValueError as e:
            raise ValueError(": ".join([*where, str(e)])) from None
        where = [", ".join(where + [f"base {b}" for b in bases])] if where or bases else []
        try:
            meta = PlatformDocument.model_validate(resolved)
        except ValidationError as e:
            msg = "; ".join(describe(err, "a platform") for err in e.errors())
            raise ValueError(": ".join([*where, msg])) from None
        return cls(model=meta.model, bridge=meta.bridge, px4=meta.autopilot.px4)

    @property
    def name(self) -> str:
        """The model's directory name, as the model refers to it (model://<name>/...)."""
        return self.model.parent.name

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


def read(platform_dir: Path) -> Any:  # noqa: ANN401 -- the raw YAML document
    """Read the platform document of a directory, its platform.yaml."""
    file = platform_dir / PLATFORM_FILE
    if not file.is_file():
        if (platform_dir / "agent.yaml").is_file():
            msg = (
                f"{platform_dir}: agent.yaml is now {PLATFORM_FILE}, with `model: model.sdf` and "
                "`bridge: bridge.yaml` beside its `autopilot`"
            )
        else:
            msg = f"platform {platform_dir} has no {PLATFORM_FILE}"
        raise ValueError(msg)
    return yaml.safe_load(file.read_text())


def resolve(document: Any, here: Path, chain: tuple[Path, ...]) -> tuple[Any, list[Path]]:  # noqa: ANN401 -- raw YAML
    """Make a document's paths absolute against `here`, then lay it over its base.

    `chain` holds the platform directories already on the way, to stop a cycle of bases.
    Returns the document and the platform.yaml files of its bases, nearest first.
    """
    if not isinstance(document, dict):
        return document, []  # validation says what is wrong with it
    doc = dict(document)
    if isinstance(doc.get("model"), str):
        doc["model"] = str((here / doc["model"]).resolve())
    if isinstance(doc.get("bridge"), str):
        bridge = (here / doc["bridge"]).resolve()
        try:
            doc["bridge"] = yaml.safe_load(bridge.read_text())
        except OSError as e:
            msg = f"bridge: {bridge}: {e.strerror}"
            raise ValueError(msg) from None
    base, bases, under = doc.pop("base", None), [], {}
    if base is not None:
        base_dir = (here / str(base)).resolve()
        if base_dir in chain:
            msg = "a cycle of bases: " + " -> ".join(map(str, (*chain, base_dir)))
            raise ValueError(msg)
        under, deeper = resolve(read(base_dir), base_dir, (*chain, base_dir))
        bases = [base_dir / PLATFORM_FILE, *deeper]
    return merge_patch(under, doc), bases


def merge_patch(target: Any, patch: Any) -> Any:  # noqa: ANN401 -- YAML values
    """Lay `patch` over `target` (JSON Merge Patch, RFC 7386): mappings merge, null removes, the rest replaces."""
    if not isinstance(patch, dict):
        return patch
    merged = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = merge_patch(merged.get(key), value)
    return merged
