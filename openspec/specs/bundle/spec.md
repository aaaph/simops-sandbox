# bundle Specification

## Purpose

`build` turns an environment into a bundle: a self-describing directory with everything plain
`docker compose` needs to run the simulation, produced without starting anything.

## Requirements

### Requirement: Bundle contents
`simops build <environment>` SHALL write the bundle to `build/<name>/` and print its path, without
starting any container; when `SIMOPS_BUILD_DIR` is set, bundles go to `$SIMOPS_BUILD_DIR/<name>/`
instead, for `build`, `up`, `down` and `run` alike. The bundle SHALL contain `compose.yaml`, `spawn.sh`, `bridge.yaml`,
`worlds/` with the environment's world, and `platforms/` with every platform the agents use plus
every model those platforms reference through `model://<name>/` URIs. Building again SHALL
replace the previous bundle entirely.

#### Scenario: Platform borrowing meshes
- **WHEN** an agent's platform references another model, `model://<other>/meshes/...`
- **THEN** the bundle contains both that platform and `platforms/<other>/meshes`

#### Scenario: Bundles elsewhere
- **WHEN** `SIMOPS_BUILD_DIR=/tmp/bundles simops build rover_room.yaml` runs
- **THEN** the bundle is written to `/tmp/bundles/rover_room/` and nothing to `build/`

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

### Requirement: Containers carry their session
Every service in the bundle's `compose.yaml` SHALL be labelled `simops.session` with the session
name and `simops.router_port` with the environment's router port, so that a running session is
found from its containers, however the bundle was started.

#### Scenario: Labels in compose
- **WHEN** an environment `rover_room` with router port 7447 is built
- **THEN** every service in `compose.yaml` has the labels `simops.session: rover_room` and `simops.router_port: "7447"`
