"""Gazebo + ros_gz bridge + the static lidar transform, in one shot.

ros2 launch launch/bringup.launch.py                 # temp_room.sdf, with GUI
ros2 launch launch/bringup.launch.py gui:=false      # headless
ros2 launch launch/bringup.launch.py world:=worlds/building_robot.sdf
"""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parent.parent


def generate_launch_description():
    world = LaunchConfiguration("world")
    gui = LaunchConfiguration("gui")
    sim_time = {"use_sim_time": True}
    world_path = PathJoinSubstitution([str(ROOT), world])

    return LaunchDescription(
        [
            DeclareLaunchArgument("world", default_value="worlds/temp_room.sdf"),
            DeclareLaunchArgument("gui", default_value="true"),
            ExecuteProcess(
                cmd=["gz", "sim", "-r", world_path],
                condition=IfCondition(gui),
                output="screen",
            ),
            ExecuteProcess(
                cmd=["gz", "sim", "-r", "-s", world_path],
                condition=UnlessCondition(gui),
                output="screen",
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
