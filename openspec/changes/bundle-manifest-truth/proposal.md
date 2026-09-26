# Proposal

## Why

Task and judge are the developer's code: they drive the agent through the usual operator tools
(MAVSDK, px4-ros2, QGC) and compare the agent's own estimate with ground truth. For that they
need facts only simops knows, and today none of them is written down:
- where each agent started in the world — the agent's estimate lives in its own frame starting
  at that pose, so without it estimate and ground truth cannot be compared;
- where to connect the operator tools to each agent (its MAVLink port follows from the PX4
  instance number, which the user would have to work out);
- the true map of a generated world, to judge mapping;
- what exactly a bundle was built from, to know later what a result was obtained on.

## What Changes

- Every bundle SHALL contain `manifest.yaml`: the scenario it was built from (path and content
  hash), the simops revision, the PX4 ref, the world name and its geographic origin, and per
  agent its platform, start pose in the world frame, topic prefix, PX4 instance and MAVLink
  ports.
- A bundle with a generated room SHALL contain `truth/map.pgm` and `truth/map.yaml` — the room's
  occupancy grid in the ROS map_server format, in the world frame.
- The manifest is the one file the future simops SDK (sim control + ground truth) reads to find
  its way around a bundle.

Out of scope: a true map for `world.file` worlds, live ground truth (see `sim-oracle-namespace`),
the SDK itself.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `bundle`: adds the manifest and, for generated rooms, the true map.

Depends on `baseline-simops` being archived, which creates `bundle`.

## Impact

- `sim/simops.py` (`build` writes the manifest), `sim/generate_temp_room_world.py` (writes the
  occupancy grid it already computes for its reachability check).
- `sim/tests/test_simops.py`: manifest content, map matches the world's obstacles.
- AGENTS.md: the bundle paragraph lists the new files.
