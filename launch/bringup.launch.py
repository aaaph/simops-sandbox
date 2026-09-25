"""Gazebo + spawn + ros_gz bridge for one platform.

ros2 launch launch/bringup.launch.py                                  # default platform, GUI
ros2 launch launch/bringup.launch.py gui:=false
ros2 launch launch/bringup.launch.py platform:=rover_differential_lidar
ros2 launch launch/bringup.launch.py initial_sim_time:=0              # reproducible stamps

A platform is either platforms/<name>/model.sdf (spawned from the file) or
models/<name>/<name>.urdf.xacro (published by robot_state_publisher and spawned
from /robot_description). Its bridge config is platforms/<name>/bridge.yaml if
present, otherwise sim/bridge_fallback.yaml, which is /clock and a warning.
"""

import sys
import time
from pathlib import Path

import launch.logging
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from launch import LaunchContext, LaunchDescription

ROOT = Path(__file__).resolve().parent.parent
# frame_publisher and the SDF frame reader live in the companion package; the
# native stack runs them from the source tree, without building the package.
COMPANION = ROOT / "ros" / "src" / "px4_companion"
sys.path.insert(0, str(COMPANION))
from px4_companion.sdf_frames import sensor_frames  # noqa: E402


def platform_actions(context: LaunchContext) -> list:
    """Resolve the platform at launch time: the spawn path depends on its value."""
    platform = LaunchConfiguration("platform").perform(context)
    sim_time = {"use_sim_time": True}
    actions = []

    sdf = ROOT / "platforms" / platform / "model.sdf"
    xacro = ROOT / "models" / platform / f"{platform}.urdf.xacro"

    if sdf.exists():
        spawn_args = ["-file", str(sdf)]
        spawn_z = "0.2"
        spawn_x = "0.0"
    elif xacro.exists():
        actions.append(
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[
                    {"robot_description": ParameterValue(Command(["xacro ", str(xacro)]), value_type=str)},
                    sim_time,
                ],
                output="screen",
            )
        )
        spawn_args = ["-topic", "robot_description"]
        spawn_z = "0.4"  # wheels are r=0.4 on this one
        spawn_x = "0.0"
    else:
        raise RuntimeError(f"platform '{platform}': neither {sdf} nor {xacro} exists")

    bridge_cfg = ROOT / "platforms" / platform / "bridge.yaml"
    if not bridge_cfg.exists():
        bridge_cfg = ROOT / "sim" / "bridge_fallback.yaml"
        launch.logging.get_logger("bringup").warning(
            f"platform '{platform}' ships no bridge.yaml: falling back to {bridge_cfg.name}, "
            f"which bridges /clock and nothing else. Its sensors and commands stay on the "
            f"Gazebo side until platforms/{platform}/bridge.yaml exists."
        )

    # `create` polls for the world's /create service itself, so it can start at
    # once; the GUI then waits for it to finish rather than for a fixed delay,
    # because a model spawned after the GUI attaches may never be rendered.
    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-world",
            LaunchConfiguration("world_name"),
            "-name",
            platform,
            "-x",
            spawn_x,
            "-z",
            spawn_z,
            *spawn_args,
        ],
        parameters=[sim_time],
        output="screen",
    )
    actions.append(spawn)
    if LaunchConfiguration("gui").perform(context) == "true":
        actions.append(
            RegisterEventHandler(
                OnProcessExit(
                    target_action=spawn,
                    on_exit=[ExecuteProcess(cmd=["gz", "sim", "-g"], output="screen")],
                )
            )
        )
    frames = sensor_frames(sdf) if sdf.exists() else []
    if frames:
        actions.append(
            Node(
                executable=str(COMPANION / "px4_companion" / "frame_publisher.py"),
                name="frame_publisher",
                parameters=[
                    {"parent": "base_link", "frames": [f"{n} " + " ".join(v) for n, v in frames]},
                    sim_time,
                ],
                output="screen",
            )
        )

    ekf_cfg = ROOT / "platforms" / platform / "ekf.yaml"
    if ekf_cfg.exists():
        # Gazebo publishes odometry without a covariance, and robot_localization
        # reads a zero covariance as certainty, so the raw topic gets one first.
        actions.append(
            Node(
                executable=str(ROOT / "sim" / "odom_covariance.py"),
                name="odom_covariance",
                parameters=[sim_time],
                output="screen",
            )
        )
        actions.append(
            Node(
                package="robot_localization",
                executable="ekf_node",
                name="ekf_filter_node",
                parameters=[str(ekf_cfg), sim_time],
                output="screen",
            )
        )

    actions.append(
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            parameters=[{"config_file": str(bridge_cfg)}, sim_time],
            output="screen",
        )
    )
    return actions


def generate_launch_description() -> LaunchDescription:
    """Declare the launch arguments; the platform decides the rest."""
    world = LaunchConfiguration("world")
    _gui = LaunchConfiguration("gui")
    t0 = LaunchConfiguration("initial_sim_time")
    world_path = PathJoinSubstitution([str(ROOT), world])

    return LaunchDescription(
        [
            DeclareLaunchArgument("world", default_value="worlds/temp_room.sdf"),
            # must match <world name=...> inside the .sdf; the generator emits "room"
            DeclareLaunchArgument("world_name", default_value="room"),
            DeclareLaunchArgument("platform", default_value="rover_differential_lidar"),
            DeclareLaunchArgument("gui", default_value="true"),
            # wall-clock epoch by default: keeps Rerun off 1970 and stops
            # consecutive runs from overwriting each other. Pass 0 for
            # reproducible stamps.
            DeclareLaunchArgument("initial_sim_time", default_value=str(int(time.time()))),
            # macOS Gazebo refuses to run server and GUI in one process
            # (gazebosim/gz-sim#44), so the server always runs on its own and the
            # GUI, when asked for, is a second process that attaches to it.
            ExecuteProcess(
                cmd=["gz", "sim", "-s", "-r", "--initial-sim-time", t0, world_path],
                output="screen",
            ),
            OpaqueFunction(function=platform_actions),
        ]
    )
