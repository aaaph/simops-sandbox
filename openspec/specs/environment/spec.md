# environment Specification

## Purpose

An environment is the one file a user writes to describe a simulation: which world, which agents on
which platforms and where, and how the agents' topics are named; each agent's autopilot comes
from its platform. It describes no action: `build` turns an environment into a bundle, `up` runs the bundle as a session,
and what happens in a session (a task, world events, success criteria) is a scenario, which is
not part of the environment. An agent is one body placed in the simulation: an instance of a
platform, under its own name.

## Requirements

### Requirement: Environment contents
An environment SHALL be a YAML file with a `name`, a `world` and an `agents` map. Optional keys
SHALL default to `namespaces: false`, `network.router_port: 7447` and `network.mavlink_port:
14540`. The name SHALL identify the environment's session: its compose project and gz partition.
An environment SHALL NOT name PX4 firmware: each agent's firmware comes from its platform (see
`autopilot`).

#### Scenario: Defaults applied
- **WHEN** an environment omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false`, router port 7447 and MAVLink port 14540

#### Scenario: MAVLink port set
- **WHEN** an environment sets `network: {mavlink_port: 14590}`
- **THEN** it is loaded with MAVLink port 14590 and router port 7447

#### Scenario: Old `autopilot` key
- **WHEN** an environment sets `autopilot`
- **THEN** loading fails with a message saying the firmware is set in the platform's `agent.yaml`

### Requirement: Paths relative to the environment file
Every path in an environment (`world.file`, each agent's `platform`) SHALL be resolved against the
directory of the environment file, not the current working directory.

#### Scenario: Environment loaded from another directory
- **WHEN** an environment that names `../platforms/<p>` is loaded while the working directory is elsewhere
- **THEN** the platform resolves to `<environment dir>/../platforms/<p>`

### Requirement: Exactly one world source
The world SHALL be given as exactly one world source: `generate_room` — a room generated from
`seed`, `size` and `obstacles` — `file`, a path to an SDF world, or `empty_world` — an open field
with no walls and no obstacles, taking no fields. Giving more than one, or none, SHALL fail
loading with a message naming `generate_room`, `file` and `empty_world`.

#### Scenario: Generated room
- **WHEN** the world is `generate_room: {seed: 42, size: [20, 16]}`
- **THEN** the environment's world is a room generated from that seed and size

#### Scenario: Ready-made world
- **WHEN** the world is `file: ../worlds/<w>.sdf`
- **THEN** the environment's world is that file

#### Scenario: Empty world
- **WHEN** the world is `empty_world:`
- **THEN** the environment's world is an open field: no walls, no obstacles, only the ground and
  the start marker

#### Scenario: empty_world takes no fields
- **WHEN** the world is `empty_world: {size: [12, 9]}`
- **THEN** loading fails with a message naming `size` and `empty_world`

#### Scenario: Both generate_room and file
- **WHEN** the world sets both `generate_room` and `file`
- **THEN** loading fails with a message naming `generate_room`, `file` and `empty_world`

#### Scenario: empty_world together with another source
- **WHEN** the world sets `empty_world` together with `generate_room` or `file`
- **THEN** loading fails with a message naming `generate_room`, `file` and `empty_world`

#### Scenario: No world source
- **WHEN** the world sets none of `generate_room`, `file` or `empty_world`
- **THEN** loading fails with a message naming `generate_room`, `file` and `empty_world`

#### Scenario: Old `room` key
- **WHEN** the world is given as `room: {seed: 42}`
- **THEN** loading fails with a message saying `world.room` is now `world.generate_room`

### Requirement: Agents
Each entry of `agents` SHALL name one agent — its key is the agent's name in the simulation —
and give its `platform` directory and an optional `pose` `[x, y, z, roll, pitch, yaw]` (missing
components are 0). A platform directory SHALL contain `model.sdf`, `bridge.yaml` and
`agent.yaml`. Loading an environment SHALL load each platform's `agent.yaml` and fail on an
invalid one with a message naming that `agent.yaml` file, the key and why.

#### Scenario: Agent with a partial pose
- **WHEN** an agent has `pose: [0, 0, 0.2]`
- **THEN** it is placed at x=0, y=0, z=0.2 with zero roll, pitch and yaw

#### Scenario: Old `robots` key
- **WHEN** an environment lists its agents under `robots:`
- **THEN** loading fails with a message naming `agents:`

#### Scenario: Invalid agent.yaml
- **WHEN** an agent's platform `agent.yaml` sets `autopilot.px4.version: v1.17.0`
- **THEN** loading the environment fails with a message naming that `agent.yaml`, 1.17.0 and the 1.18 minimum

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
world, an agent, `network`), with a message naming the key and where it is. The same SHALL hold
for a platform's `agent.yaml` (see `autopilot`). The keys `robots`, `autopilot` and `world.room`
keep their own messages naming where their content went.

#### Scenario: Misspelled key
- **WHEN** an environment sets `namespace: true` instead of `namespaces`
- **THEN** loading fails with a message naming `namespace`

#### Scenario: Unknown agent key
- **WHEN** an agent sets `position:` instead of `pose:`
- **THEN** loading fails with a message naming `position` and the agent
