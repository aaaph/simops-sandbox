## ADDED Requirements

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

## REMOVED Requirements

### Requirement: MAVLink from the host
**Reason**: host code no longer sends to a published port first; PX4 sends to the host.
**Migration**: "Host code listens for MAVLink": listen on `udpin://0.0.0.0:<mavlink_port + i>`.
