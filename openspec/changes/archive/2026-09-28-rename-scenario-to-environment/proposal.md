# Proposal

## Why

"Scenario" promises action — in simulation practice (ASAM OpenSCENARIO next to OpenDRIVE, CARLA's
scenarios over its towns) a scenario is what happens: manoeuvres, events, start and stop
conditions. The simops file describes no action: world, agents, their start poses, firmware — the
environment the developer's own code then acts in. The word is also wanted later for exactly
that action layer (task, world events, success criteria), and in the specs it collides with
OpenSpec's own `#### Scenario:` blocks ("Scenario: Scenario loaded from another directory").

"Blueprint" was tried first and dropped: IDEs match `**/blueprints/**.yaml` to Quali Torque's
schema from SchemaStore and flag every key. `environments/` matches no SchemaStore schema.

## What Changes

- The file is an **environment**: the world, agents and firmware a simulation runs, with no
  action. The vocabulary becomes environment (the YAML) → bundle (`build` output) → session (a
  running bundle, `up` to `down`); "scenario" is left free for the future action layer.
- **BREAKING** `scenarios/` becomes `environments/` (`environments/rover_room.yaml`). The YAML
  inside is unchanged, and simops takes the file by path, so only paths change.
- **BREAKING** `simops env` becomes `simops host-env`, so the command that prints host shell
  exports does not read as `simops env environments/…`.
- The `scenario` capability is retired and its requirements move, reworded, to a new
  `environment` capability; the other capabilities say "environment" where they said "scenario",
  and "session" where they mean the running thing (three requirement names change: "Firmware from
  the environment", "One port per environment", "Environments are isolated").
- CLI arguments, help, messages, code names, tests, AGENTS.md, config comments and the two open
  proposals follow.

## Capabilities

### New Capabilities

- `environment`: the environment file — `name`, world source, agents (platform + pose), PX4
  firmware (`version` / `commit`), namespaces, router port; paths relative to the file.

### Modified Capabilities

- `scenario`: retired — every requirement removed, moved to `environment`.
- `host-access`: `simops env` is renamed `simops host-env`; wording.
- `agent-interface`, `agent-spawn`, `autopilot`, `bundle`, `sim-lifecycle`: wording only — no
  behavior changes.

## Impact

- `scenarios/` → `environments/`; `sim/simops.py`, `sim/tests/`, AGENTS.md, `pixi.toml`,
  `pytest.ini`, `readme.md`, `agent.yaml` comments, `openspec/specs/`, open changes
  `session-isolation`, `bundle-manifest-truth`.
- Shell history and scripts with `scenarios/...` paths or `simops env`.
- "Environment" stays overloaded elsewhere — pixi environments (`.pixi/envs/`), the compose
  `environment:` key of each service — which is why the host command moves to `host-env`.
- OpenSpec scenario headings that must keep their names in a MODIFIED block keep the old word
  ("Env for a scenario", "Two scenarios side by side"); their bodies are reworded.
