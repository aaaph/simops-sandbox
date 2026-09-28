"""Agents: start poses and the rotation gz receives."""

import math

import pytest
from pydantic import ValidationError

from simops.agent import Pose, quaternion


@pytest.mark.parametrize(
    ("rpy", "expected"),
    [
        ((0, 0, 0), (0, 0, 0, 1)),
        ((0, 0, math.pi / 2), (0, 0, math.sqrt(0.5), math.sqrt(0.5))),
        ((math.pi / 2, 0, 0), (math.sqrt(0.5), 0, 0, math.sqrt(0.5))),
        # roll 90 then pitch 90 about the fixed axes (ROS rpy is extrinsic x-y-z)
        ((math.pi / 2, math.pi / 2, 0), (0.5, 0.5, -0.5, 0.5)),
    ],
)
def test_quaternion(rpy, expected):
    assert quaternion(*rpy) == pytest.approx(expected, abs=1e-12)


def test_pose_from_a_short_list():
    assert Pose.model_validate([1, 2]) == Pose(x=1, y=2)


def test_pose_with_too_many_numbers():
    with pytest.raises(ValidationError, match="at most 6 numbers"):
        Pose.model_validate([0, 0, 0, 0, 0, 0, 0])
