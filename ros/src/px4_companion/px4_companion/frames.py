"""PX4 (NED or FRD world, FRD body) to ROS (ENU world, FLU body), REP 103/105.

Kept free of px4_msgs so it can be tested anywhere (test/test_frames.py).
"""

from typing import TYPE_CHECKING

import numpy as np
from scipy.spatial.transform import Rotation as Rot

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

# PX4 VehicleOdometry frame enums
POSE_FRAME_NED, POSE_FRAME_FRD = 1, 2
VELOCITY_FRAME_NED, VELOCITY_FRAME_FRD, VELOCITY_FRAME_BODY_FRD = 1, 2, 3

# World: NED -> ENU swaps north/east and flips down; an FRD world frame (arbitrary
# heading) maps to FLU the same way the body does. Body: FRD -> FLU.
NED_TO_ENU = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
FRD_TO_FLU = np.diag([1.0, -1.0, -1.0])


def world_to_ros(pose_frame: int) -> np.ndarray:
    """Rotation taking PX4 world coordinates to the ROS odom frame."""
    return NED_TO_ENU if pose_frame == POSE_FRAME_NED else FRD_TO_FLU


def pose(position: ArrayLike, q_wxyz: ArrayLike, pose_frame: int) -> tuple[np.ndarray, np.ndarray, Rot]:
    """ROS odom-frame position, orientation as xyzw, and the body-to-odom rotation."""
    w2r = world_to_ros(pose_frame)
    # PX4 q rotates body FRD into the world frame; conjugate by the axis changes.
    w, x, y, z = np.asarray(q_wxyz, float)
    world_from_frd = Rot.from_quat([x, y, z, w])
    odom_from_flu = Rot.from_matrix(w2r) * world_from_frd * Rot.from_matrix(FRD_TO_FLU)
    return w2r @ np.asarray(position, float), odom_from_flu.as_quat(), odom_from_flu


def body_velocity(
    velocity: ArrayLike, velocity_frame: int, pose_frame: int, odom_from_flu: Rot
) -> tuple[np.ndarray, np.ndarray]:
    """Linear velocity in the FLU body frame, and the matrix that took it there (for the covariance)."""
    if velocity_frame == VELOCITY_FRAME_BODY_FRD:
        m = FRD_TO_FLU
    else:  # a world frame: NED, or FRD with the pose's heading offset
        m = odom_from_flu.inv().as_matrix() @ world_to_ros(pose_frame)
    return m @ np.asarray(velocity, float), m
