# host-access Specification

## Purpose

How code and tools on the host reach a running session: one router port carries both ROS 2 and
gz, and host code has to speak the same transport and message versions as the session.

## Requirements

### Requirement: One port per environment
A session SHALL be reachable from the host through one router port, `network.router_port`,
on TCP and UDP, carrying both ROS 2 and gz traffic.

#### Scenario: Port published
- **WHEN** `rover_room` is up with router port 7447
- **THEN** the host reaches its ROS 2 topics and gz topics through `localhost:7447`

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

### Requirement: What host code must use
Host ROS 2 code SHALL use rmw_zenoh to see the session's topics. Code that talks to an agent's
PX4 SHALL use `px4_msgs` generated from the firmware of that agent's platform (`version` or
`commit` in its `agent.yaml`): message type hashes are part of the topic keys, so any other
version sees no `/fmu/*` topics, without an error.

#### Scenario: Mismatched px4_msgs
- **WHEN** host code built with `px4_msgs` from another PX4 commit subscribes to `/fmu/out/...`
- **THEN** it receives nothing, and no error is reported

### Requirement: Host code listens for MAVLink
Host code SHALL reach the PX4 of the agent at index `i` in environment order over MAVLink by
listening on the host's UDP port `mavlink_port + i`, to which that PX4 sends; it answers to the
address the messages come from. Clients MAY follow one another on the same port for the life of the
session. A ground station listening on the host's port 14550 (QGC) SHALL see every agent's PX4
without being configured, as before.

#### Scenario: Heartbeat on the host port
- **WHEN** a session with agent `rover1` and `mavlink_port: 14590` is up and host code listens on UDP port 14590
- **THEN** it receives MAVLink messages from `rover1`'s PX4, among them its HEARTBEAT

#### Scenario: A second client
- **WHEN** one host client listened on port 14590 and closed, and another one listens on it
- **THEN** the second one receives `rover1`'s HEARTBEAT too

#### Scenario: QGC unchanged
- **WHEN** QGC listens on the host's port 14550 and a session is up
- **THEN** QGC shows the session's agents
