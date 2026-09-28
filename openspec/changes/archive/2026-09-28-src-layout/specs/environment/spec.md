# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
