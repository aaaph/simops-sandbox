# Spec Delta

## MODIFIED Requirements

### Requirement: Bundle contents
`simops build <environment>` SHALL write the bundle to `build/<name>/` and print its path, without
starting any container. The bundle SHALL contain `compose.yaml`, `spawn.sh`, `bridge.yaml`,
`worlds/` with the environment's world, and `platforms/` with every platform the agents use plus
every model those platforms reference through `model://<name>/` URIs. Building again SHALL
replace the previous bundle entirely.

#### Scenario: Platform borrowing meshes
- **WHEN** an agent's platform references `model://rover_differential_lidar/meshes/...`
- **THEN** the bundle contains both that platform and `platforms/rover_differential_lidar/meshes`

#### Scenario: Rebuild drops stale files
- **WHEN** a bundle directory contains a file the current environment does not produce and the environment is built again
- **THEN** the file is gone

### Requirement: The world file contains no agents
The world in the bundle SHALL contain no agents; agents are added at runtime (see
`agent-spawn`). A world file without `<world name="...">` SHALL fail the build with an error
naming the file.

#### Scenario: Generated room is empty
- **WHEN** an environment with a generated room is built
- **THEN** `worlds/room.sdf` includes no agent model

#### Scenario: World without a name
- **WHEN** `world.file` points at an SDF whose `<world>` has no name
- **THEN** the build fails naming that file

### Requirement: Deterministic generated rooms
A generated room SHALL be identical for the same `seed`, `size`, `obstacles` and first agent's
platform. Its obstacles SHALL keep the area around the origin free, and every free cell SHALL
be reachable from the origin for an agent as wide as the first agent's platform.

Known gap: only the origin is guaranteed, not each agent's pose, and only the first agent's
width is used.

#### Scenario: Same seed, same room
- **WHEN** the same environment is built twice
- **THEN** both `worlds/room.sdf` files are identical
