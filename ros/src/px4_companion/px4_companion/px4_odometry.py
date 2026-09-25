#!/usr/bin/env python3
"""PX4's EKF odometry on /odom and as the odom -> base_link transform.

/fmu/out/vehicle_odometry is NED/FRD with a PX4 timestamp; this republishes it in
the ROS conventions (ENU odom, FLU base_link, REP 103/105) that SLAM, nav2 and tf
expect. In SITL the PX4 clock is the sim clock (lockstep), so the stamps line up
with /clock; on a real vehicle they need PX4's timesync instead.
"""

import math

import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from px4_msgs.msg import VehicleOdometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf2_msgs.msg import TFMessage

from px4_companion import frames


class Px4Odometry(Node):
    """Convert each PX4 odometry sample and publish it on /odom and /tf."""

    def __init__(self) -> None:
        """Declare the frame names and wire the PX4 subscription."""
        super().__init__("px4_odometry")
        self.odom_frame = self.declare_parameter("odom_frame", "odom").value
        self.base_frame = self.declare_parameter("base_frame", "base_link").value
        self.publish_tf = self.declare_parameter("publish_tf", value=True).value

        self.odom_pub = self.create_publisher(Odometry, "/odom", 10)
        self.tf_pub = self.create_publisher(TFMessage, "/tf", 10)
        self.create_subscription(
            VehicleOdometry, "/fmu/out/vehicle_odometry", self.on_odometry, qos_profile_sensor_data
        )

    def on_odometry(self, px4: VehicleOdometry) -> None:
        """Republish one sample; drop it while the EKF has no pose yet (NaN)."""
        if px4.pose_frame not in (frames.POSE_FRAME_NED, frames.POSE_FRAME_FRD):
            return
        if math.isnan(px4.position[0]) or math.isnan(px4.q[0]):
            return

        position, q_xyzw, odom_from_flu = frames.pose(px4.position, px4.q, px4.pose_frame)
        velocity, vel_to_body = frames.body_velocity(
            px4.velocity, px4.velocity_frame, px4.pose_frame, odom_from_flu
        )
        angular = frames.FRD_TO_FLU @ np.asarray(px4.angular_velocity, float)

        msg = Odometry()
        msg.header.stamp.sec, usec = divmod(px4.timestamp_sample, 1_000_000)
        msg.header.stamp.nanosec = usec * 1000
        msg.header.frame_id = self.odom_frame
        msg.child_frame_id = self.base_frame

        p, o = msg.pose.pose.position, msg.pose.pose.orientation
        p.x, p.y, p.z = (float(v) for v in position)
        o.x, o.y, o.z, o.w = (float(v) for v in q_xyzw)
        t, a = msg.twist.twist.linear, msg.twist.twist.angular
        if not np.isnan(velocity).any():
            t.x, t.y, t.z = (float(v) for v in velocity)
        if not np.isnan(angular).any():
            a.x, a.y, a.z = (float(v) for v in angular)

        # Variances come per axis of PX4's frames; carry them through the same
        # rotations as the values. PX4 gives none for angular velocity: left 0.
        w2r = frames.world_to_ros(px4.pose_frame)
        pose_cov = np.zeros((6, 6))
        pose_cov[:3, :3] = w2r @ np.diag(px4.position_variance) @ w2r.T
        pose_cov[3:, 3:] = np.diag(px4.orientation_variance)  # roll/pitch/yaw: sign flips only
        twist_cov = np.zeros((6, 6))
        twist_cov[:3, :3] = vel_to_body @ np.diag(px4.velocity_variance) @ vel_to_body.T
        msg.pose.covariance = [float(v) for v in np.nan_to_num(pose_cov).flat]
        msg.twist.covariance = [float(v) for v in np.nan_to_num(twist_cov).flat]
        self.odom_pub.publish(msg)

        if self.publish_tf:
            tf = TransformStamped()
            tf.header = msg.header
            tf.child_frame_id = self.base_frame
            tf.transform.translation.x, tf.transform.translation.y, tf.transform.translation.z = p.x, p.y, p.z
            tf.transform.rotation = o
            self.tf_pub.publish(TFMessage(transforms=[tf]))


def main() -> None:
    """Spin the node; the launch file owns its parameters."""
    rclpy.init()
    rclpy.spin(Px4Odometry())


if __name__ == "__main__":
    main()
