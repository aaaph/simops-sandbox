# Spec Delta

## Purpose

A scenario is the one file a user writes to describe a simulation: which world, which agents on
which platforms and where, which autopilot firmware, and how the agents' topics are named. An agent is one body placed in
the simulation: an instance of a platform, under its own name.

## ADDED Requirements

### Requirement: Scenario file
A scenario SHALL be a YAML file with a `name`, a `world`, an `agents` map and, when its agents'
platforms use PX4, `autopilot.px4.ref`. Optional keys SHALL default to `namespaces: false` and
`network.router_port: 7447`. The name SHALL identify the scenario's running instance.

#### Scenario: Defaults applied
- **WHEN** a scenario omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false` and router port 7447

### Requirement: Paths relative to the scenario file
Every path in a scenario (`world.file`, each agent's `platform`) SHALL be resolved against the
directory of the scenario file, not the current working directory.

#### Scenario: Scenario loaded from another directory
- **WHEN** a scenario that names `../platforms/<p>` is loaded while the working directory is elsewhere
- **THEN** the platform resolves to `<scenario dir>/../platforms/<p>`

### Requirement: World source
The world SHALL be given either as `room` — generated from `seed`, `size` and `obstacles` — or
as `file`, a path to an SDF world.

#### Scenario: Generated room
- **WHEN** the world is `room: {seed: 42, size: [20, 16]}`
- **THEN** the scenario's world is a room generated from that seed and size

#### Scenario: Ready-made world
- **WHEN** the world is `file: ../worlds/<w>.sdf`
- **THEN** the scenario's world is that file

### Requirement: Agents
Each entry of `agents` SHALL name one agent — its key is the agent's name in the simulation —
and give its `platform` directory and an optional `pose` `[x, y, z, roll, pitch, yaw]` (missing
components are 0). A platform directory SHALL contain `model.sdf`, `bridge.yaml` and
`agent.yaml`.

#### Scenario: Agent with a partial pose
- **WHEN** an agent has `pose: [0, 0, 0.2]`
- **THEN** it is placed at x=0, y=0, z=0.2 with zero roll, pitch and yaw

#### Scenario: Old `robots` key
- **WHEN** a scenario lists its agents under `robots:`
- **THEN** loading fails with a message naming `agents:`

### Requirement: Several agents need namespaces
A scenario with more than one agent SHALL set `namespaces: true`; otherwise loading it SHALL
fail with a message saying so, before anything is built or started.

#### Scenario: Two agents without namespaces
- **WHEN** a scenario with two agents and `namespaces: false` is loaded
- **THEN** simops exits with an error naming `namespaces: true` and builds nothing
