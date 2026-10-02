## MODIFIED Requirements

### Requirement: Environment contents
An environment SHALL be a YAML file with a `name`, a `world` and an `agents` map. Optional keys
SHALL default to `namespaces: false`, `network.router_port: 7447` and `network.mavlink_port:
14540`. The name SHALL identify the environment's session: its compose project and gz partition.
An environment SHALL NOT name PX4 firmware: each agent's firmware comes from its platform (see
`autopilot`).

#### Scenario: Defaults applied
- **WHEN** an environment omits `namespaces` and `network`
- **THEN** it is loaded with `namespaces: false`, router port 7447 and MAVLink port 14540

#### Scenario: MAVLink port set
- **WHEN** an environment sets `network: {mavlink_port: 14590}`
- **THEN** it is loaded with MAVLink port 14590 and router port 7447

#### Scenario: Old `autopilot` key
- **WHEN** an environment sets `autopilot`
- **THEN** loading fails with a message saying the firmware is set in the platform's `agent.yaml`
