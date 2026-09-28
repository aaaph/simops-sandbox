"""The environment file: keys, defaults, paths, and every way loading refuses one (spec: environment)."""

import os
from pathlib import Path

import pytest
import yaml

from simops.environment import Environment, InvalidEnvironment
from simops.firmware import PX4Firmware
from simops.world import RoomSpec, WorldFile

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT = ROOT / "environments/rover_room.yaml"
PX4_PLATFORM = ROOT / "platforms/rover_differential_lidar_px4"


def rewrite(path: Path, edit) -> Path:
    """Apply `edit` to the YAML document in `path`."""
    doc = yaml.safe_load(path.read_text())
    edit(doc)
    path.write_text(yaml.safe_dump(doc))
    return path


def test_defaults(variant):
    path = rewrite(variant("defaults"), lambda d: [d.pop("namespaces"), d.pop("network")])
    environment = Environment.load(path)
    assert environment.namespaces is False
    assert environment.network.router_port == 7447


def test_paths_relative_to_environment_file(tmp_path, monkeypatch):
    doc = yaml.safe_load(ENVIRONMENT.read_text())
    doc["agents"]["rover1"]["platform"] = os.path.relpath(PX4_PLATFORM, tmp_path)
    (tmp_path / "rel.yaml").write_text(yaml.safe_dump(doc))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert Environment.load(Path("../rel.yaml")).agents["rover1"].platform.dir == PX4_PLATFORM


def test_world_sources(variant, tmp_path):
    room = Environment.load(variant("roomed", world={"room": {"seed": 42, "size": [20, 16]}}))
    assert room.world.source == RoomSpec(seed=42, size=(20, 16))
    sdf = tmp_path / "ready.sdf"
    sdf.write_text('<sdf version="1.9"><world name="ready"/></sdf>')
    ready = Environment.load(variant("filed", world={"file": str(sdf)}))
    assert ready.world.source == WorldFile(path=sdf)


def test_partial_pose(variant):
    pose = Environment.load(variant("posed")).agents["rover1"].pose
    assert (pose.x, pose.y, pose.z, pose.roll, pose.pitch, pose.yaw) == (0, 0, 0.2, 0, 0, 0)


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        # several agents need namespaces
        (
            {"agents": {"rover1": {"platform": "x"}, "rover2": {"platform": "x"}}, "namespaces": False},
            "namespaces: true",
        ),
        # a world source is exactly one of room and file
        ({"world": {"room": {"seed": 1}, "file": "x.sdf"}}, r"`room`.*`file`"),
        ({"world": {}}, r"`room`.*`file`"),
        # unknown keys, at any level
        ({"namespace": True}, r"`namespace` is not a key"),
        ({"agents": {"rover1": {"platform": "x", "position": [0, 0]}}}, r"`agents\.rover1\.position` is not"),
        ({"network": {"port": 7448}}, r"`network\.port` is not a key"),
        # PX4 firmware
        ({"autopilot": {"px4": {"ref": "4dbd2e069a5c30c2e53e47e842095d2576dc38c4"}}}, "`version`.*`commit`"),
        ({"autopilot": {"px4": {"version": "v1.18.0-rc1", "commit": "a" * 40}}}, "not both"),
        ({"autopilot": {"px4": {"commit": "4dbd2e0"}}}, "full 40-character SHA"),
        ({"autopilot": {"px4": {"version": "latest"}}}, "not a PX4 version"),
        ({"autopilot": {"px4": {"version": "v1.17.0"}}}, r"v1\.17\.0 is not supported, the minimum is 1\.18"),
    ],
)
def test_rejected(variant, keys, message):
    with pytest.raises(InvalidEnvironment, match=message):
        Environment.load(variant("rejected", **keys))


def test_old_robots_key(tmp_path):
    doc = yaml.safe_load(ENVIRONMENT.read_text())
    path = tmp_path / "old.yaml"
    path.write_text(yaml.safe_dump({**doc, "robots": doc.pop("agents")}))
    with pytest.raises(InvalidEnvironment, match="agents:"):
        Environment.load(path)


def test_message_names_the_file(variant):
    path = variant("named", namespace=True)
    with pytest.raises(InvalidEnvironment, match=str(path)):
        Environment.load(path)


@pytest.mark.parametrize("px4", [{}, {"version": "1.18.0-rc1"}, {"version": "v1.19.0"}, {"commit": "a" * 40}])
def test_px4_accepted(variant, px4):
    assert Environment.load(variant("accepted", autopilot={"px4": px4})).autopilot.px4 == PX4Firmware(**px4)


def test_no_autopilot_key(variant):
    path = rewrite(variant("noautopilot"), lambda d: d.pop("autopilot"))
    assert Environment.load(path).autopilot.px4 == PX4Firmware()
