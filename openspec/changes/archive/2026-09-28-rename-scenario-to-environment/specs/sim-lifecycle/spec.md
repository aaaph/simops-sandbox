# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Scenarios are isolated`
- TO: `### Requirement: Environments are isolated`

## MODIFIED Requirements

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
`simops down <environment>` SHALL stop and remove all containers of the environment's session, including
orphans from an earlier version of its bundle, and nothing else.

#### Scenario: Down after up
- **WHEN** `simops down` runs after a successful `up`
- **THEN** no container of that session remains and containers of other projects are untouched

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
partition. Sessions of two environments SHALL be able to run side by side when their names and router ports
differ.

#### Scenario: Two scenarios side by side
- **WHEN** environments `a` (port 7447) and `b` (port 7448) are both up
- **THEN** each has its own containers and neither sees the other's gz or ROS topics
