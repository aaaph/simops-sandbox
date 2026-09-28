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
`simops host-env <environment>` SHALL print shell exports that make gz and ROS 2 on the host join its
session: its gz partition (the environment name), gz-transport over zenoh, and zenoh client
configuration for gz and for ROS 2 pointing at the environment's router port.

#### Scenario: Env for a scenario
- **WHEN** `simops host-env environments/rover_room.yaml` runs
- **THEN** it prints `GZ_PARTITION='rover_room'`, `GZ_TRANSPORT_IMPLEMENTATION='zenoh'` and zenoh endpoints on `tcp/localhost:7447`

### Requirement: Native GUI
`simops gui <environment>` SHALL open the host's native gz GUI attached to the environment's running session.

#### Scenario: GUI shows the world
- **WHEN** `simops gui` runs against an environment whose session is up
- **THEN** the GUI shows the environment's world with its agents

### Requirement: What host code must use
Host ROS 2 code SHALL use rmw_zenoh to see the session's topics. Code that talks to an agent's
PX4 SHALL use `px4_msgs` generated from the firmware of that agent's platform (`version` or
`commit` in its `agent.yaml`): message type hashes are part of the topic keys, so any other
version sees no `/fmu/*` topics, without an error.

#### Scenario: Mismatched px4_msgs
- **WHEN** host code built with `px4_msgs` from another PX4 commit subscribes to `/fmu/out/...`
- **THEN** it receives nothing, and no error is reported
