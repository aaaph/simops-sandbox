# Spec Delta

## Purpose

First the world, then the agents: the world runs on its own, agents are added to it at runtime,
and each agent's autopilot attaches only to an agent that is already there.

## ADDED Requirements

### Requirement: Agents are added to the running world
The world SHALL start without agents. Once it runs, each agent SHALL be added to it under its
scenario name, from its platform's model, at its scenario pose.

#### Scenario: Agent added under its name
- **WHEN** the scenario has agent `rover1` at `[0, 0, 0.2]`
- **THEN** the running world contains a model named `rover1` at that pose

### Requirement: Spawn verifies presence, not the reply
Adding an agent SHALL count as done when the agent appears in the world's pose information,
regardless of whether the create request got a reply. Each agent SHALL get up to five attempts;
if it is still absent, spawning SHALL fail.

#### Scenario: Lost create reply
- **WHEN** the world creates the agent but the reply to the request is lost
- **THEN** spawning succeeds once the agent shows up in the world's pose information

#### Scenario: Agent never appears
- **WHEN** an agent is absent after five attempts
- **THEN** spawning fails and says which agent did not appear

### Requirement: Autopilot attaches after its agent exists
A agent's autopilot SHALL start only after spawning succeeded. If spawning fails, no autopilot
SHALL start.

#### Scenario: Spawn failed
- **WHEN** spawning fails
- **THEN** no `px4-<agent>` service starts

### Requirement: World restart brings the agents back
When the world restarts, the agents SHALL be added again and their autopilots restarted, without
user action.

#### Scenario: World container restarts
- **WHEN** the world service restarts
- **THEN** spawning runs again and every `px4-<agent>` restarts attached to its re-added agent
