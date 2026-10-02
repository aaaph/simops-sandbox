## ADDED Requirements

### Requirement: MAVLink ports published
The bundle's compose file SHALL publish each agent's PX4 API (offboard) MAVLink link on the host:
the agent at index `i` in environment order (its PX4 instance) on UDP port `mavlink_port + i`.
Inside the session the link stays PX4's own (`14580 + i`); only the host port depends on the
environment. PX4's GCS link SHALL keep sending to the host's port 14550, unpublished.

#### Scenario: One agent
- **WHEN** an environment with agent `rover1` and `mavlink_port: 14590` is built
- **THEN** `compose.yaml` publishes host UDP port 14590 to `rover1`'s PX4 API link (14580 in the session)

#### Scenario: Two agents
- **WHEN** an environment with agents `rover1` and `rover2` and the default MAVLink port is built
- **THEN** `compose.yaml` publishes host UDP 14580 to `rover1`'s PX4 (14580) and 14581 to `rover2`'s (14581)
