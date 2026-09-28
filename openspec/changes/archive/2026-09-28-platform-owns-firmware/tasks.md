# Tasks

The unit suite (`pixi run test`: no Docker, no network, no autopilot build) must pass after every
group. The Docker suite (`pixi run pytest -m docker`) runs on the images that already exist
(`simops-sandbox-{ros,world}`, `simops-sandbox-px4:fca3df865af3`, which is `v1.18.0-rc1`): the
firmware stays `v1.18.0-rc1`, so no image is built.

## 1. The platform owns its autopilot

- [x] 1.1 `firmware.py`: `PX4Autopilot(PX4Firmware)` with a required `airframe: int` and a `firmware` property returning the plain `PX4Firmware`; move the pydantic-error describing function out of `environment.py` to a module both `platform.py` and `environment.py` import without a cycle, taking the document's name for the unknown-key message; verify `pixi run test`
- [x] 1.2 `platform.py`: `Platform.load` validates `agent.yaml` (`autopilot.px4` required, `extra="forbid"` at every level) into `Platform.px4: PX4Autopilot`, replacing `px4_airframe`; an invalid file raises one `ValueError` starting with the `agent.yaml` path; new `tests/simops/test_platform.py` covers the `autopilot` spec's loading scenarios (missing airframe, old `ref`, both version and commit, short commit, version below 1.18, unknown key under `autopilot`, version with and without `v` accepted), writing `agent.yaml` into a copy of the PX4 platform in `tmp_path`; verify `pixi run test`
- [x] 1.3 `platforms/rover_differential_lidar_px4/agent.yaml`: `autopilot.px4.version: v1.18.0-rc1` next to `airframe: 50000`, with the `px4_msgs` type-hash comment moved from `rover_room.yaml`; verify `Platform.load` of it in `pixi run test`

## 2. The environment is only the scene

- [x] 2.1 `environment.py`: drop `Autopilot` and the `autopilot` field; a before-validator rejects `autopilot` with a message saying the firmware is set in each platform's `agent.yaml`; `world.py`: `World.room` → `World.generate_room`, the one-source message names `generate_room` and `file`; verify `pixi run test`
- [x] 2.2 `environments/rover_room.yaml` in the format of `environments/rover_env_spec.yaml` (no `autopilot`, `generate_room`), keeping its explanatory comments where they still apply; remove `rover_env_spec.yaml`; verify `pixi run simops build environments/rover_room.yaml` builds with PX4 `v1.18.0-rc1` and `build/rover_room/worlds/room.sdf` is byte-identical to the one before this change
- [x] 2.3 Tests: `tests/simops/conftest.py` gains a `platform` fixture (a copy of the PX4 platform in `tmp_path` with `agent.yaml` keys replaced, next to a link to `rover_differential_lidar` whose meshes it borrows), and `variant` leaves an absolute agent `platform` as given; `test_environment.py` covers every scenario of the `environment` delta (old `autopilot` key, `generate_room`, both and neither source, old `room` key, invalid `agent.yaml` naming that file) and drops the firmware cases that moved to `test_platform.py`; verify `pixi run test`

## 3. Firmware per agent in the bundle

- [x] 3.1 `bundle.py`: `build` resolves each distinct `platform.px4.firmware` once and prints one line per firmware; `compose` takes the resolutions and gives each `px4-<agent>` the build args, image and `PX4_SYS_AUTOSTART` of its own platform; `test_bundle.py`: `test_firmware_names_the_image` moves to platform variants, and a new test builds two agents on platforms with different versions and checks each `px4-<agent>` image; verify `pixi run test`

## 4. Language and docs

- [x] 4.1 `openspec/config.yaml`: platform's `agent.yaml` holds the PX4 airframe and firmware; environment is world, agents, namespaces, router port; world source is `generate_room` or `file`; principle 4 without "and firmware"; verify `openspec instructions proposal --change platform-owns-firmware --json` shows the new wording
- [x] 4.2 AGENTS.md: the environment's firmware becomes the platform's (the PX4 version paragraph, "A platform ... agent.yaml" note, "PX4 SITL of the environment's firmware"); verify `git grep -n "environment's firmware\|autopilot.px4\|room: {" -- ':!openspec/changes/archive'` shows only the new meaning

## 5. Integration

- [x] 5.1 Run `pixi run format`, `pixi run lint`, `pixi run test`, `pixi run pytest -m docker` (existing images only); all pass, no test container or bundle left behind
