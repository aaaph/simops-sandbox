# Spec Delta

## MODIFIED Requirements

### Requirement: Agent topics come from the platform and the autopilot
Each agent's topics on the ROS 2 bus SHALL be exactly the entries of its platform's
`bridge.yaml` plus, for a PX4 platform, PX4's `/fmu/in/*` and `/fmu/out/*`. For the
`rover_differential_lidar_px4` platform the bridged topics are `/clock`, `/scan`, `/scan/points`
and `/ground_truth`; odometry, IMU and wheel control are PX4's.

#### Scenario: PX4 rover topics
- **WHEN** a session of `environments/rover_room.yaml` is up
- **THEN** the bridge publishes `/clock`, `/scan`, `/scan/points` and `/ground_truth`, and PX4 publishes under `/fmu/out/`

### Requirement: Sim-only topics
`/clock` SHALL be the single simulation clock for the whole session. `/ground_truth` SHALL
carry the agent's true pose and velocity from physics, for evaluation only.

Known gap: `/ground_truth` is named like a hardware topic, not kept apart from them.

#### Scenario: One clock
- **WHEN** an environment has several agents
- **THEN** there is exactly one `/clock` topic, not prefixed
