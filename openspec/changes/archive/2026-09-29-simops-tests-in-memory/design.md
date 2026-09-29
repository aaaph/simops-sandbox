# Design

## Context

See proposal.md — Why. Today `bundle.build(environment)` does everything in one pass: `rmtree`
of `build/<name>/`, copies the platforms (and those whose meshes they borrow), generates or copies
the world and parses the written file for its name, rewrites and writes the namespaced models,
writes `spawn.sh`, `bridge.yaml`, `compose.yaml`, and returns `Bundle(environment, dir, compose,
world_name)`. `Session.up` calls it; `Session.ready` needs only `world_name`; the CLI prints
`bundle.dir`. `Agent` already accepts a `Platform` instance in place of a path
(`agent.py:_platform_dir`), so an environment can be built in memory without new model code.

## Goals / Non-Goals

**Goals:** computation separate from I/O in loading and building; unit tests on values;
identical bundles and command output.
**Non-Goals:** in-memory Docker tests; changing where bundles go (`build/<name>/`, see
`session-isolation`); the manifest (`bundle-manifest-truth`).

## Decisions

### Read, then parse; compute, then write
```
  Environment.load(path)  = read path    -> Environment.parse(data, base=path.parent, origin=path)
  Platform.load(dir)      = check files  -> Platform.parse(dir, yaml of dir/agent.yaml)
  simops build / up       = build(env)   -> Bundle.write(build/<name>/)
```
`parse` does everything `load` does today except the read, and keeps its messages: an
`InvalidEnvironment` starts with `origin`, a platform's `ValueError` with `<dir>/agent.yaml`.
`build` still reads inputs — platform files, a `file` world, the PX4 tags through
`ls_remote` (patched in unit tests) — but writes nothing. Alternative, faking the filesystem
(pyfakefs) or keeping `tmp_path` everywhere: the tests would still test the round trip through
YAML and XML rather than the values.

### `build()` returns the bundle; `Bundle.write(dir)` puts it on disk
`Bundle` (frozen) holds:
- `environment`, `world_name`;
- `compose: dict`, `spawn: str`, `bridge: list[dict]`;
- `world: SdfWorld | Path` — generated, or the ready-made file to copy — and `world_file: str`
  (its name in `worlds/`, the compose `SIM_WORLD` stem) and `world_summary: str | None`;
- `platforms: dict[str, Path]` — bundle name to source directory, borrowed ones included, and
  one `<p>.<agent>` copy per agent with namespaces;
- `models: dict[str, str]` — bundle name to the rewritten `model.sdf` text of each namespaced copy;
- `firmware_lines: list[str]` — the `PX4 …` lines, see below.

`write(dir) -> Path` removes `dir`, copies `platforms`, writes `models` over their copies, the
world, `spawn.sh`, `bridge.yaml` and `compose.yaml`, prints the world summary, and returns `dir`.
The name keeps meaning what the glossary says, an environment built for docker compose; the
glossary adds that it exists in memory until written. `Bundle.dir` goes: the directory is where
it was written, which the caller knows. Alternative, a separate `BundlePlan` type: a second
name for the same thing, and a glossary term with no behavior of its own.

### World name without a file
A generated world's name is `SdfWorld.name`; a `file` world is parsed where it is (a read of the
input), and a missing `<world name=...>` still exits naming the file — now the source file rather
than its copy in the bundle, which is what the user has to fix.

### `build` prints nothing; `write` prints today's lines in today's order
Today the world line (`<path>: 17 boxes + 11 cylinders, … seed 0`) comes first, then one
`PX4 <ref> = <commit>` line per firmware. The world line needs the path in the bundle, so `write`
prints both, in that order: `f"{sdf}: {bundle.world_summary}"`, then `bundle.firmware_lines`
(a `list[str]` field, filled by `build` as it resolves each firmware). The summary text comes
from worldgen: `room.summary(world, clearance=, seed=, size=, obstacles=)` and
`empty.summary(clearance=)`, the text `generate` prints after `out: `, moved into one function
each that `generate` also uses. A pure `build` also keeps unit tests free of printed noise.

### Test fixtures in memory
`tests/simops/conftest.py`:
- `environment(name, **keys) -> Environment`: rover_room's document with `keys` replaced and
  relative platforms pointing at the PX4 platform, through `Environment.parse(origin=<name>.yaml)`;
- `platform(**px4) -> Platform`: the PX4 platform's directory with `agent.yaml` replaced in
  memory, through `Platform.parse`, so its checks run;
- `variant` and the file-writing `platform` stay only for the tests listed in the proposal as
  file behavior, renamed `environment_file` and `platform_dir`.

## Risks / Trade-offs

- [A bundle written differently than before would pass the in-memory tests] → baseline: before
  touching the code, `simops build` both environments in `environments/` and keep the trees and
  stdout; after, `diff -r` and compare stdout. The on-disk bundle test stays.
- [`Bundle` carries an `SdfWorld` (a dataclass) inside a pydantic model] →
  `arbitrary_types_allowed`; it is never validated from input.
- [Docker tests call `build()` for `ready()` and relied on it writing] → `ready` needs only
  `world_name`; `Session.up` writes before `start()`. The Docker suite runs once at the end, on
  existing images.
