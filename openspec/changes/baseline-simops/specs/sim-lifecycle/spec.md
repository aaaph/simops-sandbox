# Spec Delta

## Purpose

Starting, stopping and using a scenario's simulation as a disposable dependency: `up` means the
agents are in a running world, and a failed or finished run leaves nothing behind.

## ADDED Requirements

### Requirement: Up returns when the simulation is ready
`simops up <scenario>` SHALL build the bundle, start it, and return success only once every
agent of the scenario is in the world and simulation time advances. Readiness SHALL be judged
from two world pose messages taken apart in time: both list every agent and the later one has a
greater simulation time.

#### Scenario: Agents in a running world
- **WHEN** `simops up scenarios/rover_room.yaml` returns 0
- **THEN** `rover1` is in the world and simulation time is advancing

#### Scenario: Wedged physics is not ready
- **WHEN** the world server publishes one pose message and then stops stepping
- **THEN** `up` does not report ready

### Requirement: Failed up leaves nothing running
If containers fail to start, or readiness is not reached within `--timeout` seconds (default
300), `up` SHALL print the last log lines of the services, remove every container of the
scenario, and exit non-zero.

#### Scenario: Timeout
- **WHEN** `simops up <scenario> --timeout 1` cannot reach readiness in one second
- **THEN** it prints log lines, exits non-zero, and no container of the scenario remains

### Requirement: Down
`simops down <scenario>` SHALL stop and remove all containers of the scenario, including
orphans from an earlier version of its bundle, and nothing else.

#### Scenario: Down after up
- **WHEN** `simops down` runs after a successful `up`
- **THEN** no container of that scenario remains and containers of other projects are untouched

### Requirement: Run
`simops run <scenario> -- <command>` SHALL bring the scenario up, run the command with the
host environment of `host-access` added, tear the scenario down whatever the command's outcome,
and exit with the command's exit code. If `up` fails, the command SHALL NOT run and `run` SHALL
exit non-zero.

#### Scenario: Failing command
- **WHEN** the command exits with code 3
- **THEN** the scenario is torn down and `run` exits with 3

#### Scenario: Up fails
- **WHEN** `up` fails
- **THEN** the command is not run and `run` exits non-zero

### Requirement: Scenarios are isolated
Each scenario SHALL run as its own compose project named after the scenario, with its own gz
partition. Two scenarios SHALL be able to run side by side when their names and router ports
differ.

#### Scenario: Two scenarios side by side
- **WHEN** scenarios `a` (port 7447) and `b` (port 7448) are both up
- **THEN** each has its own containers and neither sees the other's gz or ROS topics
