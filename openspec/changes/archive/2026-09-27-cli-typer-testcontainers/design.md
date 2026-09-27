# Design

## Context

See proposal.md — Why. `sim/simops.py` today: `docker_compose(sc, *args)` wraps every
`docker compose -f build/<name>/compose.yaml ...` call (`up -d`, `down --remove-orphans`,
`exec -T world ...` for readiness, `logs --tail 15`), and `main()` is argparse with a manual
split of `sys.argv` at `--` for `run`. `load`, `build`, `spawn.sh` and the readiness check
(`pose_stamp`, `ready`) are simops' own logic and stay.

testcontainers 4.14 (`testcontainers.compose.DockerCompose`) is itself a thin wrapper over the
`docker compose` CLI: `start()` runs `up --wait` (or `--detach`), `stop()` runs
`down --volumes`, `exec_in_container()` runs `exec -T`, `get_logs()` runs `logs`. Every call goes
through `subprocess.run(..., capture_output=True, check=True)`, so a non-zero exit raises
`CalledProcessError`. Ryuk (its reaper) is not used for compose projects.

## Goals / Non-Goals

**Goals:** no hand-built `docker compose` command lines in simops; Typer CLI with the same
commands, arguments and exit codes; every scenario in `baseline-simops` still passes.

**Non-Goals:** readiness as a Docker healthcheck, removing simops runtime commands, cleanup of
sessions whose process was killed — all separate changes if wanted.

## Decisions

### One `DockerCompose` per scenario, built from the bundle
`project(sc) -> DockerCompose(context=build/<name>, compose_file_name="compose.yaml", wait=True)`.
Every lifecycle function takes it from there. `up` calls `start()` without a `with` block, so
the scenario keeps running after simops exits (`gui`, QGC, tests from another process).
*Alternative:* the context manager — rejected for `up`, it would tear the scenario down on exit;
it fits `run`, which does use `with`-like try/finally semantics.

### `up`: `start()` with `--wait`, then simops' own readiness
`wait=True` makes compose wait until the services run and the one-shot `spawn` has exited 0; a
failed `spawn` fails `start()` at once (checked on compose 2.40 in explore: exit 1,
`service "spawn" didn't complete successfully`). Readiness (agents in the world, sim time
advancing) stays simops' loop on top — compose knows nothing about the world. Any
`CalledProcessError` or readiness timeout: print the log tail, `down`, exit 1, as today.
*Alternative:* `wait=False` (`--detach`) — equivalent to today, but loses the early spawn failure.

### `down` keeps `--remove-orphans`
`DockerCompose.stop()` runs `down --volumes` without `--remove-orphans`, which the `sim-lifecycle`
spec requires (a service dropped from a rebuilt bundle, e.g. a removed agent's `px4-<agent>`,
must go too). `down` therefore runs `[*project.docker_compose_command(), "down",
"--remove-orphans"]` through `subprocess.run` — the one command line left, built from the public
base command. The bundle has no named volumes, so leaving out `--volumes` changes nothing.
*Alternative:* `stop()` and accept orphans — rejected, it breaks a spec requirement.

### Readiness through `exec_in_container`
`pose_stamp` runs its `gz topic -e ... -n 1` via `project.exec_in_container([...], "world")`.
It raises on a non-zero exit (e.g. `timeout` expiring before a pose message), which
`pose_stamp` turns into `None` — "not ready yet", as the empty output does today.

### Log tail from `get_logs()`
`get_logs()` returns whole logs; simops prints the last 15 lines per service by splitting the
output on the compose `service |` prefix. Same information as `logs --tail 15`.

### Typer CLI
`app = typer.Typer()`, one command per subcommand, `scenario: Path` argument, `--timeout: float
= 300` on `up` and `run`. `run` takes the command after `--` with
`context_settings={"allow_extra_args": True, "ignore_unknown_options": True}` and `ctx.args`,
which also passes the command's own flags through untouched. Exit codes via
`raise typer.Exit(code)`. The module keeps `load`, `build`, `up`, `down`, `run`, `host_env`
importable for the tests.

### Dependencies
`typer` and `testcontainers` go under `[dependencies]` in `pixi.toml` (conda-forge: typer 0.27,
testcontainers 4.14): the CLI needs them at runtime, not only tests.

## Risks / Trade-offs

- [`capture_output=True` hides compose's progress, including the ~10 min first build of a PX4
  image] → `up` prints one line before `start()` saying images are built on first use and can
  take minutes; on failure the captured output is printed.
- [testcontainers' logger prints every failed command's stdout/stderr at ERROR — the failed
  `up` twice (its log and simops' message), and each readiness poll that times out while the
  world boots] → simops sets the `testcontainers` logger to CRITICAL and prints the failures that
  matter itself (found during apply).
- [A heavier dependency (docker-py comes with it) for ~36 lines of calls] → accepted by the
  user as the price for not maintaining the plumbing.
- [Typer's help and error formatting differs from argparse] → not part of any spec.

## Migration Plan

Refactor in place; `pixi run test` and `pixi run pytest -m docker` must pass before and after.
Rollback: revert the commit.
