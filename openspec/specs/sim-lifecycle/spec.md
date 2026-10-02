# sim-lifecycle Specification

## Purpose

Starting, stopping and using an environment's session as a disposable dependency: `up` means the
agents are in a running world, and a failed or finished run leaves nothing behind.

## Requirements

### Requirement: Up returns when the simulation is ready
`simops up <environment>` SHALL build the bundle, start it, and return success only once every
agent of the environment is in the world and simulation time advances. Readiness SHALL be judged
from two world pose messages taken apart in time: both list every agent and the later one has a
greater simulation time.

#### Scenario: Agents in a running world
- **WHEN** `simops up environments/rover_room.yaml` returns 0
- **THEN** `rover1` is in the world and simulation time is advancing

#### Scenario: Wedged physics is not ready
- **WHEN** the world server publishes one pose message and then stops stepping
- **THEN** `up` does not report ready

### Requirement: Failed up leaves nothing running
If containers fail to start, or a readiness check fails after `--timeout` seconds (default 300)
have passed, `up` SHALL print the last log lines of the services, remove every container of its
session, and exit non-zero. The timeout bounds the waiting between failed checks, not the whole
of `up`: a check that succeeds is accepted however long it took.

#### Scenario: Agent never appears
- **WHEN** an agent's model cannot be loaded, so it never appears in the world, and `simops up <environment> --timeout 1` runs
- **THEN** it prints log lines, exits non-zero, and no container of its session remains

#### Scenario: Ready on the first check
- **WHEN** `simops up <environment> --timeout 1` runs and the first readiness check succeeds
- **THEN** `up` exits 0, although it took longer than one second

### Requirement: Down
`simops down [environment]` SHALL stop and remove all containers of the session, exited ones and
orphans from an earlier version of its bundle included, and nothing else. It SHALL not need the
session's bundle directory. With no session to stop it SHALL say so and exit 0.

#### Scenario: Down after up
- **WHEN** `simops down` runs after a successful `up`
- **THEN** no container of that session remains and containers of other projects are untouched

#### Scenario: Half-failed session
- **WHEN** a session's `world` container exited and its other containers run
- **THEN** `simops down` removes all of them

#### Scenario: Bundle directory gone
- **WHEN** a session is up and its `build/<name>/` was deleted
- **THEN** `simops down <name>` removes its containers

#### Scenario: Nothing running
- **WHEN** no session is up and `simops down` runs without an argument
- **THEN** it says nothing is up and exits 0

### Requirement: Run
`simops run <environment> -- <command>` SHALL bring a session of the environment up, run the command with the
host environment of `host-access` added, tear the session down whatever the command's outcome,
and exit with the command's exit code. If `up` fails, the command SHALL NOT run and `run` SHALL
exit non-zero.

#### Scenario: Failing command
- **WHEN** the command exits with code 3
- **THEN** the session is torn down and `run` exits with 3

#### Scenario: Up fails
- **WHEN** `up` fails
- **THEN** the command is not run and `run` exits non-zero

### Requirement: Environments are isolated
Each environment's session SHALL run as its own compose project named after the environment, with its own gz
partition. Sessions of two environments SHALL be able to run side by side when their names, router ports
and MAVLink port ranges (`mavlink_port` to `mavlink_port + agents - 1`) differ. A session whose router
port is already taken on the host SHALL fail `up` as "Failed up leaves nothing running" describes. A
session whose MAVLink port range overlaps that of a running session SHALL fail `up` before starting any
container, naming that session. Either way the session that holds the port is left untouched.

#### Scenario: Two scenarios side by side
- **WHEN** environments `a` (router port 7447, MAVLink port 14540) and `b` (router port 7448, MAVLink port 14590) are both up
- **THEN** each has its own containers and neither sees the other's gz or ROS topics or MAVLink

#### Scenario: MAVLink port taken
- **WHEN** environment `a` with MAVLink port 14540 is up and `simops up` runs for environment `b` with router port 7448 and MAVLink port 14540
- **THEN** `up` for `b` names `a`, exits non-zero, starts no container of `b`, and `a` keeps running

### Requirement: Commands find the running session
`gui`, `host-env` and `down` SHALL take the environment as optional: an environment file, or a
session name (the environment's name). Without it they SHALL act on the one running session. A
session SHALL be found from its containers alone, whether it was started by `simops up` or by plain
`docker compose` on its bundle. With several sessions running and none named, the command SHALL
list their names, act on none and exit non-zero. If Docker does not answer, the command SHALL say
so and exit non-zero rather than report that nothing is running.

#### Scenario: One session running
- **WHEN** only `rover_room` is up and `simops gui` runs without an argument
- **THEN** it acts on `rover_room`

#### Scenario: Session name instead of the file
- **WHEN** `rover_room` is up and `simops down rover_room` runs
- **THEN** it acts on `rover_room` as `simops down environments/rover_room.yaml` would

#### Scenario: Several sessions running
- **WHEN** `a` and `b` are up and `simops gui` runs without an argument
- **THEN** it prints `a` and `b`, opens no GUI and exits non-zero

#### Scenario: Session started by plain compose
- **WHEN** a bundle was started with `docker compose -f build/<name>/compose.yaml up -d`
- **THEN** `simops gui`, `simops host-env` and `simops down` without an argument find it

#### Scenario: Docker not running
- **WHEN** the Docker daemon does not answer and `simops gui` runs
- **THEN** it says Docker does not answer and exits non-zero
