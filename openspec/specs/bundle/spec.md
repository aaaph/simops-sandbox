# bundle Specification

## Purpose

`build` turns an environment into a bundle: a self-describing directory with everything plain
`docker compose` needs to run the simulation, produced without starting anything.

## Requirements

### Requirement: Bundle contents
`simops build <environment>` SHALL write the bundle to `build/<name>/` and print its path, without
starting any container; when `SIMOPS_BUILD_DIR` is set, bundles go to `$SIMOPS_BUILD_DIR/<name>/`
instead, for `build`, `up`, `down` and `run` alike. The bundle SHALL contain `compose.yaml`, `spawn.sh`, `bridge.yaml`,
`worlds/` with the environment's world, and `platforms/` with the directory of every agent's
model (see `platform`, "The model's directory is the model"), under that directory's name, plus
every model those models reference through `model://<name>/` URIs. Each agent SHALL be spawned
from its model's own file in `platforms/`, whatever that file is named. Two agents whose models
lie in different directories of the same name SHALL fail the build, naming both directories.
Building again SHALL replace the previous bundle entirely.

#### Scenario: Platform borrowing meshes
- **WHEN** an agent's platform references another model, `model://<other>/meshes/...`
- **THEN** the bundle contains both that platform and `platforms/<other>/meshes`

#### Scenario: Model not named model.sdf
- **WHEN** an agent's inline platform sets `model: ../models/husky/husky.sdf`
- **THEN** the bundle contains `platforms/husky/husky.sdf` and the agent is spawned from it

#### Scenario: Two agents, one model directory
- **WHEN** `rover1` names `platforms/rover_differential_lidar_px4` and `rover11` has an inline platform whose `model` is that directory's `model.sdf`
- **THEN** the bundle contains `platforms/rover_differential_lidar_px4` once

#### Scenario: Two model directories, one name
- **WHEN** two agents' models are `a/rover/model.sdf` and `b/rover/model.sdf`
- **THEN** the build fails naming `a/rover` and `b/rover`

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
`bridge.yaml` SHALL start with the world's entries — `/clock` (`rosgraph_msgs/msg/Clock` from gz
`/clock`, gz to ROS), whatever the world source — followed by the union of every agent's platform
bridge entries, each entry once.

#### Scenario: Two agents on one platform with namespaces
- **WHEN** two agents use the same platform with `namespaces: true`
- **THEN** `bridge.yaml` has each agent's entries under its own prefix and `/clock` once

#### Scenario: Clock first
- **WHEN** an environment with one agent on `rover_differential_lidar_px4` is built
- **THEN** `bridge.yaml` lists `/clock` first, then `/scan`, `/scan/points` and `/ground_truth`

#### Scenario: Platform with no topics of its own
- **WHEN** the only agent's platform has an empty bridge
- **THEN** `bridge.yaml` holds exactly the `/clock` entry

### Requirement: Bundle runs on the building machine
The bundle's `compose.yaml` SHALL be runnable with plain `docker compose -f build/<name>/compose.yaml up`
on the machine that built it. It references this repository's Dockerfiles as build contexts, so
it is not portable to other machines.

#### Scenario: Plain compose
- **WHEN** a bundle is started with `docker compose -f build/<name>/compose.yaml up -d`
- **THEN** the same services start as with `simops up`

### Requirement: Containers carry their session
Every service in the bundle's `compose.yaml` SHALL be labelled `simops.session` with the session
name, `simops.router_port` with the environment's router port and `simops.mavlink_ports` with its
MAVLink port range (`<first>-<last>`, `mavlink_port` to `mavlink_port + agents - 1`), so that a
running session and the ports it uses are found from its containers, however the bundle was
started.

#### Scenario: Labels in compose
- **WHEN** an environment `rover_room` with router port 7447, MAVLink port 14540 and one agent is built
- **THEN** every service in `compose.yaml` has the labels `simops.session: rover_room`, `simops.router_port: "7447"` and `simops.mavlink_ports: "14540-14540"`

### Requirement: MAVLink to the host
The bundle's compose file SHALL make the PX4 of the agent at index `i` in environment order (its
PX4 instance) send its API (offboard) MAVLink link to the host's UDP port `mavlink_port + i`, and
SHALL publish no MAVLink port. PX4's GCS link SHALL keep sending to the host's port 14550.

#### Scenario: One agent
- **WHEN** an environment with agent `rover1` and `mavlink_port: 14590` is built
- **THEN** `rover1`'s PX4 is set to send its API link to the host's port 14590, and `compose.yaml` publishes only the router port

#### Scenario: Two agents
- **WHEN** an environment with agents `rover1` and `rover2` and the default MAVLink port is built
- **THEN** `rover1`'s PX4 sends to the host's port 14540 and `rover2`'s to 14541
