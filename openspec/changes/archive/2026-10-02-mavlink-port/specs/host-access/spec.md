## ADDED Requirements

### Requirement: MAVLink from the host
Host code SHALL reach the PX4 of the agent at index `i` in environment order over MAVLink at
`localhost:<mavlink_port + i>` (UDP), by sending to that port: PX4 answers the address it hears
from first. A ground station listening on the host's port 14550 (QGC) SHALL see every agent's PX4
without being configured, as before.

Known gap: PX4 keeps its first host client for its lifetime, so one host client per agent per
session; a later client, or the same one from a new socket, gets no answer until PX4 restarts.

#### Scenario: Heartbeat on the published port
- **WHEN** a session with agent `rover1` and `mavlink_port: 14590` is up and host code sends a MAVLink message to `localhost:14590`
- **THEN** it receives MAVLink messages from `rover1`'s PX4, among them its HEARTBEAT

#### Scenario: QGC unchanged
- **WHEN** QGC listens on the host's port 14550 and a session is up
- **THEN** QGC shows the session's agents
