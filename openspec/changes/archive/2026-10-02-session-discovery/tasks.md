# Tasks

The unit suite (`pixi run test`, no Docker, no network, no autopilot build) must pass after every
group.

## 1. Labels in the bundle

- [x] 1.1 `src/simops/bundle.py` `compose()`: every service gets `labels: {simops.session: <name>, simops.router_port: "<port>"}`; `tests/simops/test_bundle.py` asserts both labels on every service of `build(environment(...))` in memory, for the default port and a moved one; verify `pixi run test`

## 2. Finding the running session

- [x] 2.1 `src/simops/session.py`: parse the output of `docker ps -a --filter label=com.docker.compose.project` with a tab-separated `{{.Label ...}}` template (one container per line; `--format json` packs all labels into one comma-joined string, and label values can hold commas) into rows of session, service, state, router port and bundle directory (`com.docker.compose.project.working_dir`); unit test on a captured sample string, in memory; verify `pixi run test`
- [x] 2.2 The choosing function of design.md over those rows: named or only session, the service that must run (`world`, `zenoh-router`, or any for `down`), errors for none and for several (listing the names); unit tests from hand-made rows for one, named, several, none, a session whose `world` exited (not found for `gui`, found for `down`); verify `pixi run test`
- [x] 2.3 Reading the rows runs `docker ps` once; a non-zero exit or a missing `docker` raises an error saying Docker does not answer, never an empty list; unit test with the command replaced by a failing one (no Docker); verify `pixi run test`
- [x] 2.4 The CLI argument: an existing file or a `.yaml`/`.yml` path is loaded as an environment (errors as today), anything else is a session name; unit tests with a test environment from `tests/simops/environments/` and a bare name; verify `pixi run test`

## 3. Commands on the found session

- [x] 3.1 `gui [environment]`: the lookup with `world` running replaces `Session.running()` (removed); the GUI gets the session's partition, router port and `GZ_SIM_RESOURCE_PATH=<bundle>/platforms`, with a warning if that directory is missing; `<name> is not up: pixi run simops up ...` (the file when given, else the name) and exit 1 without starting `gz`; unit test of the exports computed from a found session, in memory; verify `pixi run test`
- [x] 3.2 `host-env [environment]`: a file prints from the file, running or not, with `GZ_SIM_RESOURCE_PATH=build_dir()/<name>/platforms`; a name or nothing goes through the lookup with `zenoh-router` running and fails when nothing is up; `tests/simops/test_session.py` and `test_cli.py` cover the file case and the resource path; verify `pixi run test`
- [x] 3.3 `down [environment]`: `docker compose -p <name> down --remove-orphans`, no bundle directory needed; nothing to stop prints that nothing is up and exits 0; `run` keeps calling it for its own session; verify `pixi run test`
- [x] 3.4 `up`'s closing lines name the session instead of the file (`pixi run simops gui <name>`, `host-env <name>`, `down <name>`); verify `pixi run test`

## 4. Resource path and docs

- [x] 4.1 `pixi.toml`: remove `GZ_SIM_RESOURCE_PATH` from `[activation.env]`; verify `pixi run printenv GZ_SIM_RESOURCE_PATH` prints nothing
- [x] 4.2 AGENTS.md: the command block shows `gui`, `host-env`, `down` without the environment (and with a name when several sessions run), sessions are found by the `simops.session` label so plain `docker compose` sessions count, a session from an older bundle needs one `up` again; `openspec/config.yaml` glossary: session is found from its containers (Spec: sim-lifecycle); verify `openspec validate session-discovery --strict` passes

## 5. Integration

- [x] 5.1 Run `pixi run format`, `pixi run lint`, `pixi run test`; all pass, and no `build/<name>/` is left that was not there before
- [x] 5.2 Docker test (`-m docker`, on the images that exist: `simops-sandbox-{ros,world}`, `simops-sandbox-px4:fca3df865af3`; if one is missing, build it first with `docker compose -f build/<name>/compose.yaml build`, as its own step): `tests/simops/test_session_docker.py` gets `host-env` without an argument printing the session's port and partition, `down` without an argument removing everything, and a session started with plain `docker compose -f <bundle>/compose.yaml up -d` found by `host-env`; verify `pixi run pytest -m docker` passes and no `t_*` container or bundle is left
- [x] 5.3 By hand: `pixi run simops up environments/rover_empty_world.yaml`, then `pixi run simops gui` opens the GUI with the rover's meshes; with nothing up, `pixi run simops gui` exits 1 at once; `pixi run simops down` cleans up; verify `docker compose ls` lists nothing of it afterwards
