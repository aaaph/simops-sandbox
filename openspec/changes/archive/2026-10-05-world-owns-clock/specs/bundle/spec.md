## MODIFIED Requirements

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
