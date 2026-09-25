"""The rover's companion computer (the Pi 5): PX4 odometry and the fixed sensor frames.

tf it builds: odom -> base_link (px4_odometry, PX4's EKF) -> lidar_link (frame_publisher,
read from model.sdf). map -> odom is SLAM's, off the companion. The sensors themselves come
from their drivers — in the sim, from the sim-sensors container (bridge.yaml).
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from px4_companion.sdf_frames import frame_specs

from launch import LaunchDescription

SHARE = Path(get_package_share_directory("rover_differential_lidar_px4"))


def generate_launch_description() -> LaunchDescription:
    """PX4 odometry and frame publisher; sim time by default, pass use_sim_time:=false on the rover."""
    sim_time = {"use_sim_time": ParameterValue(LaunchConfiguration("use_sim_time"), value_type=bool)}
    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            Node(package="px4_companion", executable="px4_odometry", parameters=[sim_time], output="screen"),
            Node(
                package="px4_companion",
                executable="frame_publisher",
                parameters=[{"parent": "base_link", "frames": frame_specs(SHARE / "model.sdf")}, sim_time],
                output="screen",
            ),
        ]
    )
