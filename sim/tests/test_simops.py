"""A scenario turns into a bundle: world with the agents in it, merged bridge, compose."""

import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import simops
import yaml
from simops import build, default_tag, host_env, load, parse_tags, parse_version, quaternion

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/rover_room.yaml"
RC1 = "fca3df865af36124a28c9d607e850f111dbaaea9"  # the commit v1.18.0-rc1 points to


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Answer `git ls-remote` from LS_REMOTE: unit tests never reach the PX4 repository."""
    monkeypatch.setattr(simops, "ls_remote", lambda _repo: LS_REMOTE)


def test_rover_room_bundle():
    spec = build(load(SCENARIO))
    bundle = ROOT / "build/rover_room"
    assert (bundle / "platforms/rover_differential_lidar_px4/model.sdf").exists()
    # its meshes come from the plain platform, model://rover_differential_lidar/meshes/...
    assert (bundle / "platforms/rover_differential_lidar/meshes").is_dir()

    # first the world, then the agents: the world file stays empty, spawn.sh adds them
    assert ET.parse(bundle / "worlds/room.sdf").find("world/include") is None
    spawn = (bundle / "spawn.sh").read_text()
    assert "W=room" in spawn
    assert 'spawn rover1 \'sdf_filename: "/sim/platforms/rover_differential_lidar_px4/model.sdf"' in spawn
    assert "position: {x: 0, y: 0, z: 0.2}" in spawn
    assert spec["services"]["px4-rover1"]["depends_on"]["spawn"]["condition"] == "service_completed_successfully"

    px4 = spec["services"]["px4-rover1"]["environment"]
    assert px4["PX4_GZ_WORLD"] == "room"
    assert px4["PX4_GZ_MODEL_NAME"] == "rover1"
    assert px4["PX4_SYS_AUTOSTART"] == "50000"  # from agent.yaml
    assert "PX4_ZENOH_NAMESPACE" not in px4
    assert {e["ros_topic_name"] for e in yaml.safe_load((bundle / "bridge.yaml").read_text())} == {
        "/clock",
        "/scan",
        "/scan/points",
        "/ground_truth",
    }
    # every gz peer in the scenario shares one partition, named after it
    parts = {s["environment"]["GZ_PARTITION"] for n, s in spec["services"].items() if n != "zenoh-router"}
    assert parts == {"rover_room"}


def test_two_agents_namespaced(tmp_path):
    sc = yaml.safe_load(SCENARIO.read_text())
    sc |= {"name": "rover_pair", "namespaces": True}
    sc["agents"]["rover2"] = {**sc["agents"]["rover1"], "pose": [2, 0, 0.2]}
    path = tmp_path / "pair.yaml"
    sc["agents"]["rover1"]["platform"] = sc["agents"]["rover2"]["platform"] = str(
        ROOT / "platforms/rover_differential_lidar_px4"
    )
    path.write_text(yaml.safe_dump(sc))

    spec = build(load(path))
    bundle = ROOT / "build/rover_pair"
    assert spec["services"]["px4-rover2"]["environment"]["PX4_INSTANCE"] == "1"
    assert spec["services"]["px4-rover2"]["environment"]["PX4_ZENOH_NAMESPACE"] == "rover2"

    assert (
        '"/sim/platforms/rover_differential_lidar_px4.rover2/model.sdf", name: "rover2"'
        in (bundle / "spawn.sh").read_text()
    )
    model = ET.parse(bundle / "platforms/rover_differential_lidar_px4.rover2/model.sdf")
    assert model.findtext(".//sensor/topic") == "/rover2/scan"
    assert model.findtext(".//odom_topic") == "/rover2/ground_truth"

    ros = sorted(e["ros_topic_name"] for e in yaml.safe_load((bundle / "bridge.yaml").read_text()))
    assert ros[0] == "/clock"
    assert "/rover1/scan" in ros
    assert "/rover2/scan/points" in ros
    assert ros.count("/clock") == 1


def variant(tmp_path: Path, name: str, **keys) -> Path:
    """rover_room with some keys replaced, written to tmp_path; the platform path stays absolute."""
    sc = yaml.safe_load(SCENARIO.read_text()) | {"name": name} | keys
    for agent in sc.get("agents", {}).values():
        agent["platform"] = str(ROOT / "platforms/rover_differential_lidar_px4")
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(sc))
    return path


def test_scenario_defaults(tmp_path):
    path = variant(tmp_path, "defaults")
    sc = yaml.safe_load(path.read_text())
    del sc["namespaces"], sc["network"]
    path.write_text(yaml.safe_dump(sc))
    loaded = load(path)
    assert loaded["namespaces"] is False
    assert loaded["network"]["router_port"] == 7447


def test_paths_relative_to_scenario_file(tmp_path, monkeypatch):
    sc = yaml.safe_load(SCENARIO.read_text())
    platform = ROOT / "platforms/rover_differential_lidar_px4"
    sc["agents"]["rover1"]["platform"] = os.path.relpath(platform, tmp_path)
    (tmp_path / "rel.yaml").write_text(yaml.safe_dump(sc))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert load(Path("../rel.yaml"))["agents"]["rover1"]["platform"] == platform


def test_several_agents_need_namespaces(tmp_path):
    agents = {"rover1": {"platform": "x"}, "rover2": {"platform": "x", "pose": [2, 0, 0.2]}}
    with pytest.raises(SystemExit, match="namespaces: true"):
        load(variant(tmp_path, "pair", agents=agents, namespaces=False))


def test_old_robots_key(tmp_path):
    sc = yaml.safe_load(SCENARIO.read_text())
    path = tmp_path / "old.yaml"
    path.write_text(yaml.safe_dump({**sc, "robots": sc.pop("agents")}))
    with pytest.raises(SystemExit, match="agents:"):
        load(path)


def test_same_seed_same_room(tmp_path):
    path = variant(tmp_path, "seeded")
    build(load(path))
    first = (ROOT / "build/seeded/worlds/room.sdf").read_bytes()
    build(load(path))
    assert (ROOT / "build/seeded/worlds/room.sdf").read_bytes() == first


def test_rebuild_drops_stale_files(tmp_path):
    path = variant(tmp_path, "stale")
    build(load(path))
    stale = ROOT / "build/stale/leftover.txt"
    stale.write_text("from an earlier build")
    build(load(path))
    assert not stale.exists()


def test_world_without_name(tmp_path):
    sdf = tmp_path / "nameless.sdf"
    sdf.write_text('<sdf version="1.9"><world></world></sdf>')
    with pytest.raises(SystemExit, match=r"nameless\.sdf"):
        build(load(variant(tmp_path, "nameless", world={"file": str(sdf)})))


def test_compose_wiring():
    spec = build(load(SCENARIO))
    services = spec["services"]
    # the world restarting takes the agents with it: spawn adds them again, PX4 reattaches
    for name in ("spawn", "px4-rover1"):
        assert services[name]["depends_on"]["world"] == {"condition": "service_started", "restart": True}
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{RC1[:12]}"  # rover_room: v1.18.0-rc1
    assert spec["name"] == "rover_room"
    assert services["zenoh-router"]["ports"] == ["7447:7447/tcp", "7447:7447/udp"]


def test_host_env(tmp_path):
    env = host_env(load(SCENARIO))
    assert env["GZ_PARTITION"] == "rover_room"
    assert env["GZ_TRANSPORT_IMPLEMENTATION"] == "zenoh"
    for key in ("GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE", "ZENOH_CONFIG_OVERRIDE"):
        assert "tcp/localhost:7447" in env[key]
    moved = host_env(load(variant(tmp_path, "moved", network={"router_port": 7448})))
    for key in ("GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE", "ZENOH_CONFIG_OVERRIDE"):
        assert "tcp/localhost:7448" in moved[key]


@pytest.mark.parametrize(
    ("rpy", "expected"),
    [
        ((0, 0, 0), (0, 0, 0, 1)),
        ((0, 0, math.pi / 2), (0, 0, math.sqrt(0.5), math.sqrt(0.5))),
        ((math.pi / 2, 0, 0), (math.sqrt(0.5), 0, 0, math.sqrt(0.5))),
        # roll 90 then pitch 90 about the fixed axes (ROS rpy is extrinsic x-y-z)
        ((math.pi / 2, math.pi / 2, 0), (0.5, 0.5, -0.5, 0.5)),
    ],
)
def test_quaternion(rpy, expected):
    assert quaternion(*rpy) == pytest.approx(expected, abs=1e-12)


LS_REMOTE = """\
a5eb12d2ab591251faa009f76b2685b8cc64405d\trefs/tags/v1.17.0
d6f12ad1c4f70ad3230afd7d86e971421e02fef4\trefs/tags/v1.17.0^{}
1111111111111111111111111111111111111111\trefs/tags/v1.18.0-beta2
ac17467e8a5b2acce94555c77ebb2a1c2e5a6452\trefs/tags/v1.18.0-rc1
fca3df865af36124a28c9d607e850f111dbaaea9\trefs/tags/v1.18.0-rc1^{}
2222222222222222222222222222222222222222\trefs/tags/v1.18.0-beta1-foo
"""


def test_version_order():
    order = ["v1.17.0", "v1.18.0-alpha1", "v1.18.0-beta2", "v1.18.0-beta10", "v1.18.0-rc1", "v1.18.0"]
    assert sorted(order, key=lambda v: parse_version(v) or ()) == order
    assert parse_version("1.18.0") == parse_version("v1.18.0")
    assert parse_version("v1.18.0-beta1-foo") is None
    assert parse_version("main") is None


def test_parse_tags():
    tags = parse_tags(LS_REMOTE)
    assert tags["v1.18.0-rc1"] == "fca3df865af36124a28c9d607e850f111dbaaea9"  # peeled: the commit
    assert tags["v1.18.0-beta2"] == "1" * 40  # lightweight: the commit itself
    assert tags["v1.17.0"] == "d6f12ad1c4f70ad3230afd7d86e971421e02fef4"


def test_default_tag():
    tags = parse_tags(LS_REMOTE)
    assert default_tag(tags) == "v1.18.0-rc1"  # no stable 1.18 yet: newest pre-release
    tags |= {"v1.18.0": "3" * 40, "v1.18.1-rc1": "4" * 40}
    assert default_tag(tags) == "v1.18.0"  # a release wins over any pre-release
    assert default_tag({"v1.17.0": "5" * 40}) is None


@pytest.mark.parametrize(
    ("px4", "message"),
    [
        ({"ref": "4dbd2e069a5c30c2e53e47e842095d2576dc38c4"}, "`version`.*`commit`"),
        ({"version": "v1.18.0-rc1", "commit": "a" * 40}, "not both"),
        ({"commit": "4dbd2e0"}, "full 40-character SHA"),
        ({"version": "latest"}, "not a PX4 version"),
        ({"version": "v1.17.0"}, r"v1\.17\.0 is not supported, the minimum is 1\.18"),
    ],
)
def test_px4_keys_rejected(tmp_path, px4, message):
    with pytest.raises(SystemExit, match=message):
        load(variant(tmp_path, "px4keys", autopilot={"px4": px4}))


@pytest.mark.parametrize("px4", [{}, {"version": "1.18.0-rc1"}, {"version": "v1.19.0"}, {"commit": "a" * 40}])
def test_px4_keys_accepted(tmp_path, px4):
    assert load(variant(tmp_path, "px4keys", autopilot={"px4": px4}))["autopilot"]["px4"] == px4


def test_no_autopilot_key(tmp_path):
    path = variant(tmp_path, "noautopilot")
    sc = yaml.safe_load(path.read_text())
    del sc["autopilot"]
    path.write_text(yaml.safe_dump(sc))
    assert load(path)["autopilot"] == {"px4": {}}


@pytest.mark.parametrize("version", ["v1.18.0-rc1", "1.18.0-rc1"])
def test_version_resolves_to_its_commit(tmp_path, version):
    spec = build(load(variant(tmp_path, "byversion", autopilot={"px4": {"version": version}})))
    px4 = spec["services"]["px4-rover1"]
    assert px4["image"] == f"simops-sandbox-px4:{RC1[:12]}"
    assert px4["build"]["args"]["PX4_REF"] == "v1.18.0-rc1"


def test_default_firmware(tmp_path):
    spec = build(load(variant(tmp_path, "bydefault", autopilot={"px4": {}})))
    assert spec["services"]["px4-rover1"]["build"]["args"]["PX4_REF"] == "v1.18.0-rc1"


def test_commit_builds_offline(tmp_path, monkeypatch):
    def offline(_repo):
        raise AssertionError("a commit must not need the network")

    monkeypatch.setattr(simops, "ls_remote", offline)
    commit = "4dbd2e069a5c30c2e53e47e842095d2576dc38c4"
    spec = build(load(variant(tmp_path, "bycommit", autopilot={"px4": {"commit": commit}})))
    px4 = spec["services"]["px4-rover1"]
    assert px4["image"] == "simops-sandbox-px4:4dbd2e069a5c"
    assert px4["build"]["args"]["PX4_REF"] == commit


def test_unknown_version(tmp_path):
    with pytest.raises(SystemExit, match=r"v1\.18\.7: no such tag in https://github.com/PX4/PX4-Autopilot.git"):
        build(load(variant(tmp_path, "unknown", autopilot={"px4": {"version": "v1.18.7"}})))
