"""Fixtures of the simops tests."""

from pathlib import Path

import pytest
import yaml

import simops.firmware
from simops.environment import Environment
from simops.platform import Platform

ROOT = Path(__file__).resolve().parents[2]
# the tests' own environment files; the examples in environments/ are not used by tests
ENVIRONMENTS = Path(__file__).resolve().parent / "environments"
PX4_PLATFORM = Path(__file__).resolve().parent / "platforms/rover_differential_lidar_px4"  # the tests' own copy
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


def document(name: str, keys: dict) -> dict:
    """Give one rover in an open field, `keys` replaced; relative platform paths become the PX4 one.

    An open field builds in ~1 ms, a 25 x 21 m room takes most of a second to generate; a test
    that needs a room says so (`world=`, a small one).
    """
    doc = {
        "name": name,
        "namespaces": False,
        "network": {"router_port": 7447},
        "world": {"empty_world": None},
        "agents": {"rover1": {"platform": str(PX4_PLATFORM), "pose": [0, 0, 0.2]}},
    } | keys
    for agent in doc.get("agents", {}).values():
        if isinstance(agent["platform"], str) and not Path(agent["platform"]).is_absolute():
            agent["platform"] = str(PX4_PLATFORM)
    return doc


@pytest.fixture
def environment():  # noqa: ANN201 -- returns the maker below
    """Build the test environment with some keys replaced, in memory; errors name `<name>.yaml`."""

    def make(name: str, **keys: object) -> Environment:
        return Environment.parse(document(name, keys), base=ENVIRONMENTS, origin=Path(f"{name}.yaml"))

    return make


@pytest.fixture
def platform():  # noqa: ANN201 -- returns the maker below
    """Give the PX4 platform's model with this `autopilot.px4`, in memory; errors name its platform.yaml."""

    def make(**px4: object) -> Platform:
        document = {"model": "model.sdf", "bridge": [], "autopilot": {"px4": px4}}
        return Platform.parse(document, here=PX4_PLATFORM, origin=PX4_PLATFORM / "platform.yaml")

    return make


@pytest.fixture
def environment_file(tmp_path: Path):  # noqa: ANN201 -- returns the maker below
    """Write the test environment with some keys replaced to tmp_path, for what needs the file itself."""

    def make(name: str, **keys: object) -> Path:
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump(document(name, keys)))
        return path

    return make


@pytest.fixture
def platform_dir(tmp_path: Path):  # noqa: ANN201 -- returns the maker below
    """Write tmp_path/platforms/<name>/platform.yaml: the PX4 platform's model and bridge, `document` over them.

    `document` is laid over `model` and `bridge` naming the PX4 platform's files; `autopilot.px4`
    is `px4` unless the document gives `autopilot`.
    """

    def make(name: str, document: dict | None = None, **px4: object) -> Path:
        out = tmp_path / "platforms" / name
        out.mkdir(parents=True)
        own = {"model": str(PX4_PLATFORM / "model.sdf"), "bridge": str(PX4_PLATFORM / "bridge.yaml")}
        (out / "platform.yaml").write_text(yaml.safe_dump(own | {"autopilot": {"px4": px4}} | (document or {})))
        return out

    return make
