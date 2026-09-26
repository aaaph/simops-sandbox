# Tasks

Group 0 renames robots to agents; after it, behavior does not change: every task adds a test
(or a recorded manual check) for a spec scenario no test covers yet. Already covered by `sim/tests/test_simops.py`: bundle contents and
borrowed meshes, empty generated room, merged bridge with namespaces, spawn after world,
airframe and instances, one partition per scenario. A test that fails here is a spec/code
mismatch: fix the spec or record it as a known gap, do not change behavior in this change.

## 0. Rename robots to agents

- [ ] 0.1 Rename the scenario key `robots:` to `agents:` in `sim/simops.py` (loading, build, compose, readiness, messages and docstrings), `scenarios/rover_room.yaml` and `sim/tests/test_simops.py`; a scenario still using `robots:` fails loading with a message naming `agents:`; verify with `pixi run test` and `pixi run simops build scenarios/rover_room.yaml`
- [ ] 0.2 Rename `platforms/rover_differential_lidar_px4/platform.yaml` to `agent.yaml` and read that name in `sim/simops.py`; verify `build/rover_room/compose.yaml` still gives `px4-rover1` airframe 50000 via `pixi run test`
- [ ] 0.3 Replace robot/platform.yaml wording with agent/agent.yaml in AGENTS.md's Docker-sim section and in comments of `infra/*.Dockerfile`; verify with `grep -rn 'robots:\|platform\.yaml' AGENTS.md infra sim scenarios` returning nothing

## 1. Scenario and bundle (unit, no Docker)

- [ ] 1.1 In `sim/tests/test_simops.py`, test `scenario`: defaults (`namespaces: false`, port 7447), paths resolved against the scenario file with a different working directory, two agents without namespaces exit with a message naming `namespaces: true`; verify with `pixi run test`
- [ ] 1.2 Test `bundle`: building twice gives identical `worlds/room.sdf`; a stale file in `build/<name>/` is gone after a rebuild; a `world.file` whose `<world>` has no name fails naming the file; verify with `pixi run test`
- [ ] 1.3 Test the compose wiring behind `agent-spawn`, `autopilot` and `sim-lifecycle`: `spawn` and every `px4-<agent>` restart with `world`; PX4 image is `simops-sandbox-px4:<ref[:12]>`; compose project is named after the scenario and the router publishes `router_port` on TCP and UDP; verify with `pixi run test`
- [ ] 1.4 Test `host-access` env: `host_env` of `rover_room` has `GZ_PARTITION=rover_room`, `GZ_TRANSPORT_IMPLEMENTATION=zenoh` and zenoh endpoints `tcp/localhost:7447` for both gz and ROS; with router port 7448 both endpoints move to 7448; verify with `pixi run test`

## 2. Lifecycle against Docker (slow, opt-in)

- [ ] 2.1 Add a `docker` pytest marker, excluded from the default run (`addopts = -m "not docker"` in `pytest.ini`); verify `pixi run test` still runs only the unit tests and `pixi run pytest -m docker --collect-only` finds the new file
- [ ] 2.2 In `sim/tests/test_simops_docker.py`, test `up`/`down`: `up` of `rover_room` returns 0 with `rover1` in the world and sim time advancing; `down` leaves no container of the project; verify with `pixi run pytest -m docker`
- [ ] 2.3 Test the failure paths: `up --timeout 1` exits non-zero and leaves no container; `run -- sh -c 'exit 3'` exits 3 and leaves no container; verify with `pixi run pytest -m docker`
- [ ] 2.4 Test world restart: after `docker compose -p rover_room restart world`, `rover1` is back in the world and `px4-rover1` restarted; verify with `pixi run pytest -m docker`
- [ ] 2.5 Test namespaces end to end: a two-agent scenario with `namespaces: true` shows `/rover1/scan`, `/rover2/scan`, `/rover2/fmu/out/...` and one `/clock` on the host (`ros2 topic list` under `simops env`); verify with `pixi run pytest -m docker`
- [ ] 2.6 Test isolation: `rover_room` on 7447 and a copy named `rover_room_b` on 7448 up at once, each host env sees only its own world; verify with `pixi run pytest -m docker`

## 3. Manual checks and docs

- [ ] 3.1 Manually check `simops gui` shows the world with `rover1`, and record the result in this task
- [ ] 3.2 Manually check that host code with `px4_msgs` from another PX4 commit sees no `/fmu/out/*` data while matching `px4_msgs` does, and record the result in this task
- [ ] 3.3 In AGENTS.md, point the scenario/lifecycle contract paragraphs to `openspec/specs/` instead of restating them, keeping quirks, workarounds and how-to; verify every command AGENTS.md shows still runs as written
