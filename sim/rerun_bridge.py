#!/usr/bin/env python3
"""Log this stack to Rerun ourselves, in the shape we want to look at.

rewire streams every topic for free, but its presentation is not ours to change:
the occupancy grid comes out mirrored, odometry drags kilometre-tall covariance
ellipsoids around, and every topic lands in a flat list. Here the layout is the
point.

Spatial things live under /world, and the path below it *is* the frame chain

    /world/map/odom/base_link/lidar_link

so a transform logged on one link moves everything beneath it, exactly like tf.
Numbers that are not geometry live outside it, in /sensors and /metrics, which is
what the time series panels read.

Run it next to the stack:  pixi run rerun_bridge
"""

import math
from typing import TYPE_CHECKING

import numpy as np
import rclpy
import rclpy.time
import rerun as rr  # ty: ignore[unresolved-import]
import rerun.blueprint as rrb  # ty: ignore[unresolved-import]
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Imu, LaserScan
from tf2_ros import Buffer, TransformListener

if TYPE_CHECKING:  # annotations are lazy on 3.14, so this is only for the checker
    from std_msgs.msg import Header

# /world is the simulation origin. slam's `map` starts there too, as long as slam
# is launched while the robot still sits on its spawn pose.
WORLD = "world"
PATH = {
    "map": f"{WORLD}/map",
    "odom": f"{WORLD}/map/odom",
    "base_link": f"{WORLD}/map/odom/base_link",
    "lidar_link": f"{WORLD}/map/odom/base_link/lidar_link",
}
CHAIN = (("map", "odom"), ("odom", "base_link"), ("base_link", "lidar_link"))
# base_link *is* the filtered estimate -- the EKF publishes it as tf and as a topic,
# so the topic gets no arrow of its own. Wheel odometry is diagnostic, but its numbers
# are odom-relative, so it still hangs below odom. Truth belongs to no estimator: it
# sits at the world root, untouched by the map -> odom correction.
ESTIMATES = {
    "/odom": (f"{WORLD}/map/odom/diagnostics/wheels", "wheels", [230, 150, 70]),
    "/odometry/filtered": (None, "filtered", [80, 170, 240]),
    "/ground_truth": (f"{WORLD}/truth", "truth", [120, 220, 120]),
}
OCCUPIED = 50  # OccupancyGrid is 0..100 with -1 unknown; above this we call it a wall


def stamp_seconds(header: Header) -> float:
    """ROS stamp as float seconds, for the Rerun timeline."""
    return header.stamp.sec + header.stamp.nanosec * 1e-9


def yaw_of(q) -> float:  # noqa: ANN001 - a geometry_msgs quaternion, not worth importing for one hint
    """Yaw from a quaternion, the only angle a planar robot has."""
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def blueprint() -> rrb.Blueprint:
    """One tab for the scene, one for the numbers -- so the viewer opens usable."""
    return rrb.Blueprint(
        rrb.Tabs(
            rrb.Spatial3DView(name="Scene", origin="/world", background=[0, 0, 0]),
            rrb.Vertical(
                rrb.TimeSeriesView(name="Drift against truth", origin="/metrics"),
                rrb.TimeSeriesView(name="IMU", origin="/sensors/imu"),
                name="Estimates",
            ),
        ),
        # all panels open: the entity tree and view settings are half the point of looking
        rrb.BlueprintPanel(expanded=True),
        rrb.SelectionPanel(expanded=True),
        rrb.TimePanel(expanded=True),
    )


