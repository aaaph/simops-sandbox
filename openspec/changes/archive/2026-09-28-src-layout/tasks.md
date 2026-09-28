# Tasks

The unit suite (`pixi run test`, no Docker, no network, no autopilot build) and the Docker suite
(`pixi run pytest -m docker`, on the images that exist: `simops-sandbox-{ros,world}` and
`simops-sandbox-px4:fca3df865af3`) must pass after every group.

## 1. Package skeleton

- [x] 1.1 Add `pyproject.toml` (hatchling; packages `simops`, `worldgen` from `src/`; scripts `simops`, `worldgen`; dependencies typer, testcontainers, pydantic, pyyaml) and install it editable through pixi `[pypi-dependencies]`; add `pydantic` to the pixi env; verify `pixi install`, `pixi run simops --help` from `environments/`, and that the patched `libgz-transport.15.1.0.dylib` is still in place next to its `.orig`
- [x] 1.2 Move the code unchanged: `sim/simops.py` → `src/simops/` modules as laid out in design.md, the room generator → `src/worldgen/room.py` wrapped in a `main(argv)` (no argument parsing at import), tests → `tests/simops/`, `tests/conftest.py`; remove the `simops` pixi task and `sim/`; update `pytest.ini`, `ruff.toml` per-file ignores and the `infra/ros.Dockerfile` comment; verify `pixi run lint`, `pixi run test`, `pixi run pytest -m docker`

## 2. Domain entities (pydantic)

- [x] 2.1 `world.py`, `platform.py`, `agent.py`: `RoomSpec | WorldFile`, `Platform` (with `width()`), `Agent`, `Pose` as pydantic models with `extra="forbid"`; unit tests per model; verify `pixi run test`
- [x] 2.2 `firmware.py`: `PX4Firmware` (version / commit / default) with today's checks and messages, version order and resolution; the tests' no-network patch targets `simops.firmware.ls_remote`; verify `pixi run test`
- [x] 2.3 `environment.py`: `Environment` as the aggregate root with every check of today's `load()` plus the new "unknown keys are rejected" and "exactly one world source" requirements; `Environment.load(path)` raises one `InvalidEnvironment` naming file, key path and reason; unit tests for every scenario of the `environment` spec, asserting the named parts of the messages; verify `pixi run test`
- [x] 2.4 `bundle.py`, `session.py`, `cli.py` take and pass `Environment` / `Bundle` / `Session` instead of dicts; the CLI prints `InvalidEnvironment` and exits 1; verify `grep -rn '\["agents"\]\|\["autopilot"\]\|\["network"\]' src/simops` finds nothing, `pixi run test`, `pixi run pytest -m docker`

## 3. worldgen as a library

- [x] 3.1 `worldgen.room.generate(seed, size, obstacles, clearance, out)` and `worldgen room` CLI with `--clearance` required, without `--platform` and `--robot`; `tests/worldgen/test_room.py`: same seed gives the same SDF, and the reachability assert holds; verify `pixi run test` and `worldgen room --help`
- [x] 3.2 `bundle.build` calls `worldgen.room.generate` in-process with `clearance = first agent's Platform.width() * 1.1`; verify `simops build environments/rover_room.yaml` gives a `build/rover_room/worlds/room.sdf` byte-identical to one built before this change — checked against HEAD's generator (seed 43, 25x21: md5 ed788d1b…); found on the way: the 1.2 move had indented the SDF template (gz read it, tests missed it), fixed here

## 4. Command line from any directory

- [x] 4.1 Unit tests for "Environment path on the command line": run the Typer app (CliRunner) with `cwd` = `environments/` and a bare `rover_room.yaml`; verify `pixi run test`, and by hand `cd environments && pixi run simops build rover_room.yaml` and `simops build rover_room.yaml` inside `pixi shell`

## 5. Language and docs

- [x] 5.1 `openspec/config.yaml`: glossary gains "world source" (`RoomSpec` | `WorldFile`) and the world generation context (room, obstacle, knows nothing of simops); `rules.tasks` adds that code names — types, functions, CLI commands and help — are glossary terms; verify `openspec instructions tasks --change src-layout --json` shows the new rule
- [x] 5.2 AGENTS.md: layout (`src/simops`, `src/worldgen`, `tests/`), commands (`simops …` in `pixi shell` or `pixi run simops …` from any directory), the "How it is done" notes pointing at the new modules; verify `git grep -n 'sim/simops.py\|sim/tests\|generate_temp_room_world' -- ':!openspec/changes/archive'` finds nothing outside this change

## 6. Integration

- [x] 6.1 Run `pixi run format`, `pixi run test`, `pixi run pytest -m docker`; all pass, no `t_*` container or bundle left
