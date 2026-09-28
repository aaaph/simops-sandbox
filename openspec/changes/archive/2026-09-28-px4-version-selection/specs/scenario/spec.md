# Spec Delta

## MODIFIED Requirements

### Requirement: Scenario file
A scenario SHALL be a YAML file with a `name`, a `world` and an `agents` map. When its agents'
platforms use PX4, `autopilot.px4` MAY name the firmware by `version` or by `commit` (see
`autopilot`); with neither, the default firmware is used. Optional keys SHALL default to
`namespaces: false` and `network.router_port: 7447`. The name SHALL identify the scenario's
running instance.

#### Scenario: Defaults applied
- **WHEN** a scenario omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false` and router port 7447

#### Scenario: Old `ref` key
- **WHEN** a scenario sets `autopilot.px4.ref`
- **THEN** loading fails with a message naming `version` and `commit`

#### Scenario: Both version and commit
- **WHEN** a scenario sets both `autopilot.px4.version` and `autopilot.px4.commit`
- **THEN** loading fails, saying only one of them may be given
