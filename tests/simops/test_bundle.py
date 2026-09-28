"""An environment turns into a bundle: world, merged bridge, spawn script, compose (spec: bundle)."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from simops.bundle import build
from simops.environment import Environment

pytestmark = pytest.mark.usefixtures("no_network")

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT = ROOT / "environments/rover_room.yaml"
RC1 = "fca3df865af36124a28c9d607e850f111dbaaea9"  # the commit v1.18.0-rc1 points to
COMMIT = "4dbd2e069a5c30c2e53e47e842095d2576dc38c4"


def test_rover_room_bundle():
    bundle = build(Environment.load(ENVIRONMENT))
    services = bundle.compose["services"]
    assert bundle.dir == ROOT / "build/rover_room"
    assert (bundle.dir / "platforms/rover_differential_lidar_px4/model.sdf").exists()
    # its meshes come from the plain platform, model://rover_differential_lidar/meshes/...
    assert (bundle.dir / "platforms/rover_differential_lidar/meshes").is_dir()

    # first the world, then the agents: the world file stays empty, spawn.sh adds them
    assert ET.parse(bundle.dir / "worlds/room.sdf").find("world/include") is None
    spawn = (bundle.dir / "spawn.sh").read_text()
    assert "W=room" in spawn
    assert 'spawn rover1 \'sdf_filename: "/sim/platforms/rover_differential_lidar_px4/model.sdf"' in spawn
    assert "position: {x: 0.0, y: 0.0, z: 0.2}" in spawn
    assert services["px4-rover1"]["depends_on"]["spawn"]["condition"] == "service_completed_successfully"

    px4 = services["px4-rover1"]["environment"]
    assert px4["PX4_GZ_WORLD"] == "room"
    assert px4["PX4_GZ_MODEL_NAME"] == "rover1"
    assert px4["PX4_SYS_AUTOSTART"] == "50000"  # from agent.yaml
    assert "PX4_ZENOH_NAMESPACE" not in px4
    assert {e["ros_topic_name"] for e in yaml.safe_load((bundle.dir / "bridge.yaml").read_text())} == {
        "/clock",
        "/scan",
        "/scan/points",
        "/ground_truth",
    }
    # every gz peer in the session shares one partition, named after it
    parts = {s["environment"]["GZ_PARTITION"] for n, s in services.items() if n != "zenoh-router"}
    assert parts == {"rover_room"}


def test_two_agents_namespaced(variant):
    two = {"rover1": {"platform": "x", "pose": [0, 0, 0.2]}, "rover2": {"platform": "x", "pose": [2, 0, 0.2]}}
    bundle = build(Environment.load(variant("rover_pair", namespaces=True, agents=two)))
    services = bundle.compose["services"]
    assert services["px4-rover2"]["environment"]["PX4_INSTANCE"] == "1"
    assert services["px4-rover2"]["environment"]["PX4_ZENOH_NAMESPACE"] == "rover2"

    assert (
        '"/sim/platforms/rover_differential_lidar_px4.rover2/model.sdf", name: "rover2"'
        in (bundle.dir / "spawn.sh").read_text()
    )
    model = ET.parse(bundle.dir / "platforms/rover_differential_lidar_px4.rover2/model.sdf")
    assert model.findtext(".//sensor/topic") == "/rover2/scan"
    assert model.findtext(".//odom_topic") == "/rover2/ground_truth"

    ros = sorted(e["ros_topic_name"] for e in yaml.safe_load((bundle.dir / "bridge.yaml").read_text()))
    assert ros[0] == "/clock"
    assert "/rover1/scan" in ros
    assert "/rover2/scan/points" in ros
    assert ros.count("/clock") == 1


def test_empty_world_is_open(variant):
    bundle = build(Environment.load(variant("empty", world={"empty_world": None})))
    sdf = ET.parse(bundle.dir / "worlds/room.sdf")
    names = {m.get("name") for m in sdf.findall("world/model")}
    assert {"start_marker", "ground_plane"} <= names
    assert not any(n.startswith(("wall_", "obs_")) for n in names)


def test_same_seed_same_room(variant):
    environment = Environment.load(variant("seeded"))
    first = (build(environment).dir / "worlds/room.sdf").read_bytes()
    assert (build(environment).dir / "worlds/room.sdf").read_bytes() == first


def test_rebuild_drops_stale_files(variant):
    environment = Environment.load(variant("stale"))
    stale = build(environment).dir / "leftover.txt"
    stale.write_text("from an earlier build")
    build(environment)
    assert not stale.exists()


def test_world_without_name(variant, tmp_path):
    sdf = tmp_path / "nameless.sdf"
    sdf.write_text('<sdf version="1.9"><world></world></sdf>')
    with pytest.raises(SystemExit, match=r"nameless\.sdf"):
        build(Environment.load(variant("nameless", world={"file": str(sdf)})))


def test_compose_wiring():
    compose = build(Environment.load(ENVIRONMENT)).compose
    services = compose["services"]
    # the world restarting takes the agents with it: spawn adds them again, PX4 reattaches
    for name in ("spawn", "px4-rover1"):
        assert services[name]["depends_on"]["world"] == {"condition": "service_started", "restart": True}
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{RC1[:12]}"  # rover_room: v1.18.0-rc1
    assert compose["name"] == "rover_room"
    assert services["zenoh-router"]["ports"] == ["7447:7447/tcp", "7447:7447/udp"]


@pytest.mark.parametrize(
    ("px4", "ref", "image"),
    [
        ({"version": "v1.18.0-rc1"}, "v1.18.0-rc1", RC1[:12]),
        ({"version": "1.18.0-rc1"}, "v1.18.0-rc1", RC1[:12]),
        ({}, "v1.18.0-rc1", RC1[:12]),
        ({"commit": COMMIT}, COMMIT, COMMIT[:12]),
    ],
)
def test_firmware_names_the_image(variant, platform, px4, ref, image):
    rover = {"platform": str(platform("px4", airframe=50000, **px4)), "pose": [0, 0, 0.2]}
    bundle = build(Environment.load(variant("firmware", agents={"rover1": rover})))
    px4_service = bundle.compose["services"]["px4-rover1"]
    assert px4_service["image"] == f"simops-sandbox-px4:{image}"
    assert px4_service["build"]["args"]["PX4_REF"] == ref


def test_two_platforms_two_firmwares(variant, platform):
    agents = {
        "rover1": {"platform": str(platform("rc1", airframe=50000, version="v1.18.0-rc1"))},
        "rover2": {"platform": str(platform("pinned", airframe=4001, commit=COMMIT)), "pose": [2, 0, 0.2]},
    }
    services = build(Environment.load(variant("mixed", namespaces=True, agents=agents))).compose["services"]
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{RC1[:12]}"
    assert services["px4-rover2"]["image"] == f"simops-sandbox-px4:{COMMIT[:12]}"
    assert services["px4-rover2"]["environment"]["PX4_SYS_AUTOSTART"] == "4001"
