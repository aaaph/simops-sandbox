#!/usr/bin/env python3
"""Republish wheel odometry with a covariance, because Gazebo ships none.

The DiffDrive plugin leaves the whole covariance block at zero, and so does its
odometry_with_covariance topic. robot_localization reads that as "this
measurement is perfect", stops listening to the IMU, and the filter becomes an
expensive copy of the wheels. So we state the uncertainty here instead.

The numbers are a modelling choice, not a measurement: they say how much a wheel
encoder may lie on a floor this robot can slip on. Raise them when the rover
slips more, lower them when the wheels are trustworthy.
"""

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


class OdomCovariance(Node):
    """Copy Odometry through, filling the diagonal of both covariance blocks."""

    def __init__(self) -> None:
        """Read the variances from parameters so they can be tuned from the launch."""
        super().__init__("odom_covariance")
        self.declare_parameter("in_topic", "/odom")
        self.declare_parameter("out_topic", "/odom/cov")
        # [x, y, z, roll, pitch, yaw] for pose, [vx, vy, vz, vroll, vpitch, vyaw] for twist
        self.declare_parameter("pose_variance", [0.05, 0.05, 1e6, 1e6, 1e6, 0.1])
        self.declare_parameter("twist_variance", [0.01, 1e6, 1e6, 1e6, 1e6, 0.05])

        self.pose_var = self.get_parameter("pose_variance").value
        self.twist_var = self.get_parameter("twist_variance").value
        self.pub = self.create_publisher(Odometry, self.get_parameter("out_topic").value, 10)
        self.create_subscription(Odometry, self.get_parameter("in_topic").value, self.relay, 10)

    def relay(self, msg: Odometry) -> None:
        """Stamp the diagonals and forward the message."""
        for block, var in ((msg.pose.covariance, self.pose_var), (msg.twist.covariance, self.twist_var)):
            for i, v in enumerate(var):
                block[i * 7] = v
        self.pub.publish(msg)


def main() -> None:
    """Spin the relay; the launch file owns its parameters."""
    rclpy.init()
    rclpy.spin(OdomCovariance())


if __name__ == "__main__":
    main()
