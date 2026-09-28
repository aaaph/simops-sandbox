# Spec Delta

## MODIFIED Requirements

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
