# Proposal

## Why

simops drives Docker through its own subprocess calls to `docker compose` (start, stop, exec,
logs), and parses its command line with hand-written argparse, including a manual split of the
arguments after `--` for `run`. Both are generic plumbing that well-known libraries already do:
testcontainers' `DockerCompose` for the compose lifecycle, Typer for the CLI. Handing them over
leaves simops with only what is its own — building the bundle, spawning, readiness.

## What Changes

- Add `typer` and `testcontainers` as dependencies of the pixi environment.
- `sim/simops.py`'s CLI moves to Typer: the same commands (`build`, `up`, `down`, `env`, `gui`,
  `run`), the same arguments and options (`scenario`, `--timeout`, the command after `--`), the
  same exit codes. Help output changes format only.
- The scenario's compose project is driven through testcontainers' `DockerCompose` instead of
  hand-built `docker compose` calls: starting, stopping, running a command in a service,
  reading logs. `up` still starts the scenario and leaves it running for `gui` and other tools.
- No behavior change: the specs of `baseline-simops` hold unchanged, and its tests (unit and
  `-m docker`) are the regression suite for this change. Hence no spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — a refactor of how simops does what its specs already say (`skip_specs: true`).

## Impact

- `pixi.toml` (two dependencies), `pixi.lock`.
- `sim/simops.py`: `main`/argparse and `docker_compose` replaced; `load`, `build`, spawning and
  readiness logic unchanged.
- `sim/tests/test_simops_docker.py`: helpers that call simops' compose wrapper follow the new API.
- Should land after `baseline-simops` (its tests guard this refactor).
