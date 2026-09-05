#!/usr/bin/env python3
"""Say what is actually wrong when `pixi run bringup` looks dead.

Gazebo can deadlock at startup between the simulation loop and the Sensors
system's render thread: every process is alive, the CPU is busy, and nothing is
published, so the log tells you nothing. This walks the chain from the physics
loop outwards and names the first link that is broken.

    pixi run doctor
"""

import subprocess
import sys
import time

import rclpy
from rclpy.node import Node
from rosidl_runtime_py.utilities import get_message

TOPICS = ("/clock", "/scan", "/imu", "/odom", "/odometry/filtered", "/tf")


def procs() -> dict[str, int]:
    """Count the processes bringup is supposed to have running."""
    out = subprocess.run(["ps", "ax", "-o", "command"], capture_output=True, text=True, check=False).stdout
    names = {
        "gz server": "gz sim -s",
        "gz gui": "gz sim -g",
        "bridge": "parameter_bridge",
        "frames": "frame_publisher.py",
        "ekf": "ekf_node",
        "odom cov": "odom_covariance.py",
    }
    return {label: sum(needle in line for line in out.splitlines()) for label, needle in names.items()}


def stepping() -> str:
    """Ask Gazebo for world stats; a timeout here means the server is wedged."""
    try:
        out = subprocess.run(
            ["gz", "topic", "-e", "-t", "/world/room/stats", "-n", "1"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except subprocess.TimeoutExpired:
        return "wedged"
    except FileNotFoundError:
        return "no gz cli"
    for line in out.splitlines():
        if line.strip().startswith("iterations:"):
            return line.split(":")[1].strip()
    return "silent"


def ros_traffic(seconds: float = 8.0) -> dict[str, int]:
    """Count messages on the topics the rest of the stack needs."""
    types = {
        "/clock": "rosgraph_msgs/msg/Clock",
        "/scan": "sensor_msgs/msg/LaserScan",
        "/imu": "sensor_msgs/msg/Imu",
        "/odom": "nav_msgs/msg/Odometry",
        "/odometry/filtered": "nav_msgs/msg/Odometry",
        "/tf": "tf2_msgs/msg/TFMessage",
    }
    rclpy.init()
    node = Node("doctor")
    seen = dict.fromkeys(TOPICS, 0)
    for topic in TOPICS:
        node.create_subscription(
            get_message(types[topic]), topic, lambda _m, t=topic: seen.__setitem__(t, seen[t] + 1), 10
        )
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    rclpy.shutdown()
    return seen


def main() -> int:
    """Print the chain and a verdict; exit non-zero when the stack is not usable."""
    running = procs()
    print("processes:  " + ", ".join(f"{k}={v}" for k, v in running.items()))
    if not running["gz server"]:
        print("\nverdict: no Gazebo server. Start it with `pixi run bringup`.")
        return 1

    steps = stepping()
    print(f"gz physics: {steps} iterations" if steps.isdigit() else f"gz physics: {steps}")
    if steps in ("wedged", "silent"):
        print(
            "\nverdict: the server is up but not stepping. This is the Gazebo startup deadlock\n"
            "between the simulation loop and the Sensors render thread -- it is a race, so\n"
            "kill bringup and start it again; it usually comes up within a try or two."
        )
        return 1

    traffic = ros_traffic()
    print("ros topics: " + ", ".join(f"{t}={n}" for t, n in traffic.items()))
    dead = [t for t, n in traffic.items() if n == 0]
    if dead == ["/scan"]:
        print(
            "\nverdict: physics runs but the lidar is silent -- rendering failed while the rest\n"
            "of the world kept going. Restart bringup."
        )
        return 1
    if dead:
        print(
            f"\nverdict: no traffic on {', '.join(dead)}. If gz publishes them (check\n"
            "`gz topic -l`), the ROS side is stale: `pixi run ros2 daemon stop` and retry."
        )
        return 1
    print("\nverdict: everything is running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
