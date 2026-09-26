"""A scenario turns into a bundle: world with the robots in it, merged bridge, compose."""

import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from simops import build, load

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/rover_room.yaml"


def test_rover_room_bundle():
    spec = build(load(SCENARIO))
    bundle = ROOT / "build/rover_room"
    assert (bundle / "platforms/rover_differential_lidar_px4/model.sdf").exists()
    # its meshes come from the plain platform, model://rover_differential_lidar/meshes/...
    assert (bundle / "platforms/rover_differential_lidar/meshes").is_dir()

    # first the world, then the robots: the world file stays empty, spawn.sh adds them
    assert ET.parse(bundle / "worlds/room.sdf").find("world/include") is None
    spawn = (bundle / "spawn.sh").read_text()
    assert "W=room" in spawn
    assert 'spawn rover1 \'sdf_filename: "/sim/platforms/rover_differential_lidar_px4/model.sdf"' in spawn
    assert "position: {x: 0, y: 0, z: 0.2}" in spawn
    assert spec["services"]["px4-rover1"]["depends_on"]["spawn"]["condition"] == "service_completed_successfully"

    px4 = spec["services"]["px4-rover1"]["environment"]
    assert px4["PX4_GZ_WORLD"] == "room"
    assert px4["PX4_GZ_MODEL_NAME"] == "rover1"
    assert px4["PX4_SYS_AUTOSTART"] == "50000"  # from platform.yaml
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


def test_two_robots_namespaced(tmp_path):
    sc = yaml.safe_load(SCENARIO.read_text())
    sc |= {"name": "rover_pair", "namespaces": True}
    sc["robots"]["rover2"] = {**sc["robots"]["rover1"], "pose": [2, 0, 0.2]}
    path = tmp_path / "pair.yaml"
    sc["robots"]["rover1"]["platform"] = sc["robots"]["rover2"]["platform"] = str(
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
