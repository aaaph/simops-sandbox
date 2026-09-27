"""A scenario turns into a bundle: world with the agents in it, merged bridge, compose."""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml
from simops import build, host_env, load

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/rover_room.yaml"


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
    ref = yaml.safe_load(SCENARIO.read_text())["autopilot"]["px4"]["ref"]
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{ref[:12]}"
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
