# Proposal

## Why

A platform can only be a directory today (`model.sdf` + `bridge.yaml` + `agent.yaml`), so trying
the same body with another firmware or another bridge means copying the directory, and an
environment cannot describe a platform by itself. The platform should be one document that reads
the same in a platform file and inline in an environment, with an explicit `base` to build on,
in the spirit of kustomize.

## What Changes

- A platform is one document with the keys `model` (the path to its SDF model), `bridge` (the
  bridge entries, or the path to a file holding them), `autopilot` (as in `agent.yaml` today) and
  an optional `base`.
- **BREAKING** A platform directory holds `platform.yaml` instead of `agent.yaml`; `model` and
  `bridge` name its files. A directory with an `agent.yaml` and no `platform.yaml` fails loading
  with a message saying `agent.yaml` is now `platform.yaml`. `platforms/rover_differential_lidar_px4`
  is migrated.
- An agent's `platform` is either a platform directory (as now) or the same document inline.
- `base: <platform directory>` lays the document over that platform: mappings merge, a list or a
  scalar replaces, `null` removes a key (JSON Merge Patch). A `platform.yaml` may have a `base`
  too; a cycle fails loading, naming the chain.
- Every path is relative to the file it is written in: a `platform.yaml`'s to its directory, an
  inline platform's to the environment file, each before the documents are merged.
- The model's directory is the model: the bundle copies it under its own name, as it copies a
  platform directory now, and spawns the agent from the model's file name, not a fixed
  `model.sdf`.

## Capabilities

### New Capabilities
- `platform`: the platform document — its keys, a platform directory and `platform.yaml`, inline
  platforms, `base` and how documents merge, paths, the model's directory, errors.

### Modified Capabilities
- `environment`: an agent's `platform` is a directory or an inline platform (see `platform`); the
  platform-directory contents, the `agent.yaml` error scenario and unknown keys move to
  `platform.yaml`.
- `autopilot`: the airframe and firmware come from the platform's `autopilot.px4`, wherever the
  platform is written, not from `agent.yaml`.
- `bundle`: `platforms/` holds every model's directory, and each agent is spawned from its model's
  own file.
- `agent-interface`: an agent's bridged topics are its platform's `bridge` entries, wherever the
  platform is written.
- `host-access`: host code takes `px4_msgs` from the firmware in the platform's `autopilot.px4`,
  not `agent.yaml`.

## Impact

- Code: `src/simops/platform.py` (the document, loading, merge, paths), `src/simops/agent.py`
  (`platform` takes a path or a mapping), `src/simops/bundle.py` (bridge entries from the
  platform's values instead of reading `bridge.yaml`; the model's file name in
  `spawn.sh`).
- Files: `platforms/rover_differential_lidar_px4/agent.yaml` becomes `platform.yaml`.
- Tests: `tests/simops/conftest.py` (`platform`, `platform_dir` fixtures), `test_platform.py`,
  `test_environment.py`, `test_bundle.py`.
- Docs: `AGENTS.md` and the glossary in `openspec/config.yaml` (platform, `platform.yaml`, base).
- No new dependency; no change to images, sessions or the host side.
- `/clock` stays where it is (each platform's bridge entries, listed once by the bundle); moving
  it to the world is the separate change `world-owns-clock`.
