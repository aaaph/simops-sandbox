## MODIFIED Requirements

### Requirement: Environment contents
An environment SHALL be a YAML file with a `name`, a `world` and an `agents` map. Optional keys
SHALL default to `namespaces: false`, `network.router_port: 7447` and `network.mavlink_port:
14540`. The name SHALL identify the environment's session: its compose project and gz partition.
An environment SHALL NOT name PX4 firmware outside a platform: each agent's firmware comes from
its platform (see `autopilot`), whether the platform is a directory or written inline.

#### Scenario: Defaults applied
- **WHEN** an environment omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false`, router port 7447 and MAVLink port 14540

#### Scenario: MAVLink port set
- **WHEN** an environment sets `network: {mavlink_port: 14590}`
- **THEN** it is loaded with MAVLink port 14590 and router port 7447

#### Scenario: Old `autopilot` key
- **WHEN** an environment sets `autopilot` at its top level
- **THEN** loading fails with a message saying the firmware is set in the platform's `autopilot.px4`, in its `platform.yaml` or inline

### Requirement: Paths relative to the environment file
Every path in an environment (`world.file`, each agent's `platform` when it is a directory, and
the paths of an inline platform) SHALL be resolved against the directory of the environment file,
not the current working directory. Paths inside a platform directory's `platform.yaml` are
resolved against that directory (see `platform`).

#### Scenario: Environment loaded from another directory
- **WHEN** an environment that names `../platforms/<p>` is loaded while the working directory is elsewhere
- **THEN** the platform resolves to `<environment dir>/../platforms/<p>`

#### Scenario: Inline platform loaded from another directory
- **WHEN** an environment whose agent has an inline platform with `model: ../platforms/<p>/model.sdf` is loaded while the working directory is elsewhere
- **THEN** the model resolves to `<environment dir>/../platforms/<p>/model.sdf`

### Requirement: Agents
Each entry of `agents` SHALL name one agent — its key is the agent's name in the simulation —
and give its `platform` and an optional `pose` `[x, y, z, roll, pitch, yaw]` (missing components
are 0). The `platform` SHALL be either the path to a platform directory or a platform document
inline (see `platform`). Loading an environment SHALL load each agent's platform and fail on an
invalid one with a message saying where the platform is written, the key and why (see
`platform`, "Platform errors name where they are written").

#### Scenario: Agent with a partial pose
- **WHEN** an agent has `pose: [0, 0, 0.2]`
- **THEN** it is placed at x=0, y=0, z=0.2 with zero roll, pitch and yaw

#### Scenario: Old `robots` key
- **WHEN** an environment lists its agents under `robots:`
- **THEN** loading fails with a message naming `agents:`

#### Scenario: Invalid agent.yaml
- **WHEN** an agent's platform directory holds only the old `agent.yaml`, no `platform.yaml`
- **THEN** loading the environment fails with a message naming that directory and saying `agent.yaml` is now `platform.yaml`

#### Scenario: Invalid platform.yaml
- **WHEN** an agent's platform `platform.yaml` sets `autopilot.px4.version: v1.17.0`
- **THEN** loading the environment fails with a message naming that `platform.yaml`, 1.17.0 and the 1.18 minimum

#### Scenario: Directory and inline platforms side by side
- **WHEN** with `namespaces: true`, `rover1` names `../platforms/rover_differential_lidar_px4` and `rover11` has an inline platform with `base: ../platforms/rover_differential_lidar_px4`
- **THEN** the environment loads with both agents

### Requirement: Unknown keys are rejected
Loading SHALL fail on a key an environment does not define, at any level (the environment, its
world, an agent, `network`), with a message naming the key and where it is. The same SHALL hold
for a platform document, in a `platform.yaml` or inline (see `platform`). The keys `robots`,
`autopilot` and `world.room` keep their own messages naming where their content went.

#### Scenario: Misspelled key
- **WHEN** an environment sets `namespace: true` instead of `namespaces`
- **THEN** loading fails with a message naming `namespace`

#### Scenario: Unknown agent key
- **WHEN** an agent sets `position:` instead of `pose:`
- **THEN** loading fails with a message naming `position` and the agent

#### Scenario: Unknown inline platform key
- **WHEN** an agent's inline platform sets `brige:`
- **THEN** loading fails with a message naming `brige` and the agent
