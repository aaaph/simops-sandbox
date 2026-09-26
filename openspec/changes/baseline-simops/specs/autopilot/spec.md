# Spec Delta

## Purpose

Each agent's PX4 SITL as a dependency: the firmware version is picked by the scenario, the
airframe by the platform, and every agent gets its own instance.

## ADDED Requirements

### Requirement: One PX4 per agent
Every agent SHALL get its own PX4 SITL, attached to that agent in the world by its scenario name,
running the airframe from its platform's `agent.yaml` (`autopilot.px4.airframe`).

Known gap: every agent gets a PX4, so every platform needs a PX4 airframe.

#### Scenario: Airframe from the platform
- **WHEN** `rover1` uses `rover_differential_lidar_px4`, whose airframe is 50000
- **THEN** `px4-rover1` starts with airframe 50000 attached to model `rover1`

### Requirement: Firmware from the scenario
PX4 SHALL be built from `autopilot.px4.ref` (a commit, tag or branch) of `autopilot.px4.repo`
(default: the upstream PX4-Autopilot repository), the same for every agent. Each ref SHALL be
its own image, tagged by the ref's first 12 characters, so switching back to an already built
ref needs no rebuild.

#### Scenario: Ref names the image
- **WHEN** the scenario's ref is `4dbd2e069a5c30c2e53e47e842095d2576dc38c4`
- **THEN** PX4 runs from image `simops-sandbox-px4:4dbd2e069a5c`

### Requirement: Distinct instances
Agents SHALL get distinct PX4 instance numbers `0..N-1` in scenario order, so PX4s sharing one
network namespace do not collide on their ports.

#### Scenario: Second agent
- **WHEN** a scenario has agents `rover1` and `rover2`
- **THEN** `px4-rover1` runs as instance 0 and `px4-rover2` as instance 1
