# Tasks

Start after `baseline-simops` is archived: its unit and Docker tests are this refactor's
regression suite. Behavior does not change; any failing baseline test is a bug in this change.

## 1. Dependencies

- [ ] 1.1 Add `typer` and `testcontainers` to `[dependencies]` in `pixi.toml` and update `pixi.lock`; verify `pixi run python -c "import typer; from testcontainers.compose import DockerCompose"` succeeds

## 2. Compose lifecycle through testcontainers

- [ ] 2.1 Add `project(sc) -> DockerCompose` for `build/<name>/compose.yaml` and move `up` to `start()` (`--wait`) followed by the existing readiness loop, with the "images are built on first use" line before it; on `CalledProcessError` or timeout print the log tail and `down`; verify `pixi run pytest -m docker -k "up_and_down or failed_up or first_check"`
- [ ] 2.2 Move `down` to `[*project(sc).docker_compose_command(), "down", "--remove-orphans"]`; verify `pixi run pytest -m docker -k up_and_down` and that a container of a service removed from the bundle is gone after `down`
- [ ] 2.3 Move `pose_stamp` to `exec_in_container(..., "world")`, turning `CalledProcessError` into `None`; verify `pixi run pytest -m docker -k "world_restart or up_and_down"`
- [ ] 2.4 Print the log tail from `get_logs()` (last 15 lines per service) and delete `docker_compose`; point the Docker tests' helpers (`started_at`, world restart) at `project(sc)`; verify `grep -n 'docker_compose' sim/` finds nothing and `pixi run pytest -m docker` passes in full

## 3. Typer CLI

- [ ] 3.1 Replace argparse in `main()` with a Typer app: `build`, `up`, `down`, `env`, `gui`, `run`, `scenario` argument, `--timeout` on `up`/`run`, `run` taking the command after `--` via `ctx.args`, same exit codes; verify `pixi run simops --help`, `pixi run simops env scenarios/rover_room.yaml` prints the same exports as before, and `pixi run simops run <copy of rover_room on a free port> -- sh -c 'exit 3'` exits 3
- [ ] 3.2 Update the module docstring and AGENTS.md where they describe the CLI or its internals; verify every simops command AGENTS.md shows still runs as written

## 4. Integration

- [ ] 4.1 Run `pixi run lint`, `pixi run test` and `pixi run pytest -m docker`; all pass and no container of a test scenario is left (`docker ps -a --filter label=com.docker.compose.project=t_updown` and the other `t_*` names empty)
