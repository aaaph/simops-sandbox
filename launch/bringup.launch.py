"""Gazebo + robot_state_publisher + spawn + ros_gz bridge, in one shot.

ros2 launch launch/bringup.launch.py                 # temp_room.sdf, with GUI
ros2 launch launch/bringup.launch.py gui:=false      # headless
ros2 launch launch/bringup.launch.py platform:=vehicle_blue
ros2 launch launch/bringup.launch.py initial_sim_time:=0   # reproducible stamps
"""

import time
from pathlib import Path

from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from launch import LaunchDescription

ROOT = Path(__file__).resolve().parent.parent


def generate_launch_description():
    world = LaunchConfiguration("world")
    world_name = LaunchConfiguration("world_name")
    platform = LaunchConfiguration("platform")
    gui = LaunchConfiguration("gui")
    t0 = LaunchConfiguration("initial_sim_time")
    sim_time = {"use_sim_time": True}

    world_path = PathJoinSubstitution([str(ROOT), world])
    xacro_path = PathJoinSubstitution(
        [str(ROOT), "models", platform, "vehicle_blue.urdf.xacro"]
    )
    # one description feeds both TF and the simulator
    robot_description = ParameterValue(
        Command(["xacro ", xacro_path]), value_type=str
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("world", default_value="worlds/temp_room.sdf"),
            # must match <world name=...> inside the .sdf; the generator emits "room"
            DeclareLaunchArgument("world_name", default_value="room"),
            DeclareLaunchArgument("platform", default_value="vehicle_blue"),
            DeclareLaunchArgument("gui", default_value="true"),
            # wall-clock epoch by default: keeps Rerun off 1970 and stops
            # consecutive runs from overwriting each other. Pass 0 for
            # reproducible stamps.
            DeclareLaunchArgument(
                "initial_sim_time", default_value=str(int(time.time()))
            ),
            ExecuteProcess(
                cmd=["gz", "sim", "-r", "--initial-sim-time", t0, world_path],
                condition=IfCondition(gui),
                output="screen",
            ),
            ExecuteProcess(
                cmd=["gz", "sim", "-r", "-s", "--initial-sim-time", t0, world_path],
                condition=UnlessCondition(gui),
                output="screen",
            ),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": robot_description}, sim_time],
                output="screen",
            ),
            # ponytail: fixed delay instead of an event handler on the gz process.
            # `create` needs the world's /create service up. Swap for a
            # RegisterEventHandler if 3 s ever turns out to be too short.
            TimerAction(
                period=3.0,
                actions=[
                    Node(
                        package="ros_gz_sim",
                        executable="create",
                        arguments=[
                            "-world", world_name,
                            "-topic", "robot_description",
                            "-name", platform,
                            "-z", "0.4",
                        ],
                        parameters=[sim_time],
                        output="screen",
                    )
                ],
            ),
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                parameters=[
                    {"config_file": str(ROOT / "config" / "ros_gz_bridge.yaml")},
                    sim_time,
                ],
                output="screen",
            ),
        ]
    )
