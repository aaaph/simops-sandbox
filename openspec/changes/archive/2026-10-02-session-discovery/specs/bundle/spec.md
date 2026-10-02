# Spec Delta

## ADDED Requirements

### Requirement: Containers carry their session
Every service in the bundle's `compose.yaml` SHALL be labelled `simops.session` with the session
name and `simops.router_port` with the environment's router port, so that a running session is
found from its containers, however the bundle was started.

#### Scenario: Labels in compose
- **WHEN** an environment `rover_room` with router port 7447 is built
- **THEN** every service in `compose.yaml` has the labels `simops.session: rover_room` and `simops.router_port: "7447"`
