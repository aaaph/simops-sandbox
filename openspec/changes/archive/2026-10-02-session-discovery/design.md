# Design

## Context

See proposal.md — Why. Today every command takes the environment file: `Session(load(path))`
gives the name (compose project, `GZ_PARTITION`) and the router port, and `build_dir() / name` the
bundle. `Session.running()` (added with the `gui` hang fix, not yet in a spec) already asks Docker
whether a session's `world` runs, by compose's own labels `com.docker.compose.project` and
`com.docker.compose.service`. `down` runs `docker compose -f build/<name>/compose.yaml down
--remove-orphans`, so it needs the bundle on disk. The native GUI's resource path comes from
`pixi.toml` (`$PIXI_PROJECT_ROOT/platforms`).

compose labels every container with `com.docker.compose.project`, `.service` and
`.project.working_dir` — the directory of the first `-f` file, wherever compose was started from
— so for a bundle that is `build/<name>/`.

## Goals / Non-Goals

**Goals:** a running session is found from Docker alone, the same for `simops up` and plain
`docker compose`; choosing among sessions is computed in memory from container rows, so unit
tests need no Docker.

**Non-Goals:** sessions on another Docker host or context; a lookup by anything but the session
name; changing `up`, `run` or `build` beyond the labels.

## Decisions

### Docker is the record of running sessions, labels in `compose.yaml`
`compose()` adds `labels: {simops.session: <name>, simops.router_port: "<port>"}` to every service.
One `docker ps -a` with a tab-separated `{{.Label ...}}` template gives every container of every
compose project with its state and the labels above; rows without `simops.session` are other
projects, kept only so that `down <name>` still sees a session from an older bundle.
*Alternative:* a session file written by `up` — rejected: plain `docker compose` writes none, and
it goes stale when Docker or the user stops the containers.
*Alternative:* compose's labels alone (project = session name) — rejected: they cannot tell a
simops session from any other compose project on the machine, and carry no router port.

### Choosing is a pure function over container rows
`Session` lookup is split in two: one call reads the rows (`docker ps`, the only I/O), a function
groups them by `simops.session` and picks: the named session, or the only one, or an error that
lists the names. Each command says which service must run for its session to count:

    gui       world          (gz sim -g waits forever for a missing world)
    host-env  zenoh-router   (ROS and gz reach the session only through it)
    down      any container  (exited ones included: a half-failed session must go too)

The found session gives what the commands need without the environment file: name (partition,
compose project), `simops.router_port`, `working_dir` (bundle). `running()` is replaced by it.

### The argument: an environment file or a session name
An argument that names an existing file, or ends in `.yaml`/`.yml`, is loaded as an environment
(its errors as today); its name is the session name. Anything else is a session name. `host-env`
with a file computes the exports from the file, running or not (as today, plus the resource
path); everything else goes through the lookup.

### Resource path from the bundle
`GZ_SIM_RESOURCE_PATH=<bundle>/platforms`, the bundle being the session's `working_dir`, or
`build_dir() / name` for `host-env <file>` with nothing running. The bundle's `platforms/` holds
every platform and borrowed model the world uses (`bundle`), so it replaces the repository path
in `pixi.toml`, which is removed. If that directory is missing (bundle moved or deleted after
`up`), `gui` still opens and prints a warning: the world shows without the agents' meshes.

### `down` by compose project
`docker compose -p <name> down --remove-orphans`: compose finds the project's containers by label,
no compose file needed. Nothing to remove prints that nothing is up and exits 0, so `down` stays
safe to call twice and from cleanup code.

## Risks / Trade-offs

- [A session started from a bundle built before this change has no `simops.session` label: the
  lookup does not see it] → `down <name>` still works (by project); `up` rewrites the bundle, so
  restarting the session once is enough. Documented in AGENTS.md.
- [A Docker daemon that does not answer looks like "nothing running"] → a failing `docker ps` is
  its own error, never an empty list.
- [Removing `GZ_SIM_RESOURCE_PATH` from `pixi.toml` breaks a manually started `gz sim -g` in
  `pixi shell`] → `simops host-env | source` sets it, and `simops gui` is the documented way.
- [Two sessions with the same name cannot exist (one compose project)], so the name is a safe
  key; running one environment twice stays out of scope (`session-isolation`).

## Migration Plan

After updating: `simops down <name>` for sessions left up, then `simops up` again so their bundle
carries the labels. Re-enter `pixi shell` (or use `simops host-env`) for the resource path.
Rollback: revert the change; old bundles never had the labels, so nothing depends on them.
