"""A scenario: rover1 drives a 5 m square on an open field, by a MAVSDK mission.

A session in Docker, minutes, on images that already exist: `pixi run pytest -m scenario`.
MAVSDK listens where the agent's PX4 sends (host-access). Passes when the mission finishes in
time; no judge yet. The same square to run by hand: scenarios/square_mission.py.
"""

import asyncio
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from mavsdk_grpc import System
from mavsdk_grpc.mission import MissionItem, MissionPlan

from simops.environment import Environment
from simops.session import Session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

pytestmark = [pytest.mark.docker, pytest.mark.scenario]

ROOT = Path(__file__).resolve().parents[2]
PX4_PLATFORM = str(ROOT / "platforms/rover_differential_lidar_px4")
MAVLINK_PORT = 14800  # outside the lifecycle tests' ports
SIDE = 5.0  # m
METERS_PER_DEGREE = 111_320  # of latitude; flat earth, exact enough over a few metres
TIMEOUT = 300


def session(tmp_path: Path) -> Session:
    """Give an open field with rover1 at the origin, under its own name and ports."""
    sim = {
        "name": "t_square",
        "network": {"router_port": 7480, "mavlink_port": MAVLINK_PORT},
        "world": {"empty_world": None},
        "agents": {"rover1": {"platform": PX4_PLATFORM, "pose": [0, 0, 0.2]}},
    }
    path = tmp_path / "t_square.yaml"
    path.write_text(yaml.safe_dump(sim))
    return Session(Environment.load(path))


async def first[T](stream: AsyncIterator[T], until: Callable[[T], bool], within: float, what: str) -> T:
    """Wait for the first item of a MAVSDK stream that satisfies `until`; fail naming the last one seen."""
    last = None

    async def wait() -> T:
        nonlocal last
        async for last in stream:
            if until(last):
                return last
        pytest.fail(f"{what}: stream ended; last seen: {last}")

    try:
        return await asyncio.wait_for(wait(), within)
    except TimeoutError:
        pytest.fail(f"{what} not within {within:.0f} s; last seen: {last}")


def waypoint(latitude_deg: float, longitude_deg: float) -> MissionItem:
    """Give a ground waypoint: stop on it, PX4's own speed and acceptance radius, no camera or gimbal."""
    return MissionItem(
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        relative_altitude_m=0,
        speed_m_s=math.nan,
        is_fly_through=False,
        gimbal_pitch_deg=math.nan,
        gimbal_yaw_deg=math.nan,
        camera_action=MissionItem.CameraAction.NONE,
        loiter_time_s=math.nan,
        camera_photo_interval_s=math.nan,
        acceptance_radius_m=math.nan,
        yaw_deg=math.nan,
        camera_photo_distance_m=math.nan,
        vehicle_action=MissionItem.VehicleAction.NONE,
    )


async def drive_square(port: int) -> None:
    """Connect to rover1's PX4, wait until it can arm, drive the square from home back to home."""
    rover = System()
    try:  # returns only once mavsdk_server has heard the vehicle
        await asyncio.wait_for(rover.connect(system_address=f"udpin://0.0.0.0:{port}"), 60)
    except TimeoutError:
        pytest.fail(f"no vehicle heard on UDP port {port} within 60 s")
    await first(rover.core.connection_state(), lambda s: s.is_connected, 60, "rover1 connected")
    await first(
        rover.telemetry.health(),
        lambda h: h.is_global_position_ok and h.is_home_position_ok and h.is_armable,
        120,
        "rover1 armable with a global position and home",
    )
    home = await first(rover.telemetry.home(), lambda _: True, 10, "home position")

    north = SIDE / METERS_PER_DEGREE
    east = north / math.cos(math.radians(home.latitude_deg))
    corners = [(north, 0), (north, east), (0, east), (0, 0)]  # back home last
    plan = MissionPlan([waypoint(home.latitude_deg + n, home.longitude_deg + e) for n, e in corners])
    await rover.mission.upload_mission(plan)
    await rover.action.arm()
    await rover.mission.start_mission()
    await first(rover.mission.mission_progress(), lambda p: p.current == p.total, 180, "mission finished")
    assert await rover.mission.is_mission_finished()
    await rover.action.disarm()


def test_square(tmp_path):
    sim = session(tmp_path)
    try:
        assert sim.up(TIMEOUT) == 0
        asyncio.run(drive_square(MAVLINK_PORT))
    finally:
        sim.down()
