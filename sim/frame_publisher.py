#!/usr/bin/env python3
"""Publish the platform's fixed sensor frames on /tf instead of /tf_static.

Convention says fixed frames belong on /tf_static, and for tf2 consumers that is
strictly better. We publish them on /tf because Rerun's bridge does not pick up
the latched topic on a late join, and having to start the viewer before the stack
is a trap that costs more than the extra traffic.

Frames come in as "<child> x y z roll pitch yaw" strings, read out of the model
SDF by the launch file, so the numbers are never restated by hand.
"""

import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation as Rot
from tf2_msgs.msg import TFMessage


def quat(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """RPY -> xyzw. Six lines beats a dependency for one conversion."""
    return Rot.from_euler("xyz", [roll, pitch, yaw]).as_quat()


class FramePublisher(Node):
    """Republish the platform's fixed frames on /tf, forever."""

    def __init__(self) -> None:
        """Turn the launch file's frame specs into the messages tick() resends."""
        super().__init__("frame_publisher")
        self.declare_parameter("parent", "base_link")
        self.declare_parameter("frames", [""])
        self.declare_parameter("rate", 20.0)

        parent = self.get_parameter("parent").value
        self.msgs = []
        for spec in self.get_parameter("frames").value:
            if not spec.strip():
                continue
            child, *v = spec.split()
            x, y, z, roll, pitch, yaw = (float(n) for n in v)
            t = TransformStamped()
            t.header.frame_id = parent
            t.child_frame_id = child
            t.transform.translation.x = x
            t.transform.translation.y = y
            t.transform.translation.z = z
            q = quat(roll, pitch, yaw)
            (t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z, t.transform.rotation.w) = q
            self.msgs.append(t)

        self.pub = self.create_publisher(TFMessage, "/tf", 10)
        rate = self.get_parameter("rate").value
        self.create_timer(1.0 / rate, self.tick)
        self.get_logger().info(f"publishing {len(self.msgs)} fixed frames on /tf at {rate} Hz")

    def tick(self) -> None:
        """Stamp every fixed frame with now and publish the batch."""
        now = self.get_clock().now().to_msg()
        for t in self.msgs:
            t.header.stamp = now
        self.pub.publish(TFMessage(transforms=self.msgs))


def main() -> None:
    """Spin the node; the launch file owns its parameters."""
    rclpy.init()
    rclpy.spin(FramePublisher())


if __name__ == "__main__":
    main()
