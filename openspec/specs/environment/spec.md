# environment Specification

## Purpose

An environment is the one file a user writes to describe a simulation: which world, which agents on
which platforms and where, which PX4 firmware, and how the agents' topics are named. It
describes no action: `build` turns an environment into a bundle, `up` runs the bundle as a session,
and what happens in a session (a task, world events, success criteria) is a scenario, which is
not part of the environment. An agent is one body placed in the simulation: an instance of a
platform, under its own name.

## Requirements

### Requirement: Environment file
An environment SHALL be a YAML file with a `name`, a `world` and an `agents` map. When its agents'
platforms use PX4, `autopilot.px4` MAY name the firmware by `version` or by `commit` (see
`autopilot`); with neither, the default firmware is used. Optional keys SHALL default to
`namespaces: false` and `network.router_port: 7447`. The name SHALL identify the environment's
session: its compose project and gz partition.

#### Scenario: Defaults applied
- **WHEN** an environment omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false` and router port 7447

#### Scenario: Old `ref` key
- **WHEN** an environment sets `autopilot.px4.ref`
- **THEN** loading fails with a message naming `version` and `commit`

#### Scenario: Both version and commit
- **WHEN** an environment sets both `autopilot.px4.version` and `autopilot.px4.commit`
- **THEN** loading fails, saying only one of them may be given

### Requirement: Paths relative to the environment file
Every path in an environment (`world.file`, each agent's `platform`) SHALL be resolved against the
directory of the environment file, not the current working directory.

#### Scenario: Environment loaded from another directory
- **WHEN** an environment that names `../platforms/<p>` is loaded while the working directory is elsewhere
- **THEN** the platform resolves to `<environment dir>/../platforms/<p>`

### Requirement: World source
The world SHALL be given as exactly one world source: `room` — generated from `seed`, `size` and
`obstacles` — or `file`, a path to an SDF world. Giving both, or neither, SHALL fail loading with a
message naming `room` and `file`.

#### Scenario: Generated room
- **WHEN** the world is `room: {seed: 42, size: [20, 16]}`
- **THEN** the environment's world is a room generated from that seed and size

#### Scenario: Ready-made world
- **WHEN** the world is `file: ../worlds/<w>.sdf`
- **THEN** the environment's world is that file

#### Scenario: Both room and file
- **WHEN** the world sets both `room` and `file`
- **THEN** loading fails with a message naming `room` and `file`

### Requirement: Agents
Each entry of `agents` SHALL name one agent — its key is the agent's name in the simulation —
and give its `platform` directory and an optional `pose` `[x, y, z, roll, pitch, yaw]` (missing
components are 0). A platform directory SHALL contain `model.sdf`, `bridge.yaml` and
`agent.yaml`.

#### Scenario: Agent with a partial pose
- **WHEN** an agent has `pose: [0, 0, 0.2]`
- **THEN** it is placed at x=0, y=0, z=0.2 with zero roll, pitch and yaw

#### Scenario: Old `robots` key
- **WHEN** an environment lists its agents under `robots:`
- **THEN** loading fails with a message naming `agents:`

### Requirement: Several agents need namespaces
An environment with more than one agent SHALL set `namespaces: true`; otherwise loading it SHALL
fail with a message saying so, before anything is built or started.

#### Scenario: Two agents without namespaces
- **WHEN** an environment with two agents and `namespaces: false` is loaded
- **THEN** simops exits with an error naming `namespaces: true` and builds nothing

### Requirement: Environment path on the command line
The environment path given to a simops command SHALL be resolved against the directory the
command is run from, both for the `simops` command and for `pixi run simops` from any directory
of the project.

#### Scenario: Relative path from a subdirectory
- **WHEN** `simops build rover_room.yaml` runs in `environments/`
- **THEN** it builds `environments/rover_room.yaml`

#### Scenario: Through pixi from a subdirectory
- **WHEN** `pixi run simops build rover_room.yaml` runs in `environments/`
- **THEN** it builds `environments/rover_room.yaml`

### Requirement: Unknown keys are rejected
Loading SHALL fail on a key an environment does not define, at any level (the environment, its
world, an agent, `autopilot.px4`, `network`), with a message naming the key and where it is.
The keys `robots` and `autopilot.px4.ref` keep their own messages naming their replacements.

#### Scenario: Misspelled key
- **WHEN** an environment sets `namespace: true` instead of `namespaces`
- **THEN** loading fails with a message naming `namespace`

#### Scenario: Unknown agent key
- **WHEN** an agent sets `position:` instead of `pose:`
- **THEN** loading fails with a message naming `position` and the agent
