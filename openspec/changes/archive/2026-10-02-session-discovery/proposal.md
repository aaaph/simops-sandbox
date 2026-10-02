# Proposal

## Why

`gui`, `host-env` and `down` act on a running session, yet each must be given the environment
file, although almost always exactly one session is running and Docker already knows which.
Without a running session `gz sim -g` waits for a world that never comes, so `gui` against the
wrong environment hangs. And the native GUI finds the agents' meshes through
`GZ_SIM_RESOURCE_PATH` set by `pixi.toml` to this repository's `platforms/`: once simops is a
dev-dependency of another repository, that path is wrong, while the bundle of the running session
holds exactly the platforms its world uses.

No session file is written by `up` to find sessions with: a bundle can be started with plain
`docker compose` (`bundle`), which writes nothing of simops', and a file outlives a session that
Docker or the user stopped. Docker is the one source of truth for what runs; the bundle's
`compose.yaml` labels its containers so that Docker can answer.

## What Changes

- The bundle's `compose.yaml` SHALL label every service with the session's name and router port,
  so a session started by `simops up` or by plain `docker compose` is found the same way.
- `gui`, `host-env` and `down` SHALL take the environment as optional: an environment file or a
  session name. Without it they act on the one running session; with none running, `gui` and
  `host-env` fail saying nothing is up, and with several they list them and do nothing.
- `gui` SHALL refuse a session whose world is not running instead of waiting for it forever.
- `gui` and `host-env` SHALL point `GZ_SIM_RESOURCE_PATH` at the session's bundle `platforms/`,
  so the GUI loads the agents' meshes from the bundle, not from this repository.
- `down` SHALL find the session's containers by its compose project, without needing the bundle
  directory, and remove containers that exited too; nothing running is not an error for `down`.
- `host-env <environment file>` keeps working without a running session (exports computed from
  the file), so the environment can be prepared before `up`.
- `pixi.toml` drops its `GZ_SIM_RESOURCE_PATH`.

Out of scope: several sessions of one environment, `up` refusing an already running session
(`session-isolation`, which reuses the lookup added here), a session on another Docker host.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `host-access`: `gui` and `host-env` find the running session themselves, refuse when none is
  up, and give the GUI the bundle's platforms as its resource path.
- `sim-lifecycle`: `down` acts on the one running session when none is named, by compose project.
- `bundle`: `compose.yaml` labels its services with the session's name and router port.

## Impact

- `src/simops/bundle.py` (labels in `compose`), `src/simops/session.py` (finding running
  sessions, `running()` replaced by it, `host_env` with the resource path, `down` by project),
  `src/simops/cli.py` (optional argument, name or file).
- `pixi.toml` (`GZ_SIM_RESOURCE_PATH` removed), AGENTS.md (commands without the environment).
- `tests/simops/`: labels in `test_bundle.py`; choosing among running sessions in memory from
  given container labels; the Docker suite gets `gui`/`host-env`/`down` without an argument.
- `session-isolation` builds on the same lookup to see an environment's session before `up`.
