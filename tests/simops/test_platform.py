"""Platforms: one document, in platform.yaml or inline, laid over a base (specs: platform, autopilot)."""

from pathlib import Path

import pytest
import yaml

from simops.firmware import PX4Firmware
from simops.platform import Platform

PX4_PLATFORM = Path(__file__).resolve().parent / "platforms/rover_differential_lidar_px4"  # the tests' own copy
ENVIRONMENTS = Path(__file__).resolve().parent / "environments"
RC1 = "fca3df865af36124a28c9d607e850f111dbaaea9"
SCAN = {
    "ros_topic_name": "/scan",
    "gz_topic_name": "/scan",
    "ros_type_name": "sensor_msgs/msg/LaserScan",
    "gz_type_name": "gz.msgs.LaserScan",
    "direction": "GZ_TO_ROS",
}


@pytest.fixture(scope="module")
def rover_bridge() -> list[dict]:
    """Give the PX4 platform's bridge entries, as its bridge.yaml has them."""
    return yaml.safe_load((PX4_PLATFORM / "bridge.yaml").read_text())


def over_rover(**keys: object) -> Platform:
    """Parse an inline platform written next to the test environments, laid over the PX4 platform."""
    return Platform.parse({"base": "../platforms/rover_differential_lidar_px4", **keys}, here=ENVIRONMENTS)


@pytest.mark.parametrize(
    ("px4", "message"),
    [
        ({}, r"autopilot\.px4\.airframe: Field required"),
        ({"airframe": 50000, "ref": RC1}, "`version`.*`commit`"),
        ({"airframe": 50000, "version": "v1.18.0-rc1", "commit": RC1}, "not both"),
        ({"airframe": 50000, "commit": "4dbd2e0"}, "full 40-character SHA"),
        ({"airframe": 50000, "version": "latest"}, "not a PX4 version"),
        ({"airframe": 50000, "version": "v1.17.0"}, r"v1\.17\.0 is not supported, the minimum is 1\.18"),
        ({"airframe": 50000, "gains": 1}, r"`autopilot\.px4\.gains` is not a key a platform defines"),
    ],
)
def test_rejected(platform, px4, message):
    with pytest.raises(ValueError, match=message) as e:
        platform(**px4)
    assert str(e.value).startswith(str(PX4_PLATFORM / "platform.yaml"))


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"model": "model.sdf", "bridge": []}, r"autopilot: Field required"),
        ({"bridge": [], "autopilot": {"px4": {"airframe": 1}}}, r"model: Field required"),
        ({"model": "model.sdf", "autopilot": {"px4": {"airframe": 1}}}, r"bridge: Field required"),
        (
            {"model": "nowhere.sdf", "bridge": [], "autopilot": {"px4": {"airframe": 1}}},
            r"nowhere\.sdf is not a file",
        ),
        ({"model": "model.sdf", "brige": [], "autopilot": {"px4": {"airframe": 1}}}, r"`brige` is not a key"),
    ],
)
def test_document_rejected(document, message):
    with pytest.raises(ValueError, match=message):
        Platform.parse(document, here=PX4_PLATFORM)


@pytest.mark.parametrize("firmware", [{}, {"version": "1.18.0-rc1"}, {"version": "v1.19.0"}, {"commit": RC1}])
def test_accepted(platform, firmware):
    px4 = platform(airframe=4001, **firmware).px4
    assert px4.airframe == 4001
    assert px4.firmware == PX4Firmware(**firmware)


def test_px4_platform(rover_bridge):
    rover = Platform.load(PX4_PLATFORM)
    assert (rover.px4.airframe, rover.px4.version) == (50000, "v1.18.0-rc1")
    assert rover.model == PX4_PLATFORM / "model.sdf"
    assert rover.name == "rover_differential_lidar_px4"
    assert rover.bridge == rover_bridge


def test_bridge_inline_or_in_a_file(rover_bridge):
    autopilot = {"px4": {"airframe": 50000}}
    in_file = Platform.parse(
        {"model": "model.sdf", "bridge": "bridge.yaml", "autopilot": autopilot}, here=PX4_PLATFORM
    )
    inline = Platform.parse(
        {"model": "model.sdf", "bridge": rover_bridge, "autopilot": autopilot}, here=PX4_PLATFORM
    )
    assert in_file == inline


def test_inline_model_path():
    document = {"model": "../platforms/rover_differential_lidar_px4/model.sdf", "bridge": []}
    rover = Platform.parse(document | {"autopilot": {"px4": {"airframe": 50000}}}, here=ENVIRONMENTS)
    assert rover.model == PX4_PLATFORM / "model.sdf"


def test_base_alone_is_the_base():
    assert over_rover() == Platform.load(PX4_PLATFORM)


def test_another_firmware_over_the_base(rover_bridge):
    rover = over_rover(autopilot={"px4": {"version": "v1.18.0"}})
    assert rover.model == PX4_PLATFORM / "model.sdf"  # the base's path, not one next to the environments
    assert rover.bridge == rover_bridge
    assert (rover.px4.airframe, rover.px4.version) == (50000, "v1.18.0")


def test_bridge_replaced():
    assert over_rover(bridge=[SCAN]).bridge == [SCAN]


@pytest.mark.parametrize("side", ["gz_topic_name", "ros_topic_name"])
def test_clock_is_the_worlds(side):
    with pytest.raises(ValueError, match=r"bridge: `/clock` is the world's"):
        over_rover(bridge=[SCAN | {side: "/clock"}])


def test_key_removed():
    with pytest.raises(
        ValueError, match=r"base .*rover_differential_lidar_px4/platform\.yaml: bridge: Field required"
    ):
        over_rover(bridge=None)


@pytest.mark.generating_files
def test_invalid_value_from_the_base(platform_dir, tmp_path):
    old = platform_dir("old", airframe=50000, version="v1.17.0")
    with pytest.raises(ValueError, match=rf"^base {old / 'platform.yaml'}: .*1\.17\.0.*minimum is 1\.18"):
        Platform.parse({"base": "platforms/old"}, here=tmp_path)


@pytest.mark.generating_files
def test_base_of_a_base(platform_dir, tmp_path):
    platform_dir("a", airframe=1, version="v1.18.0-rc1")
    platform_dir("b", {"base": "../a", "autopilot": {"px4": {"airframe": 2}}})
    rover = Platform.parse({"base": "platforms/b", "autopilot": {"px4": {"version": "v1.18.0"}}}, here=tmp_path)
    assert (rover.px4.airframe, rover.px4.version) == (2, "v1.18.0")


@pytest.mark.generating_files
def test_cycle_of_bases(platform_dir):
    a = platform_dir("a", {"base": "../b"})
    b = platform_dir("b", {"base": "../a"})
    with pytest.raises(ValueError, match="cycle of bases") as e:
        Platform.load(a.resolve())
    assert f"{a.resolve()} -> {b.resolve()} -> {a.resolve()}" in str(e.value)


@pytest.mark.generating_files
def test_old_agent_yaml(tmp_path):
    (tmp_path / "agent.yaml").write_text("autopilot: {px4: {airframe: 50000}}")
    with pytest.raises(ValueError, match=r"agent\.yaml is now platform\.yaml"):
        Platform.load(tmp_path)


@pytest.mark.generating_files
def test_no_platform_yaml(tmp_path):
    with pytest.raises(ValueError, match=r"has no platform\.yaml"):
        Platform.load(tmp_path)
