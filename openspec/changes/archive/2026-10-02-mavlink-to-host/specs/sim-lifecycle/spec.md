## MODIFIED Requirements

### Requirement: Environments are isolated
Each environment's session SHALL run as its own compose project named after the environment, with its own gz
partition. Sessions of two environments SHALL be able to run side by side when their names, router ports
and MAVLink port ranges (`mavlink_port` to `mavlink_port + agents - 1`) differ. A session whose router
port is already taken on the host SHALL fail `up` as "Failed up leaves nothing running" describes. A
session whose MAVLink port range overlaps that of a running session SHALL fail `up` before starting any
container, naming that session. Either way the session that holds the port is left untouched.

#### Scenario: Two scenarios side by side
- **WHEN** environments `a` (router port 7447, MAVLink port 14540) and `b` (router port 7448, MAVLink port 14590) are both up
- **THEN** each has its own containers and neither sees the other's gz or ROS topics or MAVLink

#### Scenario: MAVLink port taken
- **WHEN** environment `a` with MAVLink port 14540 is up and `simops up` runs for environment `b` with router port 7448 and MAVLink port 14540
- **THEN** `up` for `b` names `a`, exits non-zero, starts no container of `b`, and `a` keeps running
