# Proposal

## Why

`/clock` is the world's: the gz server publishes it, one per session, with or without agents. Yet
it is bridged only because each platform's bridge entries list it, and the bundle keeps it once.
A platform that leaves it out — an inline platform written by hand — leaves the session without
sim time, and a session's clock should not depend on which platforms its agents use.

## What Changes

- The world bridges `/clock` (`rosgraph_msgs/msg/Clock` from gz `/clock`, gz to ROS): the
  bundle's `bridge.yaml` is the world's entries, `/clock`, then every agent's platform entries.
  The environment gets no new key.
- **BREAKING** A platform's bridge entries SHALL NOT bridge `/clock`: loading fails naming the
  platform and saying the world bridges it. `platforms/rover_differential_lidar_px4/bridge.yaml`
  drops its `/clock` entry.
- Not in this change: a `world.bridge` key for the world's own topics (a sensor placed in a world,
  world-level ground truth); it comes with the first world that has such topics.

Applies after `platform-inline-and-base` (it words an agent's topics as its platform's bridge
entries, which this change edits again).

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `bundle`: `bridge.yaml` starts with the world's `/clock`, then the agents' entries.
- `agent-interface`: `/clock` is the world's, not an agent's; the rover's bridged topics no longer
  include it; a platform listing it fails loading.

## Impact

- Code: `src/simops/world.py` (the world's bridge entries), `src/simops/bundle.py` (merge starts
  with them; the `/clock` special cases in namespacing go), `src/simops/platform.py` (a bridge
  entry for `/clock` is rejected).
- Files: `platforms/rover_differential_lidar_px4/bridge.yaml` loses `/clock`.
- Tests: `test_bundle.py`, `test_platform.py`.
- Docs: `AGENTS.md` (the `sim-sensors` line), the `sim-only` glossary entry in
  `openspec/config.yaml` if it needs to say where `/clock` comes from.
- Sessions see the same topics as before.
