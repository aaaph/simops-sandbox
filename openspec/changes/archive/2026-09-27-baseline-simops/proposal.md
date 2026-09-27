# Proposal

## Why

simops was built without specs: its contract lives in AGENTS.md next to environment quirks and
the roadmap, and in `sim/simops.py`. The next changes (sim-only topics under `/sim`, optional
autopilot, mixed fleets) each modify that contract, so it has to exist as specs first: otherwise
their delta specs describe changes against nothing.

## What Changes

- Record the behavior simops has today as specs. The one behavior change: an **agent** is a
  body placed in the simulation, so the specs are born with that name:
  - **BREAKING** scenario key `robots:` becomes `agents:`; each entry keeps `platform:` and
    `pose:`. Platform directories stay in `platforms/`.
  - **BREAKING** a platform's `platform.yaml` becomes `agent.yaml`.
  - Nothing outside this repository reads these files yet, so there is no migration.
- Where current behavior departs from the project's principles, the spec records what is there
  now and names the gap; fixing it belongs to the follow-up changes:
  - `/ground_truth` is published next to hardware topics, not under `/sim` (`sim-oracle-namespace`).
  - every agent gets a PX4, and readiness finds the world through the PX4 service
    (`optional-autopilot`).
  - a generated room keeps only the origin free and reachable, sized for the first agent's
    platform (`optional-autopilot`, when several agents of different sizes appear).
  - TF frame ids are not prefixed with the agent's namespace.
- Add tests for the scenarios the specs name that no test covers yet.

Out of scope: the native pixi stack (`pixi run up/down/doctor`, `sim/stack.py`,
`launch/bringup.launch.py`) — legacy, gets no spec; the gz-transport patch and other
environment workarounds, which stay in AGENTS.md.

## Capabilities

### New Capabilities

- `scenario`: the scenario file — world source (`room` or `file`), autopilot firmware ref,
  agents (platform + pose), `namespaces`, router port; paths relative to the file.
- `bundle`: building a scenario into `build/<name>/` — compose file, world, platforms (and the
  platforms their meshes borrow from), merged bridge config, spawn script; generated rooms are
  deterministic for a seed.
- `sim-lifecycle`: `up` (returns once every agent is in the world and sim time advances; on
  failure prints logs and leaves nothing running), `down`, `run` (up, command, down whatever
  happens), scenarios side by side by name and port.
- `agent-spawn`: world first, then agents — the world starts empty, agents are added to the
  running world under their scenario names, and are added again when the world restarts; the
  autopilot starts only after its agent is in the world.
- `agent-interface`: what user code sees — hardware topics per platform (`/scan`,
  `/scan/points`, `/fmu/*`), sim-only `/clock` and `/ground_truth`, `/<agent>/` prefixes with
  `namespaces: true` (required for more than one agent).
- `host-access`: reaching a scenario from the host — `env` (partition, zenoh endpoints for gz
  and ROS), `gui` (native gz GUI), one router port per scenario; what host code must use
  (rmw_zenoh, px4_msgs from the scenario's PX4 ref).
- `autopilot`: PX4 SITL per agent at the scenario's ref, airframe from the platform, one image
  per ref, own instance number per agent.

### Modified Capabilities

None — `openspec/specs/` is empty.

## Impact

- New: `openspec/specs/` gets its first seven capabilities when this change is archived.
- Code: none, apart from new tests in `sim/tests/` for uncovered scenarios.
- Docs: AGENTS.md keeps quirks, workarounds and how-to; the contract sections can later point
  to the specs instead of restating them.
