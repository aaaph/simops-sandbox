"""Fixtures of the simops tests."""

from pathlib import Path

import pytest
import yaml

import simops.firmware

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT = ROOT / "environments/rover_room.yaml"
PX4_PLATFORM = ROOT / "platforms/rover_differential_lidar_px4"
# what `git ls-remote --tags` says, trimmed: v1.18.0-rc1 points to fca3df865af3
LS_REMOTE = """\
a5eb12d2ab591251faa009f76b2685b8cc64405d\trefs/tags/v1.17.0
d6f12ad1c4f70ad3230afd7d86e971421e02fef4\trefs/tags/v1.17.0^{}
1111111111111111111111111111111111111111\trefs/tags/v1.18.0-beta2
ac17467e8a5b2acce94555c77ebb2a1c2e5a6452\trefs/tags/v1.18.0-rc1
fca3df865af36124a28c9d607e850f111dbaaea9\trefs/tags/v1.18.0-rc1^{}
2222222222222222222222222222222222222222\trefs/tags/v1.18.0-beta1-foo
"""


@pytest.fixture
def ls_remote_text() -> str:
    """Give the trimmed `git ls-remote --tags` output."""
    return LS_REMOTE


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer `git ls-remote` from LS_REMOTE: unit tests never reach the PX4 repository."""
    monkeypatch.setattr(simops.firmware, "ls_remote", lambda _repo: LS_REMOTE)


@pytest.fixture
def variant(tmp_path: Path):  # noqa: ANN201 -- returns the maker below
    """Write rover_room with some keys replaced to tmp_path; relative platform paths become the PX4 one."""

    def make(name: str, **keys: object) -> Path:
        doc = yaml.safe_load(ENVIRONMENT.read_text()) | {"name": name} | keys
        for agent in doc.get("agents", {}).values():
            if not Path(agent["platform"]).is_absolute():
                agent["platform"] = str(PX4_PLATFORM)
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump(doc))
        return path

    return make


@pytest.fixture
def platform(tmp_path: Path):  # noqa: ANN201 -- returns the maker below
    """Copy the PX4 platform to tmp_path/platforms/<name> with its `autopilot.px4` replaced.

    model.sdf and bridge.yaml are links; the platform whose meshes it borrows is linked next to it.
    """

    def make(name: str, **px4: object) -> Path:
        platforms = tmp_path / "platforms"
        borrowed = platforms / "rover_differential_lidar"
        if not borrowed.exists():
            platforms.mkdir(exist_ok=True)
            borrowed.symlink_to(ROOT / "platforms/rover_differential_lidar")
        out = platforms / name
        out.mkdir()
        for f in ("model.sdf", "bridge.yaml"):
            (out / f).symlink_to(PX4_PLATFORM / f)
        (out / "agent.yaml").write_text(yaml.safe_dump({"autopilot": {"px4": px4}}))
        return out

    return make
