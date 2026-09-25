"""The NED/FRD -> ENU/FLU conventions of px4_companion.frames, on cases easy to get backwards."""

import numpy as np
from px4_companion.frames import (
    POSE_FRAME_NED,
    VELOCITY_FRAME_BODY_FRD,
    VELOCITY_FRAME_NED,
    body_velocity,
    pose,
)
from scipy.spatial.transform import Rotation as Rot

IDENTITY_WXYZ = [1.0, 0.0, 0.0, 0.0]


def yaw(q_xyzw):
    return Rot.from_quat(q_xyzw).as_euler("xyz")[2]


def wxyz(rot):
    x, y, z, w = rot.as_quat()
    return [w, x, y, z]


def test_north_is_enu_plus_y():
    """PX4 identity faces north, which is +y in ENU: yaw +90 deg; NED position swaps and flips."""
    p, q, _ = pose([1.0, 2.0, 3.0], IDENTITY_WXYZ, POSE_FRAME_NED)
    assert np.allclose(p, [2.0, 1.0, -3.0])
    assert np.isclose(yaw(q), np.pi / 2)


def test_east_is_enu_yaw_zero():
    """PX4 yaw +90 deg is clockwise from north, i.e. east: ENU yaw 0."""
    _, q, _ = pose([0.0, 0.0, 0.0], wxyz(Rot.from_euler("z", np.pi / 2)), POSE_FRAME_NED)
    assert np.isclose(yaw(q), 0.0)


def test_world_velocity_along_heading_is_forward():
    for heading, v_ned in ((0.0, [1.0, 0.0, 0.0]), (np.pi / 2, [0.0, 1.0, 0.0])):
        _, _, r = pose([0.0, 0.0, 0.0], wxyz(Rot.from_euler("z", heading)), POSE_FRAME_NED)
        v, _ = body_velocity(v_ned, VELOCITY_FRAME_NED, POSE_FRAME_NED, r)
        assert np.allclose(v, [1.0, 0.0, 0.0])


def test_body_frd_right_is_flu_minus_y():
    _, _, r = pose([0.0, 0.0, 0.0], IDENTITY_WXYZ, POSE_FRAME_NED)
    v, _ = body_velocity([0.0, 1.0, 0.0], VELOCITY_FRAME_BODY_FRD, POSE_FRAME_NED, r)
    assert np.allclose(v, [0.0, -1.0, 0.0])
