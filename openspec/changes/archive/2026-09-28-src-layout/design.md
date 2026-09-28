# Design

## Context

See proposal.md — Why. Today: `sim/simops.py` (515 lines: loading and checks, PX4 version
resolution, compose generation, spawn script, readiness, lifecycle, Typer CLI) and
`sim/generate_temp_room_world.py` (375 lines, arguments parsed at import, `robot_width()` reads
`platforms/<name>/model.sdf` of this repository, an unused `--robot` include left from the native
stack). The pixi task `simops = "python sim/simops.py"` runs from the project root. Unit tests (33)
and Docker tests (7) cover the specs and are the regression suite for this change.

## Goals / Non-Goals

**Goals:** modules named by the glossary, entities as types owning their checks, two bounded
contexts with one dependency direction, commands that work from any directory, no behavior
change beyond the `environment` delta. **Non-Goals:** keeping every spawn pose free
(`spawn-poses-clear`), a published package, an editor schema wired to `environments/`.

## Decisions

### Modules by domain concept, packages by bounded context
DDD names modules after the ubiquitous language; a layer folder (`domain/`, `application/`) is
not required by it. Top-level packages are bounded contexts; inside, one module per entity with
its logic; a module becomes a subpackage only when it grows.

```
src/simops/                      simulation context
  environment.py   Environment (aggregate root): name, world, agents, firmware, namespaces,
                   network; load(path) reads the YAML and each platform's agent.yaml
  world.py         WorldSource = RoomSpec(seed, size, obstacles) | WorldFile(path)
  platform.py      Platform: dir, model.sdf, bridge.yaml, PX4 airframe; width() from model.sdf
  agent.py         Agent(name, platform, pose), Pose (x y z roll pitch yaw), quaternion()
  firmware.py      PX4Firmware: Version | Commit | default; parse/order versions, tags via
                   git ls-remote, resolve() -> (ref, commit)
  bundle.py        Bundle + build(Environment) -> Bundle: compose.yaml, spawn.sh, bridge.yaml,
                   worlds/, platforms/
  session.py       Session(bundle): project(), up / down / run, readiness, host_env, log tail
  cli.py           Typer app: build, up, down, host-env, gui, run
src/worldgen/                    world generation context - knows nothing of simops
  room.py          Room / obstacles, generate(...) -> SDF, the reachability check
  cli.py           `worldgen room ...` (the generator's options minus --platform/--robot)
tests/simops/, tests/worldgen/, tests/conftest.py
```

Dependencies go one way: `cli → session → bundle → environment → {agent, platform, world,
firmware}`, and `bundle → worldgen`. worldgen imports nothing from simops.

### "World" in two contexts
In simops the world is what an environment names: a `RoomSpec` or a `WorldFile` (glossary term
"world source"). In worldgen a `Room` is what gets generated. Different types, different names,
so `simops.world.RoomSpec` and `worldgen.room.Room` cannot be confused.

### pydantic models, strict
Entities are pydantic v2 models with `extra="forbid"` (the new "unknown keys" requirement).
Validators carry today's checks and messages: `robots` → "is now `agents`", `ref` → "`version`
or `commit`", both version and commit, 40-hex commit, version format, < 1.18 with the C++14
reason, several agents without namespaces, exactly one world source. `Environment.load()` turns a
pydantic `ValidationError` into one `InvalidEnvironment` (not `EnvironmentError`, a builtin alias of `OSError`) whose message names the file, the key path
and the reason; the CLI prints it and exits 1, as `sys.exit(message)` does today. Loaded paths
(platform, world file) are resolved against the environment file's directory, as today.
*Alternative:* dataclasses — no dependency, but no generated schema and hand-written checks.

### Installed commands instead of a pixi task
`pyproject.toml` (hatchling) declares packages `simops` and `worldgen` from `src/` and the scripts
`simops = "simops.cli:app"`, `worldgen = "worldgen.cli:app"`. pixi installs the project editable
through `[pypi-dependencies]` (`simops-sandbox = { path = ".", editable = true }`), and the
`simops` task is removed: `pixi run simops …` then finds the installed command and runs it in the
caller's directory, so paths resolve where they are typed. The repository root (for `build/` and
`infra/`) is found from the package location (`src/simops/../..`) — valid for editable installs of
this repository only, which is all there is today.
*Alternative:* resolve arguments against pixi's `INIT_CWD` — fixes one symptom, keeps a script.

### worldgen as a library, simops measures the platform
`robot_width()` moves to `simops.platform.Platform.width()`. simops calls
`worldgen.room.generate(seed, size, obstacles, clearance=width * 1.1, out=...)` in-process instead
of running the script; worldgen's CLI takes `--clearance` explicitly (required) and drops
`--platform` and the unused `--robot`. The first agent's platform keeps deciding the clearance,
so rooms stay byte-identical; every spawn pose and the widest agent are `spawn-poses-clear`.

### Tests follow the modules
`tests/simops/test_{environment,firmware,bundle,agent}.py` (unit), `tests/simops/test_session_docker.py`
(`-m docker`), `tests/worldgen/test_room.py` (determinism, reachability assert), shared
`tests/conftest.py` (removes new bundles; the no-network `ls_remote` patch now targets
`simops.firmware`). `pytest.ini`: `testpaths = tests`, no `pythonpath` (the packages are installed).

## Risks / Trade-offs

- [The editable install needs a build backend (hatchling) fetched by pixi/uv on first install]
  → one-time network access, like any `pixi install`; verified in the tasks.
- [`pixi install` touching the env may restore the conda gz-transport] → check the patched
  library after install, as in earlier changes.
- [pydantic error texts differ from today's] → the spec scenarios name what each message must
  contain; tests assert those parts, not whole strings.
- [A 515-line file split in one go] → move code without changing it first, run both suites, then
  replace dicts with models module by module.

## Migration Plan

One change, no data migration. Rollback: revert the commit. Users run `simops …` or
`pixi run simops …` as before; `pixi run python sim/simops.py` stops existing.
