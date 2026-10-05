"""An environment turns into a bundle: world, merged bridge, spawn script, compose (spec: bundle)."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simops.bundle import build
from simops.environment import Environment
from simops.world import CLOCK
from worldgen.world import SdfWorld, StartMarker

pytestmark = pytest.mark.usefixtures("no_network")

ENVIRONMENTS = Path(__file__).resolve().parent / "environments"
SMALL_ROOM = ENVIRONMENTS / "small_room.yaml"
ROVER_DIR = "../platforms/rover_differential_lidar_px4"  # from the test environments
BOX_MODEL = """<sdf version="1.9"><model name="box"><link name="base"><collision name="c">
<geometry><box><size>0.5 0.4 0.2</size></box></geometry></collision></link></model></sdf>"""
RC1 = "fca3df865af36124a28c9d607e850f111dbaaea9"  # the commit v1.18.0-rc1 points to
COMMIT = "4dbd2e069a5c30c2e53e47e842095d2576dc38c4"


def test_rover_room_bundle(environment):
    bundle = build(environment("rover_room"))
    services = bundle.compose["services"]
    assert set(bundle.platforms) == {"rover_differential_lidar_px4"}  # its meshes are its own

    # first the world, then the agents: the world holds none, spawn.sh adds them
    assert "W=field" in bundle.spawn  # the open field of the test environment
    assert 'spawn rover1 \'sdf_filename: "/sim/platforms/rover_differential_lidar_px4/model.sdf"' in bundle.spawn
    assert "position: {x: 0.0, y: 0.0, z: 0.2}" in bundle.spawn
    assert services["px4-rover1"]["depends_on"]["spawn"]["condition"] == "service_completed_successfully"

    px4 = services["px4-rover1"]["environment"]
    assert px4["PX4_GZ_WORLD"] == "field"
    assert px4["PX4_GZ_MODEL_NAME"] == "rover1"
    assert px4["PX4_SYS_AUTOSTART"] == "50000"  # from the platform's platform.yaml
    assert "PX4_ZENOH_NAMESPACE" not in px4
    assert {e["ros_topic_name"] for e in bundle.bridge} == {"/clock", "/scan", "/scan/points", "/ground_truth"}
    # every gz peer in the session shares one partition, named after it
    parts = {s["environment"]["GZ_PARTITION"] for n, s in services.items() if n != "zenoh-router"}
    assert parts == {"rover_room"}


@pytest.mark.generating_files
def test_bundle_on_disk(tmp_path):
    out = build(Environment.load(SMALL_ROOM)).write(tmp_path / "small_room")
    assert (out / "platforms/rover_differential_lidar_px4/model.sdf").exists()
    assert (out / "platforms/rover_differential_lidar_px4/meshes").is_dir()
    assert ET.parse(out / "worlds/room.sdf").find("world/include") is None
    assert "W=room" in (out / "spawn.sh").read_text()
    assert (out / "compose.yaml").exists()
    assert (out / "bridge.yaml").exists()


def test_two_agents_namespaced(environment):
    two = {"rover1": {"platform": "x", "pose": [0, 0, 0.2]}, "rover2": {"platform": "x", "pose": [2, 0, 0.2]}}
    bundle = build(environment("rover_pair", namespaces=True, agents=two))
    services = bundle.compose["services"]
    assert services["px4-rover2"]["environment"]["PX4_INSTANCE"] == "1"
    assert services["px4-rover2"]["environment"]["PX4_ZENOH_NAMESPACE"] == "rover2"

    assert '"/sim/platforms/rover_differential_lidar_px4.rover2/model.sdf", name: "rover2"' in bundle.spawn
    model = ET.fromstring(bundle.models["rover_differential_lidar_px4.rover2/model.sdf"])
    assert model.findtext(".//sensor/topic") == "/rover2/scan"
    assert model.findtext(".//odom_topic") == "/rover2/ground_truth"

    ros = sorted(e["ros_topic_name"] for e in bundle.bridge)
    assert ros[0] == "/clock"
    assert "/rover1/scan" in ros
    assert "/rover2/scan/points" in ros
    assert ros.count("/clock") == 1
    # each agent's entries are rewritten in its own copy, the platform's stay as they are
    assert "/scan" in {e["ros_topic_name"] for e in bundle.environment.agents["rover2"].platform.bridge}


def test_clock_first(environment):
    bridge = build(environment("clocked")).bridge
    assert bridge[0] == CLOCK  # the world's
    assert [e["ros_topic_name"] for e in bridge[1:]] == ["/scan", "/scan/points", "/ground_truth"]


def test_clock_without_agent_topics(environment):
    silent = {"rover1": {"platform": {"base": ROVER_DIR, "bridge": []}}}
    assert build(environment("silent", agents=silent)).bridge == [CLOCK]


@pytest.mark.parametrize("form", ["inline", "base"])
def test_three_forms_one_bundle(form):
    directory = build(Environment.load(ENVIRONMENTS / "rover_platform_dir.yaml"))
    other = build(Environment.load(ENVIRONMENTS / f"rover_platform_{form}.yaml"))
    assert dict(other) == dict(directory)  # every field of the bundle; as dicts, a failure names the fields


def test_one_model_directory_two_agents(environment):
    agents = {
        "rover1": {"platform": ROVER_DIR},
        "rover11": {"platform": {"base": ROVER_DIR, "bridge": []}, "pose": [2, 0, 0.2]},
    }
    platforms = build(environment("shared", namespaces=True, agents=agents)).platforms
    assert set(platforms) == {f"rover_differential_lidar_px4{copy}" for copy in ("", ".rover1", ".rover11")}


def test_firmware_over_the_base(environment):
    agents = {
        "rover1": {"platform": ROVER_DIR},
        # the base names a version: null removes it, or version and commit would both be set
        "rover11": {"platform": {"base": ROVER_DIR, "autopilot": {"px4": {"version": None, "commit": COMMIT}}}},
    }
    services = build(environment("refirmed", namespaces=True, agents=agents)).compose["services"]
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{RC1[:12]}"
    assert services["px4-rover11"]["image"] == f"simops-sandbox-px4:{COMMIT[:12]}"
    assert {services[f"px4-{a}"]["environment"]["PX4_SYS_AUTOSTART"] for a in agents} == {"50000"}


@pytest.mark.generating_files
def test_model_not_named_model_sdf(environment, tmp_path):
    (tmp_path / "husky").mkdir()
    (tmp_path / "husky/husky.sdf").write_text(BOX_MODEL)
    husky = {"model": str(tmp_path / "husky/husky.sdf"), "bridge": [], "autopilot": {"px4": {"airframe": 50000}}}
    bundle = build(environment("husky", agents={"rover1": {"platform": husky}}))
    assert bundle.platforms == {"husky": tmp_path / "husky"}
    assert '"/sim/platforms/husky/husky.sdf"' in bundle.spawn


@pytest.mark.generating_files
def test_two_model_directories_one_name(environment, tmp_path):
    agents = {}
    for i, side in enumerate(("a", "b")):
        (tmp_path / side / "rover").mkdir(parents=True)
        (tmp_path / side / "rover/model.sdf").write_text(BOX_MODEL)
        model = str(tmp_path / side / "rover/model.sdf")
        agents[f"rover{i}"] = {"platform": {"model": model, "bridge": [], "autopilot": {"px4": {"airframe": 1}}}}
    with pytest.raises(SystemExit, match=rf"{tmp_path / 'a/rover'} and {tmp_path / 'b/rover'}"):
        build(environment("clash", namespaces=True, agents=agents))


def test_empty_world_is_open(environment):
    world = build(environment("empty", world={"empty_world": None})).world
    assert isinstance(world, SdfWorld)
    assert [type(p) for p in world.parts] == [StartMarker]


def test_same_seed_same_room(environment):
    seeded = environment("seeded", world={"generate_room": {"seed": 3, "size": [6, 5], "obstacles": 4}})
    bundle = build(seeded)
    assert bundle.world_name == "room"
    assert bundle.world == build(seeded).world


@pytest.mark.generating_files
def test_rebuild_drops_stale_files(environment, tmp_path):
    bundle = build(environment("stale"))
    stale = bundle.write(tmp_path / "stale") / "leftover.txt"
    stale.write_text("from an earlier build")
    bundle.write(tmp_path / "stale")
    assert not stale.exists()


@pytest.mark.generating_files
def test_world_without_name(environment, tmp_path):
    sdf = tmp_path / "nameless.sdf"
    sdf.write_text('<sdf version="1.9"><world></world></sdf>')
    with pytest.raises(SystemExit, match=rf"^{sdf}: "):
        build(environment("nameless", world={"file": str(sdf)}))


def test_compose_wiring(environment):
    compose = build(environment("rover_room")).compose
    services = compose["services"]
    # the world restarting takes the agents with it: spawn adds them again, PX4 reattaches
    for name in ("spawn", "px4-rover1"):
        assert services[name]["depends_on"]["world"] == {"condition": "service_started", "restart": True}
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{RC1[:12]}"  # rover_room: v1.18.0-rc1
    assert compose["name"] == "rover_room"
    assert services["zenoh-router"]["ports"] == ["7447:7447/tcp", "7447:7447/udp"]  # no MAVLink port


def test_mavlink_to_the_host(environment):
    one = build(environment("mav", network={"mavlink_port": 14590})).compose["services"]
    assert one["px4-rover1"]["environment"]["PX4_MAVLINK_PORT"] == "14590"
    two = {"rover1": {"platform": "x", "pose": [0, 0, 0.2]}, "rover2": {"platform": "x", "pose": [2, 0, 0.2]}}
    pair = build(environment("mav_pair", namespaces=True, agents=two)).compose["services"]
    assert [pair[f"px4-{a}"]["environment"]["PX4_MAVLINK_PORT"] for a in two] == ["14540", "14541"]
    assert pair["world"]["labels"]["simops.mavlink_ports"] == "14540-14541"


@pytest.mark.parametrize(
    ("px4", "ref", "image"),
    [
        ({"version": "v1.18.0-rc1"}, "v1.18.0-rc1", RC1[:12]),
        ({"version": "1.18.0-rc1"}, "v1.18.0-rc1", RC1[:12]),
        ({}, "v1.18.0-rc1", RC1[:12]),
        ({"commit": COMMIT}, COMMIT, COMMIT[:12]),
    ],
)
def test_firmware_names_the_image(environment, platform, px4, ref, image):
    rover = {"platform": platform(airframe=50000, **px4), "pose": [0, 0, 0.2]}
    px4_service = build(environment("firmware", agents={"rover1": rover})).compose["services"]["px4-rover1"]
    assert px4_service["image"] == f"simops-sandbox-px4:{image}"
    assert px4_service["build"]["args"]["PX4_REF"] == ref


def test_two_platforms_two_firmwares(environment, platform):
    agents = {
        "rover1": {"platform": platform(airframe=50000, version="v1.18.0-rc1")},
        "rover2": {"platform": platform(airframe=4001, commit=COMMIT), "pose": [2, 0, 0.2]},
    }
    services = build(environment("mixed", namespaces=True, agents=agents)).compose["services"]
    assert services["px4-rover1"]["image"] == f"simops-sandbox-px4:{RC1[:12]}"
    assert services["px4-rover2"]["image"] == f"simops-sandbox-px4:{COMMIT[:12]}"
    assert services["px4-rover2"]["environment"]["PX4_SYS_AUTOSTART"] == "4001"


@pytest.mark.parametrize("port", [7447, 7448])
def test_containers_carry_their_session(environment, port):
    services = build(environment("labelled", network={"router_port": port})).compose["services"]
    for spec in services.values():
        assert spec["labels"] == {
            "simops.session": "labelled",
            "simops.router_port": str(port),
            "simops.mavlink_ports": "14540-14540",
        }
