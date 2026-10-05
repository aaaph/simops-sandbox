## MODIFIED Requirements

### Requirement: Agent topics come from the platform and the autopilot
Each agent's topics on the ROS 2 bus SHALL be exactly its platform's bridge entries (see
`platform`), wherever the platform is written, plus, for a PX4 platform, PX4's `/fmu/in/*` and
`/fmu/out/*`. For the `rover_differential_lidar_px4` platform the bridged topics are `/clock`,
`/scan`, `/scan/points` and `/ground_truth`; odometry, IMU and wheel control are PX4's.

#### Scenario: PX4 rover topics
- **WHEN** a session of `environments/rover_room.yaml` is up
- **THEN** the bridge publishes `/clock`, `/scan`, `/scan/points` and `/ground_truth`, and PX4 publishes under `/fmu/out/`

#### Scenario: Inline bridge
- **WHEN** the only agent's inline platform has `base: ../platforms/rover_differential_lidar_px4` and `bridge` with only the `/clock` and `/scan` entries
- **THEN** the bridge publishes `/clock` and `/scan`, and no `/scan/points` or `/ground_truth`
