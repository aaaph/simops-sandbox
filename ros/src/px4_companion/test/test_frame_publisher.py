"""Tests for frame_publisher: the RPY convention, the spec parsing, and the wire.

Run with `pixi run test`. Nothing here needs Gazebo or a running stack -- the node
test spins the publisher and a throwaway subscriber inside one rclpy context.
"""

import math
import time

import pytest
import rclpy
from px4_companion.frame_publisher import FramePublisher, quat
from rclpy.node import Node
from scipy.spatial.transform import Rotation as Rot
from tf2_msgs.msg import TFMessage

FRAMES = [
    "lidar_link 0 0 0.26 0 0 0",
    "imu_link 0.2 -0.1 0.05 0 0 1.5707963",
]
# a blank entry is what the launch file passes when a platform declares no frames
FRAMES_YAML = '["' + '","'.join([*FRAMES, ""]) + '"]'


def composed(roll, pitch, yaw):
    """Fixed-axis RPY the long way: Rz then Ry then Rx, composed one axis at a time.

    Still scipy, but a different code path from `from_euler("xyz", ...)`, so it is
    a real second opinion on the convention rather than a restatement of it.
    """
    rz, ry, rx = (Rot.from_rotvec(v) for v in ([0, 0, yaw], [0, pitch, 0], [roll, 0, 0]))
    return Rot.from_matrix(rz.as_matrix() @ ry.as_matrix() @ rx.as_matrix()).as_quat()


@pytest.fixture
def node():
    """Build a FramePublisher carrying FRAMES, parameters injected as global ROS args."""
    rclpy.init(args=["--ros-args", "-p", "parent:=chassis", "-p", "rate:=50.0", "-p", f"frames:={FRAMES_YAML}"])
    n = FramePublisher()
    yield n
    n.destroy_node()
    rclpy.shutdown()


def test_quat_identity():
    assert quat(0.0, 0.0, 0.0) == pytest.approx((0.0, 0.0, 0.0, 1.0))


def test_quat_is_xyzw_not_wxyz():
    # a quarter turn about yaw puts the sine in z, never in the first slot
    x, y, z, w = quat(0.0, 0.0, math.pi / 2)
    assert (x, y) == pytest.approx((0.0, 0.0))
    assert (z, w) == pytest.approx((math.sqrt(0.5), math.sqrt(0.5)))


@pytest.mark.parametrize(
    "rpy",
    [(0.0, 0.0, 0.0), (0.3, 0.0, 0.0), (0.0, -0.7, 0.0), (0.0, 0.0, 2.1), (0.3, -0.7, 2.1)],
)
def test_quat_is_fixed_axis_rpy(rpy):
    # scipy's lowercase "xyz" is extrinsic, which is what ROS means by roll-pitch-yaw;
    # the intrinsic "XYZ" would disagree on the mixed case below
    assert quat(*rpy) == pytest.approx(composed(*rpy))


def test_specs_become_transforms(node):
    assert [t.child_frame_id for t in node.msgs] == ["lidar_link", "imu_link"]
    assert {t.header.frame_id for t in node.msgs} == {"chassis"}


def test_translation_parsed(node):
    lidar, imu = node.msgs
    assert (lidar.transform.translation.x, lidar.transform.translation.z) == pytest.approx((0.0, 0.26))
    t = imu.transform.translation
    assert (t.x, t.y, t.z) == pytest.approx((0.2, -0.1, 0.05))


def test_rotation_parsed(node):
    imu = node.msgs[1].transform.rotation
    assert (imu.x, imu.y, imu.z, imu.w) == pytest.approx(quat(0.0, 0.0, 1.5707963))


def test_blank_specs_are_skipped(node):
    assert len(node.msgs) == len(FRAMES)


def test_publishes_on_tf(node):
    """The node test: a real subscriber on /tf gets the frames, restamped each tick."""
    got = []
    listener = Node("test_listener")
    listener.create_subscription(TFMessage, "/tf", got.append, 10)

    deadline = time.monotonic() + 10.0
    while len(got) < 2 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        rclpy.spin_once(listener, timeout_sec=0.05)
    listener.destroy_node()

    assert len(got) >= 2, "no /tf traffic within 10 s"
    assert [t.child_frame_id for t in got[0].transforms] == ["lidar_link", "imu_link"]
    stamps = [msg.transforms[0].header.stamp for msg in got[:2]]
    assert (stamps[1].sec, stamps[1].nanosec) != (stamps[0].sec, stamps[0].nanosec), "stamp is frozen"
