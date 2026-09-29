# Proposal

## Why

Most simops unit tests write files only to read them back: the `variant` fixture writes an
environment YAML to load it, `platform` builds a platform directory of links and an `agent.yaml`,
and every bundle test writes `build/<name>/` to parse `compose.yaml`, `spawn.sh`, `bridge.yaml`
and the per-agent models again. The code under test computes; only loading and `build` touch
the disk, and they do both at once. worldgen now separates the two (`room.world()` returns an
`SdfWorld`, `generate` writes it); simops should too, so its tests assert on values in memory and
only the tests whose behavior is a file use one. It also comes before `bundle-manifest-truth`,
whose manifest and true map can then be tested in memory as well.

## What Changes

- `Environment.parse(data, base=..., origin=...)` validates an environment document in memory,
  with the same `InvalidEnvironment` messages naming `origin`; `Environment.load(path)` reads the
  file and calls it.
- `Platform.parse(dir, data)` validates an `agent.yaml` document in memory, its messages naming
  `<dir>/agent.yaml`; `Platform.load(dir)` checks the files and calls it.
- `build(environment)` returns a `Bundle` in memory: compose, the spawn script, the merged bridge,
  the world (a generated `SdfWorld` or the ready-made file), the platforms to copy and the
  per-agent models with namespaced topics. `Bundle.write(dir)` puts it on disk — the only place
  simops writes a bundle. `simops build`, `up` and `run` write it to `build/<name>/` as today.
- worldgen: `room.summary(...)` and `empty.summary(...)` give the one-line summary `generate`
  prints, so simops prints the same line without generating through a file.
- Tests: fixtures `environment(...)` and `platform(...)` build values in memory; unit tests of
  `environment`, `platform`, `bundle`, `session` assert on them. Files stay only where the
  behavior is a file: a bundle on disk (platforms and borrowed meshes copied, a rebuild drops
  stale files), `simops build`, paths relative to the environment file, a `file` world source, a
  platform's `agent.yaml` read through an environment, and the Docker tests.
- No behavior change: the bundle written for every environment in `environments/` and the
  command output stay identical.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No requirement changes; the change sets `skip_specs: true`.

## Impact

- `src/simops/environment.py`, `platform.py`, `bundle.py`, `session.py`, `cli.py`;
  `src/worldgen/room.py`, `empty.py` (`summary`).
- `tests/simops/conftest.py` (fixtures), `test_environment.py`, `test_platform.py`,
  `test_bundle.py`, `test_session.py`; `tests/simops/test_session_docker.py` keeps its files.
- `openspec/config.yaml` glossary (bundle: in memory and on disk), AGENTS.md (the build line).
- `bundle-manifest-truth` builds on the in-memory `Bundle` (a manifest field, written by `write`).
