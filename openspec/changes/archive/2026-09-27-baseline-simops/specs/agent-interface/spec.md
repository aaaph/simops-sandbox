# Spec Delta

## Purpose

The topics user code sees: what each agent publishes and consumes, and how names change when
several agents share one simulation.

## ADDED Requirements

### Requirement: Agent topics come from the platform and the autopilot
Each agent's topics on the ROS 2 bus SHALL be exactly the entries of its platform's
`bridge.yaml` plus, for a PX4 platform, PX4's `/fmu/in/*` and `/fmu/out/*`. For the
`rover_differential_lidar_px4` platform the bridged topics are `/clock`, `/scan`, `/scan/points`
and `/ground_truth`; odometry, IMU and wheel control are PX4's.

#### Scenario: PX4 rover topics
- **WHEN** `scenarios/rover_room.yaml` is up
- **THEN** the bridge publishes `/clock`, `/scan`, `/scan/points` and `/ground_truth`, and PX4 publishes under `/fmu/out/`

### Requirement: Sim-only topics
`/clock` SHALL be the single simulation clock for the whole scenario. `/ground_truth` SHALL
carry the agent's true pose and velocity from physics, for evaluation only.

Known gap: `/ground_truth` is named like a hardware topic, not kept apart from them.

#### Scenario: One clock
- **WHEN** a scenario has several agents
- **THEN** there is exactly one `/clock` topic, not prefixed

### Requirement: Namespaces
With `namespaces: true`, every topic of an agent — gz and ROS, bridged and PX4 — SHALL be under
`/<agent>/`, except `/clock`. With `namespaces: false` topics SHALL keep their platform names.
TF frame ids SHALL NOT be prefixed (known gap).

#### Scenario: Namespaced rover
- **WHEN** agent `rover2` runs with `namespaces: true`
- **THEN** its topics are `/rover2/scan`, `/rover2/scan/points`, `/rover2/ground_truth` and `/rover2/fmu/...`

#### Scenario: Single agent without namespaces
- **WHEN** `rover_room.yaml` runs with `namespaces: false`
- **THEN** the topics are `/scan`, `/ground_truth` and `/fmu/...` with no prefix
