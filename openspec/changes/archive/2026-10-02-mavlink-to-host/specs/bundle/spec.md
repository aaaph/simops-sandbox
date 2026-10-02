## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Containers carry their session
Every service in the bundle's `compose.yaml` SHALL be labelled `simops.session` with the session
name, `simops.router_port` with the environment's router port and `simops.mavlink_ports` with its
MAVLink port range (`<first>-<last>`, `mavlink_port` to `mavlink_port + agents - 1`), so that a
running session and the ports it uses are found from its containers, however the bundle was
started.

#### Scenario: Labels in compose
- **WHEN** an environment `rover_room` with router port 7447, MAVLink port 14540 and one agent is built
- **THEN** every service in `compose.yaml` has the labels `simops.session: rover_room`, `simops.router_port: "7447"` and `simops.mavlink_ports: "14540-14540"`

## REMOVED Requirements

### Requirement: MAVLink ports published
**Reason**: MAVSDK's `mavsdk_server` waits for the vehicle to speak first, while a PX4 reached
through a published port waits for its client to; they never meet.
**Migration**: PX4 sends to the host (requirement "MAVLink to the host"); host code listens on
`udpin://0.0.0.0:<mavlink_port + i>` instead of sending to `udpout://localhost:<port>`.
