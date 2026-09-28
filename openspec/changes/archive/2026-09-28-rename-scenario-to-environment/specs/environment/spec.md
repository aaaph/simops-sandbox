# Spec Delta

## Purpose

An environment is the one file a user writes to describe a simulation: which world, which agents on
which platforms and where, which PX4 firmware, and how the agents' topics are named. It
describes no action: `build` turns an environment into a bundle, `up` runs the bundle as a session,
and what happens in a session (a task, world events, success criteria) is a scenario, which is
not part of the environment. An agent is one body placed in the simulation: an instance of a
platform, under its own name.

## ADDED Requirements

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
The world SHALL be given either as `room` — generated from `seed`, `size` and `obstacles` — or
as `file`, a path to an SDF world.

#### Scenario: Generated room
- **WHEN** the world is `room: {seed: 42, size: [20, 16]}`
- **THEN** the environment's world is a room generated from that seed and size

#### Scenario: Ready-made world
- **WHEN** the world is `file: ../worlds/<w>.sdf`
- **THEN** the environment's world is that file

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
