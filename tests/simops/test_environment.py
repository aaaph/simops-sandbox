"""The environment file: keys, defaults, paths, and every way loading refuses one (spec: environment)."""

import os
from pathlib import Path

import pytest
import yaml

from simops.environment import Environment, InvalidEnvironment
from simops.world import EmptySpec, RoomSpec, WorldFile

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
    room = Environment.load(variant("roomed", world={"generate_room": {"seed": 42, "size": [20, 16]}}))
    assert room.world.source == RoomSpec(seed=42, size=(20, 16))
    sdf = tmp_path / "ready.sdf"
    sdf.write_text('<sdf version="1.9"><world name="ready"/></sdf>')
    ready = Environment.load(variant("filed", world={"file": str(sdf)}))
    assert ready.world.source == WorldFile(path=sdf)
    empty = Environment.load(variant("emptied", world={"empty_world": None}))
    assert empty.world.source == EmptySpec()


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
        # a world source is exactly one of generate_room, file and empty_world
        ({"world": {"generate_room": {"seed": 1}, "file": "x.sdf"}}, r"`generate_room`.*`file`.*`empty_world`"),
        ({"world": {"empty_world": None, "file": "x.sdf"}}, r"`generate_room`.*`file`.*`empty_world`"),
        ({"world": {}}, r"`generate_room`.*`file`.*`empty_world`"),
        ({"world": {"room": {"seed": 1}}}, r"`world\.room` is now `world\.generate_room`"),
        ({"world": {"empty_world": {"obstacles": 5}}}, r"`world\.empty_world\.obstacles` is not a key"),
        ({"world": {"empty_world": {"size": [12, 9]}}}, r"`world\.empty_world\.size` is not a key"),
        # unknown keys, at any level
        ({"namespace": True}, r"`namespace` is not a key"),
        ({"agents": {"rover1": {"platform": "x", "position": [0, 0]}}}, r"`agents\.rover1\.position` is not"),
        ({"network": {"port": 7448}}, r"`network\.port` is not a key"),
        # the firmware lives in the platform's agent.yaml
        ({"autopilot": {"px4": {"version": "v1.18.0-rc1"}}}, "agent.yaml"),
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


def test_invalid_agent_yaml(variant, platform):
    old = platform("old_px4", airframe=50000, version="v1.17.0")
    path = variant("oldpx4", agents={"rover1": {"platform": str(old)}})
    with pytest.raises(InvalidEnvironment, match=rf"{old / 'agent.yaml'}.*v1\.17\.0.*minimum is 1\.18"):
        Environment.load(path)
