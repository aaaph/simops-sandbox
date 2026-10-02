## MODIFIED Requirements

### Requirement: Environments are isolated
Each environment's session SHALL run as its own compose project named after the environment, with its own gz
partition. Sessions of two environments SHALL be able to run side by side when their names, router ports
and MAVLink port ranges (`mavlink_port` to `mavlink_port + agents - 1`) differ. A session whose router
port or any of whose MAVLink ports is already taken on the host SHALL fail `up` as "Failed up leaves
nothing running" describes, leaving the session that holds the port untouched.

#### Scenario: Two scenarios side by side
- **WHEN** environments `a` (router port 7447, MAVLink port 14580) and `b` (router port 7448, MAVLink port 14590) are both up
- **THEN** each has its own containers and neither sees the other's gz or ROS topics or MAVLink

#### Scenario: MAVLink port taken
- **WHEN** environment `a` with MAVLink port 14580 is up and `simops up` runs for environment `b` with router port 7448 and MAVLink port 14580
- **THEN** `up` for `b` exits non-zero, no container of `b` remains, and `a` keeps running
