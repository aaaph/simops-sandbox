# Proposal

## Why

The PX4 firmware sits in the environment, next to the world and the agents, while the airframe
it runs sits in the platform. The two cannot be separated: an airframe exists only in some
firmware versions, and its parameters are tuned for them. Keeping them apart lets an environment
pick a firmware its platforms' airframes were never made for. By principle 4, what cannot be
separated from the body belongs to the platform. That leaves the environment as only the scene:
the world, the agents and where they stand, and how the session is reached.

The world key `room` also reads as "a room" rather than an instruction. `generate_room` says
that `build` generates it, and leaves room for `generate_maze` next to it.

## What Changes

- **BREAKING** A platform's `agent.yaml` names its whole autopilot: `autopilot.px4` holds the
  `airframe` and the firmware (`version` or `commit`, or neither for the default, and `repo`),
  with the same rules the environment's `autopilot.px4` has today.
- **BREAKING** The environment no longer has `autopilot`. An environment that still sets it
  fails loading with a message saying the firmware now lives in the platform's `agent.yaml`.
- Each agent's PX4 runs the firmware of its platform. Agents on platforms with different
  firmware run different PX4 images; `build` resolves each distinct firmware once.
- An invalid `agent.yaml` (unknown key, both `version` and `commit`, too old a version, missing
  airframe) fails loading the environment, naming the `agent.yaml` file, the key and why.
- For now every platform must have `autopilot.px4` with an `airframe`: every agent still gets
  a PX4. Agents without an autopilot come in a later change (`agents-without-autopilot`).
- **BREAKING** The world source key `room` becomes `generate_room`; `file` stays.
- `environments/rover_room.yaml` takes the new format, and
  `platforms/rover_differential_lidar_px4/agent.yaml` gets its firmware (`v1.18.0-rc1`).
- The glossary follows: a platform's `agent.yaml` holds the airframe and firmware, the
  environment no longer picks firmware (principle 4), the room world source is `generate_room`.

Out of scope: overriding a platform's firmware from the environment or per agent (not needed
yet); agents without an autopilot and manual control (next change).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `environment`: no `autopilot`; the world source keys are `generate_room` and `file`; a
  platform's `agent.yaml` is validated as part of loading.
- `autopilot`: the firmware comes from the agent's platform, not from the environment, and may
  differ between agents; the PX4 platform requirement is stated in the platform.
- `host-access`: host code talking to an agent's PX4 uses `px4_msgs` of that agent's platform
  firmware.

## Impact

- `src/simops/platform.py` (reads and validates `agent.yaml` as a model),
  `src/simops/firmware.py` (the firmware of a platform), `src/simops/environment.py` (drops
  `Autopilot`), `src/simops/world.py` (`generate_room`), `src/simops/bundle.py` (firmware per
  agent's platform in `compose` and `build`).
- `environments/rover_room.yaml`, `platforms/rover_differential_lidar_px4/agent.yaml`; the
  sketch `environments/rover_env_spec.yaml` is folded into `rover_room.yaml` and removed.
- Tests: `tests/simops/test_environment.py`, `test_bundle.py`, `conftest.py`, new
  `test_platform.py`.
- `openspec/config.yaml` glossary and principle 4; AGENTS.md mentions of the environment's
  firmware.
- Any environment outside this repository with `autopilot` or `world.room` has to be rewritten.
