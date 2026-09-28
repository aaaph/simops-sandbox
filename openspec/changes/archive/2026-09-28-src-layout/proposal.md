# Proposal

## Why

`sim/` is a folder of scripts: `simops.py` (515 lines) passes the raw YAML dict of an environment
everywhere, so the glossary's entities — platform, agent, environment, bundle, session, PX4
firmware — exist in the docs but not in the code. The room generator is a script with its
arguments parsed at import time, reads platforms of this repository by name, and is run as a
separate process. And `pixi run simops` runs from the project root whatever directory it is
called from, so `cd environments && pixi run simops up rover_room.yaml` fails with a missing file.

## What Changes

- A `src/` layout with two bounded contexts, each an installable package in one `pyproject.toml`:
  - `src/simops/` — the simulation context, one module per glossary entity with its logic:
    `environment`, `world`, `platform`, `agent`, `firmware`, `bundle`, `session`, and `cli`.
  - `src/worldgen/` — the world generation context: `room` (rooms and obstacles, `generate()`)
    with its own `worldgen` command; it knows nothing of simops (no platforms, no agents).
- Entities are pydantic models: the checks `load()` makes today move into them, so an invalid
  environment cannot be built. Their JSON Schema becomes available for editors (not wired to
  `environments/*.yaml` in this change).
- Both packages are installed editable into the pixi environment: the `simops` and `worldgen`
  commands run in the directory they are called from; `pixi run simops …` keeps working and now
  resolves relative paths from where it is called.
- simops measures the platform's width itself and passes the clearance to worldgen, which it
  calls as a library instead of a subprocess; generated rooms stay byte-identical.
- Loading is stricter where a mistake used to pass silently: unknown keys in an environment are
  rejected, and a world given as both `room` and `file` is an error instead of `file` winning.
- Tests move to `tests/simops/` and `tests/worldgen/`; `sim/` is gone.
- The glossary gains "world source" (`RoomSpec` | `WorldFile`, the environment's view of its
  world) and the world generation context (room, obstacle); `rules.tasks` adds that code names —
  types, functions, CLI commands and help — are glossary terms.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `environment`: the environment path on the command line is resolved against the directory
  the command runs in; unknown keys are rejected; a world source is exactly one of `room` or
  `file`.

## Impact

- New `pyproject.toml`; `pixi.toml` (pydantic, the editable packages, the `simops` task removed);
  `pytest.ini`, `ruff.toml`; `sim/` → `src/simops/`, `src/worldgen/`, `tests/`.
- `infra/ros.Dockerfile` comment; AGENTS.md (layout, commands); `openspec/config.yaml`
  (glossary, rules).
- Bundles keep being written to `<repository>/build/<name>/` and built from this repository's
  `infra/` — the packages are editable installs of this repository, not yet usable elsewhere.
- Follow-up change `spawn-poses-clear`: worldgen keeps every agent's spawn pose free (today only
  the origin), closing the known gap in `bundle`.
