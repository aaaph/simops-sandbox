"""Scenario: rover1 drives a square from home back to home, by a MAVSDK mission.

Run by hand against a session that is up:

    pixi run simops up environments/rover_empty_world.yaml
    pixi run python scenarios/square_mission.py            # --port, --side
    pixi run simops down

Listens where the agent's PX4 sends its API link: the environment's network.mavlink_port
(14540 by default, + i for agent i). QGC on 14550 can watch at the same time.
"""

import argparse
import asyncio
import math
import time

from mavsdk_grpc import System
from mavsdk_grpc.mission import MissionItem, MissionPlan

METERS_PER_DEGREE = 111_320  # of latitude; flat earth, exact enough over a few metres


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


async def run_square(port: int, side: float) -> None:
    """Connect to the PX4 sending to `port`, wait until it can arm, drive the square, disarm."""
    rover = System()
    print(f"Connecting to the rover on udpin://0.0.0.0:{port} ...")
    await rover.connect(system_address=f"udpin://0.0.0.0:{port}")

    print("Waiting for the rover to connect...")
    async for state in rover.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    print("Waiting for a global position, home and arming checks...")
    async for health in rover.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok and health.is_armable:
            print("Ready to arm")
            break

    async for home in rover.telemetry.home():
        print(f"Home: {home.latitude_deg:.7f}, {home.longitude_deg:.7f}")
        break

    north = side / METERS_PER_DEGREE
    east = north / math.cos(math.radians(home.latitude_deg))
    corners = [(north, 0), (north, east), (0, east), (0, 0)]  # back home last
    plan = MissionPlan([waypoint(home.latitude_deg + n, home.longitude_deg + e) for n, e in corners])
    print(f"Uploading the mission: a {side:g} m square, {len(corners)} waypoints...")
    await rover.mission.upload_mission(plan)

    print("Arming...")
    await rover.action.arm()

    t0 = time.monotonic()
    print("Starting the mission...")
    await rover.mission.start_mission()
    async for progress in rover.mission.mission_progress():
        print(f"  [{time.monotonic() - t0:6.1f} s] waypoint {progress.current}/{progress.total}")
        if progress.current == progress.total:
            break
    print(f"Mission finished in {time.monotonic() - t0:.1f} s")

    print("Disarming...")
    await rover.action.disarm()
    print("Done")


def main() -> None:
    """Parse the arguments and run the scenario."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=14540, help="the agent's MAVLink port (default 14540)")
    parser.add_argument("--side", type=float, default=5.0, help="side of the square, m (default 5)")
    args = parser.parse_args()
    asyncio.run(run_square(args.port, args.side))


if __name__ == "__main__":
    main()
