# Tasks

Starts after `platform-inline-and-base` is applied (platforms hold their bridge entries as values).

## 1. The world bridges /clock

- [ ] 1.1 In `src/simops/world.py`, the world's bridge entries: the `/clock` entry
  (`rosgraph_msgs/msg/Clock` from gz `/clock`, `GZ_TO_ROS`), the same for every world source. In
  `src/simops/bundle.py`, `bridge.yaml` starts with them, then every agent's entries, each once;
  drop the `/clock` special case from namespacing. Verify: tests in 1.3.
- [ ] 1.2 In `src/simops/platform.py`, a bridge entry whose `gz_topic_name` or `ros_topic_name` is
  `/clock` fails validation saying the world bridges `/clock` (the message carries where the
  platform is written, as other platform errors do). Remove `/clock` from
  `platforms/rover_differential_lidar_px4/bridge.yaml`, from the tests' copy
  `tests/simops/platforms/rover_differential_lidar_px4/bridge.yaml` and from the written-out bridge in
  `tests/simops/environments/rover_platform_inline.yaml` (the three-forms test of
  `platform-inline-and-base` must still pass). Verify: tests in 1.3; `pixi run simops
  build environments/rover_room.yaml` writes a `bridge.yaml` with `/clock` first (network: PX4
  tags).
- [ ] 1.3 Unit tests, in memory: `test_bundle.py` — `/clock` first then the rover's three
  entries; exactly `/clock` for an inline platform with `bridge: []`; `/clock` once with two
  namespaced agents. `test_platform.py` — an inline platform whose bridge lists `/clock` (as gz or
  as ROS topic) fails naming `/clock` and the world. Verify: `pixi run pytest
  tests/simops/test_bundle.py tests/simops/test_platform.py --durations=5` passes, no test over
  ~50 ms.
- [ ] 1.4 Docs: `AGENTS.md` — the `sim-sensors` line says `/clock` comes from the world and the
  rest from the agents' bridge entries; the `sim-only` glossary entry in `openspec/config.yaml`
  if it needs to say so. Verify: `pixi run lint` passes and `openspec validate world-owns-clock
  --strict` passes.

## 2. Integration

- [ ] 2.1 A session. Verify: `pixi run pytest -m "docker and not scenario"` passes on existing
  images (Docker), and with `environments/rover_empty_world.yaml` up, `ros2 topic list` through
  `simops host-env` shows `/clock` once; `simops down` leaves no container of it.
