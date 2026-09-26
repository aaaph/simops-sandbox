# Spec Delta

## Purpose

`build` turns a scenario into a bundle: a self-describing directory with everything plain
`docker compose` needs to run the simulation, produced without starting anything.

## ADDED Requirements

### Requirement: Bundle contents
`simops build <scenario>` SHALL write the bundle to `build/<name>/` and print its path, without
starting any container. The bundle SHALL contain `compose.yaml`, `spawn.sh`, `bridge.yaml`,
`worlds/` with the scenario's world, and `platforms/` with every platform the agents use plus
every model those platforms reference through `model://<name>/` URIs. Building again SHALL
replace the previous bundle entirely.

#### Scenario: Platform borrowing meshes
- **WHEN** an agent's platform references `model://rover_differential_lidar/meshes/...`
- **THEN** the bundle contains both that platform and `platforms/rover_differential_lidar/meshes`

#### Scenario: Rebuild drops stale files
- **WHEN** a bundle directory contains a file the current scenario does not produce and the scenario is built again
- **THEN** the file is gone

### Requirement: The world file contains no agents
The world in the bundle SHALL contain no agents; agents are added at runtime (see
`agent-spawn`). A world file without `<world name="...">` SHALL fail the build with an error
naming the file.

#### Scenario: Generated room is empty
- **WHEN** a scenario with a generated room is built
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
- **WHEN** the same scenario is built twice
- **THEN** both `worlds/room.sdf` files are identical

### Requirement: Merged bridge configuration
`bridge.yaml` SHALL be the union of every agent's platform bridge entries, each entry once.

#### Scenario: Two agents on one platform with namespaces
- **WHEN** two agents use the same platform with `namespaces: true`
- **THEN** `bridge.yaml` has each agent's entries under its own prefix and `/clock` once

### Requirement: Bundle runs on the building machine
The bundle's `compose.yaml` SHALL be runnable with plain `docker compose -f build/<name>/compose.yaml up`
on the machine that built it. It references this repository's Dockerfiles as build contexts, so
it is not portable to other machines.

#### Scenario: Plain compose
- **WHEN** a bundle is started with `docker compose -f build/<name>/compose.yaml up -d`
- **THEN** the same services start as with `simops up`
