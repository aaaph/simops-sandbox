# Spec Delta

## MODIFIED Requirements

### Requirement: Host environment
`simops host-env [environment]` SHALL print shell exports that make gz and ROS 2 on the host join
a session: its gz partition (the environment name), gz-transport over zenoh, zenoh client
configuration for gz and for ROS 2 pointing at its router port, and `GZ_SIM_RESOURCE_PATH` at the
`platforms/` of its bundle. Given an environment file, it SHALL print them from the file, whether
the session runs or not. Given a session name or nothing, it SHALL take them from the running
session (see `sim-lifecycle`, "Commands find the running session") and fail, saying nothing is up,
when that session's router is not running.

#### Scenario: Env for a scenario
- **WHEN** `simops host-env environments/rover_room.yaml` runs
- **THEN** it prints `GZ_PARTITION='rover_room'`, `GZ_TRANSPORT_IMPLEMENTATION='zenoh'`, zenoh endpoints on `tcp/localhost:7447` and `GZ_SIM_RESOURCE_PATH` ending in `rover_room/platforms`

#### Scenario: Env of the running session
- **WHEN** only `rover_room` is up with router port 7448 and `simops host-env` runs without an argument
- **THEN** it prints `GZ_PARTITION='rover_room'` and zenoh endpoints on `tcp/localhost:7448`

#### Scenario: Nothing up
- **WHEN** no session is up and `simops host-env` runs without an argument
- **THEN** it says nothing is up, prints no exports and exits non-zero

### Requirement: Native GUI
`simops gui [environment]` SHALL open the host's native gz GUI attached to a running session (see
`sim-lifecycle`, "Commands find the running session"), loading the agents' meshes from the
session's bundle. When the session's world is not running it SHALL not open the GUI: it SHALL say
which session is not up and how to start it, and exit non-zero at once.

#### Scenario: GUI shows the world
- **WHEN** `simops gui` runs against an environment whose session is up
- **THEN** the GUI shows the environment's world with its agents

#### Scenario: Meshes from the bundle
- **WHEN** `simops gui` runs from a repository with no `platforms/` of its own
- **THEN** the GUI shows the agents' meshes, read from the session's bundle

#### Scenario: Session not up
- **WHEN** `rover_room` is not up and `simops gui environments/rover_room.yaml` runs
- **THEN** it says `rover_room` is not up, names `simops up environments/rover_room.yaml` and exits non-zero without waiting
