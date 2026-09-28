# Spec Delta

## ADDED Requirements

### Requirement: Environment contents
An environment SHALL be a YAML file with a `name`, a `world` and an `agents` map. Optional keys
SHALL default to `namespaces: false` and `network.router_port: 7447`. The name SHALL identify the
environment's session: its compose project and gz partition. An environment SHALL NOT name PX4
firmware: each agent's firmware comes from its platform (see `autopilot`).

#### Scenario: Defaults applied
- **WHEN** an environment omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false` and router port 7447

#### Scenario: Old `autopilot` key
- **WHEN** an environment sets `autopilot`
- **THEN** loading fails with a message saying the firmware is set in the platform's `agent.yaml`

### Requirement: Exactly one world source
The world SHALL be given as exactly one world source: `generate_room` — a room generated from
`seed`, `size` and `obstacles` — or `file`, a path to an SDF world. Giving both, or neither,
SHALL fail loading with a message naming `generate_room` and `file`.

#### Scenario: Generated room
- **WHEN** the world is `generate_room: {seed: 42, size: [20, 16]}`
- **THEN** the environment's world is a room generated from that seed and size

#### Scenario: Ready-made world
- **WHEN** the world is `file: ../worlds/<w>.sdf`
- **THEN** the environment's world is that file

#### Scenario: Both generate_room and file
- **WHEN** the world sets both `generate_room` and `file`
- **THEN** loading fails with a message naming `generate_room` and `file`

#### Scenario: Old `room` key
- **WHEN** the world is given as `room: {seed: 42}`
- **THEN** loading fails with a message saying `world.room` is now `world.generate_room`

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Environment file
**Reason**: The PX4 firmware moves to the platform's `agent.yaml`; the environment's keys are
restated in "Environment contents".
**Migration**: Move `autopilot.px4.version`/`commit`/`repo` into each platform's `agent.yaml`
under `autopilot.px4`, and delete `autopilot` from the environment.

### Requirement: World source
**Reason**: The key `room` becomes `generate_room`; restated in "Exactly one world source".
**Migration**: Rename `world.room` to `world.generate_room`.
