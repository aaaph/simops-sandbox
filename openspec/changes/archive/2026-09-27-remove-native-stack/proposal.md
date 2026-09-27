# Proposal

## Why

The repo carries two simulations: simops (Docker, PX4, specs) and the native host stack it
replaced (`pixi run up`: gz + ros_gz_bridge + robot_localization + SLAM + rerun on the Mac, no
autopilot). The native stack is no longer used, has no spec, and by the project's principle its
ROS nodes (state estimation, TF, visualisation) belong to the user's stack, not to the sim. It
costs dependencies, pixi tasks, tests and half of AGENTS.md — and it hides a latent break: a
Docker test reads `worlds/temp_room.sdf`, a gitignored file only the native `world` task writes.

## What Changes

- Remove the native stack: `sim/stack.py`, `sim/doctor.py`, `sim/frame_publisher.py`,
  `sim/odom_covariance.py`, `sim/rerun_bridge.py`, `sim/bridge_fallback.yaml`, `launch/`, their
  tests (`test_stack.py`, `test_frame_publisher.py`), the pixi tasks `world`, `zenoh`,
  `bringup`, `slam`, `rerun_bridge`, `up`, `down`, `doctor`, `px4-build`, `px4`, `teleop`.
- Remove what only it needs: dependencies `ros-lyrical-slam-toolbox`, `ros-lyrical-nav2-bringup`,
  `ros-lyrical-robot-localization`, `ros-lyrical-ros-gz`, `rerun-sdk`; the `PX4_DIR` activation
  variable and PX4/`models` entries of `GZ_SIM_RESOURCE_PATH`; `platforms/rover_differential_lidar/`
  `ekf.yaml` and `slam.yaml`; `.stack/` and `worlds/temp_room.sdf` in `.gitignore`; ruff ignores
  for removed files.
- Remove the six unused gz tutorial worlds in `worlds/`.
- Replace `scipy` (two roll/pitch/yaw rotations, in `simops.py` and the room generator) with
  `math`, and drop the dependency.
- The Docker test for a failed `up` generates its own world instead of reading `temp_room.sdf`.
- Tests remove the `build/<name>/` bundles they create.
- AGENTS.md: drop "Running the simulation" and the native-only quirks (IMU at 30 Hz, odometry
  covariance, `rmw_zenohd` on 7447); keep the stale ros2 daemon quirk, which holds for host ROS.

Kept: `platforms/rover_differential_lidar/` (`model.sdf`, `bridge.yaml`, meshes) — the PX4 platform
takes its meshes from it and it is the future agent without an autopilot; `ros-lyrical-desktop`
(host `ros2`, rmw_zenoh), `gz-sim` and `infra/build-gz-transport.sh` (native GUI).
`odom_covariance`'s logic returns inside the sim container with the no-autopilot agent; git keeps it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — the native stack never had a spec, and simops' behavior does not change
(`skip_specs: true`).

## Impact

- ~850 lines of code and two test files removed; 11 pixi tasks and 6 dependencies fewer;
  `pixi.lock` shrinks.
- AGENTS.md loses its first section; `README`/docs pointing at `pixi run up` go with it.
- The native gz GUI (`simops gui`) must still find the rover meshes through
  `GZ_SIM_RESOURCE_PATH` — checked by hand in the tasks.
