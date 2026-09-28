# Spec Delta

## MODIFIED Requirements

### Requirement: Agents are added to the running world
The world SHALL start without agents. Once it runs, each agent SHALL be added to it under its
environment name, from its platform's model, at its environment pose.

#### Scenario: Agent added under its name
- **WHEN** the environment has agent `rover1` at `[0, 0, 0.2]`
- **THEN** the running world contains a model named `rover1` at that pose
