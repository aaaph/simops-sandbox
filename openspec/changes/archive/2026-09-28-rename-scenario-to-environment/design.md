# Design

## Context

See proposal.md — Why. "Scenario" is in 7 main specs (23 requirements outside the `scenario`
spec, 5 Purpose sections), `sim/simops.py` (CLI argument, messages, the `sc` variable), both test
modules, AGENTS.md, comments in `pixi.toml`, `pytest.ini`, `readme.md`, `agent.yaml`, and two open
proposals. OpenSpec's own files under `.agents/` and `.claude/` use "scenario" in OpenSpec's sense
(WHEN/THEN blocks) and are not part of this rename.

## Goals / Non-Goals

**Goals:** one word per concept — environment (file), bundle (built), session (running), scenario
reserved for a future action layer; no command reads `simops env environments/…`. **Non-Goals:** any behavior change; the action layer itself.

## Decisions

### Retire `scenario`, add `environment` — not a rename in place
OpenSpec renames requirements (RENAMED), not capabilities. The change removes every `scenario`
requirement (`retire_capabilities: true`, so archive deletes the emptied spec) and adds them,
reworded, to a new `environment` capability with its own Purpose.
*Alternative:* keep the capability id `scenario` and only reword its text — rejected, the spec
file name is the first thing a reader sees.

### "Session" where the text means the running thing
Plain replacement gives "no container of the environment remains" or "a running environment". Where
the text means containers, topics or a torn-down run, it says "session" (defined in the
`environment` Purpose); where it means the file, "environment".

### Scenario headings inside MODIFIED blocks keep their names
OpenSpec rejects a MODIFIED block whose `#### Scenario:` names differ from the current ones, so
"Env for a scenario" and "Two scenarios side by side" keep their headings; their bodies are
reworded. New capability `environment` names its scenarios freely.

### Purpose sections are edited in the main specs directly
Delta specs cannot change an existing capability's Purpose; the five Purpose sections that say
"scenario" are reworded in `openspec/specs/<capability>/spec.md` during apply.

### No alias for the old directory
simops takes the environment by path, so there is nothing to alias: `scenarios/` moves to
`environments/` with `git mv`, and old paths simply do not exist. The YAML format is unchanged.

### `simops env` becomes `simops host-env`
With the file called an environment, `simops env environments/rover_room.yaml` reads as two
different things named "env". The command prints the host shell exports (`host_env()`, spec
`host-access`), so it is named after that. No alias: one user today.

### Why not "blueprint"
Tried first: IDEs with the Red Hat YAML extension apply SchemaStore's "Quali Torque Blueprint
Spec 2" to `**/blueprints/**.yaml` and flag every key. No SchemaStore schema matches
`environments/*.yaml`.

### Fix found on the way
`host-access` still said `px4_msgs` come from `autopilot.px4.ref`, which `px4-version-selection`
removed; its MODIFIED block says "the environment's PX4 firmware (`version` or `commit`)".

## Risks / Trade-offs

- [Two OpenSpec scenario headings keep the old word] → cosmetic; a later change touching those
  requirements can rename them with a REMOVED + ADDED pair.
- [Paths in shell history break] → one user today; AGENTS.md shows the new paths.
