"""The environment file: keys, defaults, paths, and every way loading refuses one (spec: environment)."""

from pathlib import Path

import pytest

from simops.environment import Environment, InvalidEnvironment
from simops.world import EmptySpec, RoomSpec, WorldFile

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENTS = Path(__file__).resolve().parent / "environments"  # the base of the `environment` fixture
PX4_PLATFORM = Path(__file__).resolve().parent / "platforms/rover_differential_lidar_px4"  # the tests' own copy
AUTOPILOT = {"px4": {"airframe": 50000}}
ROVER_DIR = "../platforms/rover_differential_lidar_px4"  # from the test environments


def test_defaults():
    agents = {"rover1": {"platform": str(PX4_PLATFORM)}}
    doc = {"name": "defaults", "world": {"empty_world": None}, "agents": agents}
    environment = Environment.parse(doc, base=ROOT, origin=Path("defaults.yaml"))
    assert environment.namespaces is False
    assert environment.network.router_port == 7447
    assert environment.network.mavlink_port == 14540


def test_mavlink_port(environment):
    network = environment("mav", network={"mavlink_port": 14590}).network
    assert (network.router_port, network.mavlink_port) == (7447, 14590)


def test_paths_relative_to_environment_file(monkeypatch):
    # small_room.yaml names ../platforms/...: right from its own directory, wrong from tests/
    monkeypatch.chdir(ROOT / "tests")
    environment = Environment.load(Path("simops/environments/small_room.yaml"))
    assert environment.agents["rover1"].platform.model == PX4_PLATFORM / "model.sdf"


def test_inline_platform_relative_to_environment_file(environment):
    inline = {"model": f"{ROVER_DIR}/model.sdf", "bridge": [], "autopilot": AUTOPILOT}
    rover = environment("inline", agents={"rover1": {"platform": inline}}).agents["rover1"].platform
    assert rover.model == PX4_PLATFORM / "model.sdf"


def test_directory_and_inline_side_by_side(environment):
    agents = {
        "rover1": {"platform": ROVER_DIR},
        "rover11": {"platform": {"base": ROVER_DIR}, "pose": [2, 0, 0.2]},
    }
    loaded = environment("both", namespaces=True, agents=agents).agents
    assert loaded["rover1"].platform == loaded["rover11"].platform


def test_world_sources(environment):
    room = environment("roomed", world={"generate_room": {"seed": 42, "size": [20, 16]}})
    assert room.world.source == RoomSpec(seed=42, size=(20, 16))
    ready = environment("filed", world={"file": "../worlds/ready.sdf"})  # relative to the environment file
    assert ready.world.source == WorldFile(path=(ENVIRONMENTS / "../worlds/ready.sdf").resolve())
    assert environment("emptied", world={"empty_world": None}).world.source == EmptySpec()


def test_partial_pose(environment):
    pose = environment("posed").agents["rover1"].pose
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
        # the firmware lives in the platform, in its platform.yaml or inline
        ({"autopilot": {"px4": {"version": "v1.18.0-rc1"}}}, r"`autopilot\.px4` of its platform\.yaml"),
        # an inline platform is checked like any other, and the message names the agent
        (
            {"agents": {"rover1": {"platform": {"model": "x.sdf", "brige": [], "autopilot": AUTOPILOT}}}},
            r"agents\.rover1\.platform: .*`brige` is not a key a platform defines",
        ),
        (
            {
                "agents": {
                    "rover1": {"platform": {"base": ROVER_DIR, "autopilot": {"px4": {"version": "v1.17.0"}}}}
                }
            },
            r"^rejected\.yaml: agents\.rover1\.platform: .*v1\.17\.0.*minimum is 1\.18",
        ),
    ],
)
def test_rejected(environment, keys, message):
    with pytest.raises(InvalidEnvironment, match=message):
        environment("rejected", **keys)


def test_old_robots_key(environment):
    with pytest.raises(InvalidEnvironment, match="agents:"):
        environment("old", robots={})


def test_message_names_the_file(environment):
    with pytest.raises(InvalidEnvironment, match=r"^named\.yaml: "):
        environment("named", namespace=True)


def test_unreadable_file(tmp_path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(InvalidEnvironment, match=rf"^{missing}: "):
        Environment.load(missing)


@pytest.mark.generating_files
def test_invalid_platform_yaml(environment, platform_dir):
    old = platform_dir("old_px4", airframe=50000, version="v1.17.0")
    with pytest.raises(InvalidEnvironment, match=rf"{old / 'platform.yaml'}: .*v1\.17\.0.*minimum is 1\.18"):
        environment("oldpx4", agents={"rover1": {"platform": str(old)}})


@pytest.mark.generating_files
def test_invalid_agent_yaml(environment, tmp_path):
    (tmp_path / "agent.yaml").write_text("autopilot: {px4: {airframe: 50000}}")
    with pytest.raises(InvalidEnvironment, match=rf"{tmp_path}: agent\.yaml is now platform\.yaml"):
        environment("oldagent", agents={"rover1": {"platform": str(tmp_path)}})