class RerunBridge(Node):
    """Subscribe to the handful of topics worth looking at and log them to Rerun."""

    def __init__(self) -> None:
        """Wire up the subscriptions; the tf buffer feeds the frame hierarchy."""
        super().__init__("rerun_bridge")
        self.declare_parameter("endpoint", "")  # empty: spawn our own viewer
        endpoint = self.get_parameter("endpoint").value

        rr.init("simops", spawn=not endpoint)
        if endpoint:
            rr.connect_grpc(endpoint)
        rr.send_blueprint(blueprint())
        rr.log(WORLD, rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        # a frame is a coordinate system, not a body: without axes it is invisible
        for path in PATH.values():
            rr.log(path, rr.TransformAxes3D(axis_length=0.3), static=True)
        # the body, so base_link carries something you can see. Sizes are the chassis
        # collision box from model.sdf: 1 x 0.5 x 0.1, centred 0.2 m ahead of the axle.
        rr.log(
            PATH["base_link"] + "/body",
            rr.Boxes3D(centers=[[0.2, 0.0, 0.0]], half_sizes=[[0.5, 0.25, 0.05]], colors=[90, 140, 200]),
            static=True,
        )

        self.truth: tuple[float, float, float] | None = None
        self.tf = Buffer()
        TransformListener(self.tf, self)

        latched = QoSProfile(
            depth=1, reliability=QoSReliabilityPolicy.RELIABLE, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL
        )
        self.create_subscription(OccupancyGrid, "/map", self.on_map, latched)
        self.create_subscription(LaserScan, "/scan", self.on_scan, 10)
        self.create_subscription(Imu, "/imu", self.on_imu, 10)
        for topic, (path, name, color) in ESTIMATES.items():
            # bind the topic here: the three messages are indistinguishable otherwise,
            # they all claim frame odom -> base_link
            self.create_subscription(
                Odometry, topic, lambda m, pa=path, n=name, c=color: self.on_odom(m, pa, n, c), 10
            )
        self.create_timer(0.05, self.on_frames)

    def on_frames(self) -> None:
        """Push the current tf chain, so everything below a link follows it."""
        rr.set_time("ros_time", timestamp=self.get_clock().now().nanoseconds * 1e-9)
        for parent, child in CHAIN:
            try:
                t = self.tf.lookup_transform(parent, child, rclpy.time.Time()).transform
            except Exception as exc:  # noqa: BLE001 - a missing link just means "not yet"
                self.get_logger().debug(f"no transform {parent} -> {child}: {exc}")
                continue
            quaternion = rr.Quaternion(xyzw=[t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w])

            rr.log(
                PATH[child],
                rr.Transform3D(
                    translation=[t.translation.x, t.translation.y, t.translation.z], quaternion=quaternion
                ),
            )

    def on_map(self, msg: OccupancyGrid) -> None:
        """Occupied cells as points in the map frame -- built from the grid ourselves.

        Row `j` of the data is at `origin_y + (j + 0.5) * resolution`, which is the
        whole trick the mirrored picture was getting wrong.
        """
        rr.set_time("ros_time", timestamp=stamp_seconds(msg.header))
        data = np.asarray(msg.data, dtype=np.int8).reshape(msg.info.height, msg.info.width)
        rows, cols = np.nonzero(data > OCCUPIED)
        res = msg.info.resolution
        xs = msg.info.origin.position.x + (cols + 0.5) * res
        ys = msg.info.origin.position.y + (rows + 0.5) * res
        rr.log(
            PATH["map"] + "/grid",
            rr.Points3D(np.c_[xs, ys, np.zeros_like(xs)], colors=[210, 210, 210], radii=res),
        )

    def on_scan(self, msg: LaserScan) -> None:
        """Ranges as points in the sensor frame; the hierarchy places them."""
        rr.set_time("ros_time", timestamp=stamp_seconds(msg.header))
        r = np.asarray(msg.ranges, dtype=np.float32)
        ang = msg.angle_min + np.arange(len(r), dtype=np.float32) * msg.angle_increment
        keep = np.isfinite(r) & (r > msg.range_min) & (r < msg.range_max)
        pts = np.c_[r[keep] * np.cos(ang[keep]), r[keep] * np.sin(ang[keep]), np.zeros(keep.sum())]
        rr.log(PATH["lidar_link"] + "/scan", rr.Points3D(pts, colors=[120, 220, 120], radii=0.02))

    def on_imu(self, msg: Imu) -> None:
        """Log the two channels that matter for a planar robot: yaw rate and forward accel."""
        rr.set_time("ros_time", timestamp=stamp_seconds(msg.header))
        rr.log("sensors/imu/yaw_rate", rr.Scalars(msg.angular_velocity.z))
        rr.log("sensors/imu/accel_x", rr.Scalars(msg.linear_acceleration.x))

    def on_odom(self, msg: Odometry, path: str | None, name: str, color: list[int]) -> None:
        """Draw the estimate where it belongs, and score it against truth in /metrics.

        `path` is None for the filtered estimate: base_link already is that pose, drawn
        by the frame chain, and a second arrow on top of it would say nothing new.
        """
        rr.set_time("ros_time", timestamp=stamp_seconds(msg.header))
        p, yaw = msg.pose.pose.position, yaw_of(msg.pose.pose.orientation)
        if path:
            rr.log(
                path,
                rr.Arrows3D(
                    origins=[[p.x, p.y, 0.05]],
                    vectors=[[0.5 * math.cos(yaw), 0.5 * math.sin(yaw), 0]],
                    colors=[color],
                ),
            )
        if name == "truth":
            self.truth = (p.x, p.y, yaw)
            return
        if self.truth is None:
            return
        tx, ty, tyaw = self.truth
        rr.log(f"metrics/{name}/position_error", rr.Scalars(math.hypot(p.x - tx, p.y - ty)))
        rr.log(
            f"metrics/{name}/yaw_error_deg",
            rr.Scalars(math.degrees((yaw - tyaw + math.pi) % (2 * math.pi) - math.pi)),
        )


def main() -> None:
    """Spin the bridge; the launch file owns its parameters."""
    rclpy.init()
    rclpy.spin(RerunBridge())


if __name__ == "__main__":
    main()
