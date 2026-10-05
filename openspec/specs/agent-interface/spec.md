# agent-interface Specification

## Purpose

The topics user code sees: what each agent publishes and consumes, and how names change when
several agents share one simulation.

## Requirements

### Requirement: Agent topics come from the platform and the autopilot
Each agent's topics on the ROS 2 bus SHALL be exactly its platform's bridge entries (see
`platform`), wherever the platform is written, plus, for a PX4 platform, PX4's `/fmu/in/*` and
`/fmu/out/*`. For the `rover_differential_lidar_px4` platform the bridged topics are `/scan`,
`/scan/points` and `/ground_truth`; odometry, IMU and wheel control are PX4's. `/clock` is the
world's, not an agent's (see "Sim-only topics").

#### Scenario: PX4 rover topics
- **WHEN** a session of `environments/rover_room.yaml` is up
- **THEN** the bridge publishes `/clock`, `/scan`, `/scan/points` and `/ground_truth`, and PX4 publishes under `/fmu/out/`

#### Scenario: Inline bridge
- **WHEN** the only agent's inline platform has `base: ../platforms/rover_differential_lidar_px4` and `bridge` with only the `/scan` entry
- **THEN** the bridge publishes `/clock` and `/scan`, and no `/scan/points` or `/ground_truth`

### Requirement: Sim-only topics
`/clock` SHALL be the single simulation clock for the whole session, bridged by the world
whatever the agents' platforms are. A platform's bridge entries SHALL NOT bridge `/clock`
(neither as the gz nor as the ROS topic); loading an environment that uses such a platform SHALL
fail, naming where the platform is written and saying the world bridges `/clock`.
`/ground_truth` SHALL carry the agent's true pose and velocity from physics, for evaluation only.

Known gap: `/ground_truth` is named like a hardware topic, not kept apart from them.

#### Scenario: One clock
- **WHEN** an environment has several agents
- **THEN** there is exactly one `/clock` topic, not prefixed

#### Scenario: Clock without any platform listing it
- **WHEN** a session's only agent has a platform whose bridge lists only `/scan`
- **THEN** `/clock` is published

#### Scenario: Platform listing /clock
- **WHEN** an agent's platform bridge has an entry with `gz_topic_name: /clock`
- **THEN** loading the environment fails naming that platform and saying the world bridges `/clock`

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
