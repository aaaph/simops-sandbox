"""Platforms: agent.yaml names the PX4 airframe and firmware (spec: autopilot)."""

from pathlib import Path

import pytest

from simops.firmware import PX4Firmware
from simops.platform import Platform

PX4_PLATFORM = Path(__file__).resolve().parents[2] / "platforms/rover_differential_lidar_px4"
RC1 = "fca3df865af36124a28c9d607e850f111dbaaea9"


@pytest.mark.parametrize(
    ("px4", "message"),
    [
        ({}, r"autopilot\.px4\.airframe: Field required"),
        ({"airframe": 50000, "ref": RC1}, "`version`.*`commit`"),
        ({"airframe": 50000, "version": "v1.18.0-rc1", "commit": RC1}, "not both"),
        ({"airframe": 50000, "commit": "4dbd2e0"}, "full 40-character SHA"),
        ({"airframe": 50000, "version": "latest"}, "not a PX4 version"),
        ({"airframe": 50000, "version": "v1.17.0"}, r"v1\.17\.0 is not supported, the minimum is 1\.18"),
        ({"airframe": 50000, "gains": 1}, r"`autopilot\.px4\.gains` is not a key agent\.yaml defines"),
    ],
)
def test_rejected(platform, px4, message):
    path = platform("broken", **px4)
    with pytest.raises(ValueError, match=message) as e:
        Platform.load(path)
    assert str(e.value).startswith(str(path / "agent.yaml"))


def test_no_autopilot(platform):
    path = platform("bare", airframe=50000)
    (path / "agent.yaml").write_text("{}")
    with pytest.raises(ValueError, match=r"autopilot: Field required"):
        Platform.load(path)


@pytest.mark.parametrize("firmware", [{}, {"version": "1.18.0-rc1"}, {"version": "v1.19.0"}, {"commit": RC1}])
def test_accepted(platform, firmware):
    px4 = Platform.load(platform("ok", airframe=4001, **firmware)).px4
    assert px4.airframe == 4001
    assert px4.firmware == PX4Firmware(**firmware)


def test_px4_platform():
    px4 = Platform.load(PX4_PLATFORM).px4
    assert (px4.airframe, px4.version) == (50000, "v1.18.0-rc1")
