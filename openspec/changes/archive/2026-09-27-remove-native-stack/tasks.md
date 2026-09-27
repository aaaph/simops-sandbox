# Tasks

simops behavior does not change: `pixi run test` and `pixi run pytest -m docker` are the
regression suite and must pass after every group. Removed files stay recoverable from git.

## 1. Make the Docker tests independent of the native stack

- [x] 1.1 In `test_failed_up_leaves_nothing`, generate the world into `tmp_path` with `sim/generate_temp_room_world.py` (with its default platform: the broken model is never passed to it) instead of reading `worlds/temp_room.sdf`; verify by moving `worlds/temp_room.sdf` away and running `pixi run pytest -m docker -k failed_up`
- [x] 1.2 Make the unit and Docker tests remove the `build/<name>/` bundles they create (a fixture that deletes them after the test); verify `ls build/` shows no `t_*`, `seeded`, `stale`, `rover_pair`, `defaults`, `moved`, `nameless`, `pair` after `pixi run test` and `pixi run pytest -m docker`

## 2. Replace scipy with math

- [x] 2.1 In `sim/simops.py`, compute the spawn quaternion from roll/pitch/yaw with `math` (extrinsic x-y-z, as ROS rpy); add a unit test comparing it with known values (identity, yaw 90 deg, roll 90 deg, a mixed rotation); verify `pixi run test`
- [x] 2.2 In `sim/generate_temp_room_world.py`, compute the rotation matrix row it needs with `math`; verify `pixi run simops build scenarios/rover_room.yaml` gives a byte-identical `build/rover_room/worlds/room.sdf` before and after, and `grep -rn scipy sim/` finds nothing
- [x] 2.3 Remove `scipy` from `pixi.toml`; verify `pixi install` and `pixi run test`

## 3. Remove the native stack

- [x] 3.1 Delete `sim/stack.py`, `sim/doctor.py`, `sim/frame_publisher.py`, `sim/odom_covariance.py`, `sim/rerun_bridge.py`, `sim/bridge_fallback.yaml`, `launch/`, `sim/tests/test_stack.py`, `sim/tests/test_frame_publisher.py`, and their entries in `ruff.toml`; update `pytest.ini` `testpaths` (no `launch`); verify `pixi run lint` and `pixi run test`
- [x] 3.2 Remove the pixi tasks `world`, `zenoh`, `bringup`, `slam`, `rerun_bridge`, `up`, `down`, `doctor`, `px4-build`, `px4`, `teleop`, and the dependencies `ros-lyrical-slam-toolbox`, `ros-lyrical-nav2-bringup`, `ros-lyrical-robot-localization`, `ros-lyrical-ros-gz`, `rerun-sdk`; verify `pixi install` succeeds and `pixi task list` shows only `simops`, `lint`, `test`, `format`
- [x] 3.3 Drop `PX4_DIR` from `[activation.env]` and trim `GZ_SIM_RESOURCE_PATH` to `$PIXI_PROJECT_ROOT/platforms`; verify `infra/build-gz-transport.sh` is still in place (patched `libgz-transport.15.1.0.dylib` next to its `.orig`) after `pixi install`, re-running the script if `pixi` restored the conda library
- [x] 3.4 Delete `platforms/rover_differential_lidar/ekf.yaml` and `slam.yaml`, the six gz tutorial worlds in `worlds/` (`building_robot`, `jetty_world`, `moving_robot`, `sensor_tutorial`, `test_world`, `world_demo`), and the `.gitignore` lines for `worlds/temp_room.sdf` and `.stack/`; verify `git grep -n 'ekf.yaml\|slam.yaml\|temp_room\|\.stack'` finds nothing outside `openspec/`

## 4. Docs

- [x] 4.1 In AGENTS.md, remove "Running the simulation" and the quirks about the 30 Hz IMU, odometry covariance and `rmw_zenohd` on 7447; keep the stale ros2 daemon quirk; rewrite the intro line so the Docker sim is the way to run it; replace `readme.md`'s title if it still says otherwise; verify `git grep -n 'pixi run up\|pixi run down\|doctor\|bringup\|rerun' -- AGENTS.md readme.md` finds nothing

## 5. Integration

- [x] 5.1 Run `pixi run lint`, `pixi run test` and `pixi run pytest -m docker`; all pass, no `t_*` container or bundle left
- [x] 5.2 Manually: `pixi run simops up scenarios/rover_room.yaml` and `pixi run simops gui scenarios/rover_room.yaml` show the rover with its meshes (the trimmed `GZ_SIM_RESOURCE_PATH` still finds them); record the result in this task — 2026-09-27: `simops up`, `gui` on rover_room: the rover shows with its meshes, driven with the QGC joystick; `simops down` after
