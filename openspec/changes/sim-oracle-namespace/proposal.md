# Proposal

## Why

simops gives an agent what the real hardware gives it, plus sim-only channels for evaluation —
but today the sim-only `/ground_truth` sits next to the hardware topics (`/scan`, `/fmu/*`) and
only a comment keeps user code from feeding it into control. Evaluation code (the SITL test
harness) needs ground truth; deployed code must never see it. That boundary should be
structural, so a single prefix check tells them apart.

## What Changes

- Principle as a requirement: an agent's topics SHALL be the interfaces its real hardware has;
  everything sim-only SHALL be under `/sim/`, except `/clock` (ROS `use_sim_time` expects it
  there).
- **BREAKING** `/ground_truth` moves to `/sim/<agent>/ground_truth` — always with the agent's
  name, whether `namespaces` is on or off: sim-only topics are addressed per agent, and one
  prefix `/sim/` covers all of them.
- The gz topic moves with it, so the gz side keeps the same split.
- Removes the `/ground_truth` known gap from `agent-interface`.

Out of scope: new sim-only channels (contacts, world-level truth) and sim control; they come
with the changes that need them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-interface`: sim-only topics live under `/sim/<agent>/`; the hardware-only principle
  becomes a requirement; `/ground_truth` is renamed.

Depends on `baseline-simops` being archived, which creates `agent-interface`.

## Impact

- `platforms/rover_differential_lidar_px4/model.sdf` (`<odom_topic>` of the ground-truth
  odometry publisher) and `bridge.yaml`.
- `sim/simops.py` namespacing: `/sim/<agent>/...` topics are prefixed with the agent name even
  with `namespaces: false`, and never get a second `/<agent>/` in front.
- `sim/tests/test_simops.py` topic expectations; AGENTS.md mentions of `/ground_truth`.
- Host code that subscribes to `/ground_truth` must switch to `/sim/<agent>/ground_truth`.
