# Proposal

## Why

The project's words drifted three times in a week — robot → agent, scenario → blueprint →
environment — and each time a spec kept a stale word for a while (`host-access` pointed at the
removed `ref` key until a rename caught it). The principles everything is built on were agreed
while exploring but live nowhere an author reads before writing: not in the specs (they are not
behavior), not in the OpenSpec context (`openspec/config.yaml` is still the template).

In spec-driven development the specs are behavior contracts written in the project's language;
that language and the principles belong to the project context (spec-kit's constitution, Kiro's
steering, OpenSpec's `context`), which every authoring step reads. In domain-driven design this
is the ubiquitous language: one word per concept, used the same in talk, specs and code.

## What Changes

- `openspec/config.yaml` gets a `context`: the glossary, the principles, the supported stack and
  the working conventions below. OpenSpec shows it to every `propose`, `apply` and `archive`.
- `openspec/config.yaml` gets `rules` that apply the language where it is written: specs and
  proposals use the glossary's terms and no synonyms, a new term enters the glossary in the change
  that first uses it, tasks keep unit tests free of Docker and autopilot builds.
- AGENTS.md's "Words:" paragraph becomes a pointer to the glossary instead of a second copy.
- No spec changes (`skip_specs: true`): terms that already carry behavior (e.g. a session is one
  compose project) stay defined by their requirements; the glossary names them and points there.

### Glossary (draft for review)

Two bounded contexts share a few words, so each term says which side it belongs to.

*Simulation (simops):*
- **platform** — a body type: `platforms/<p>/` with `model.sdf`, `bridge.yaml`, `agent.yaml`
  (what cannot be separated from the body, e.g. the PX4 airframe).
- **agent** — one body in the simulation: an instance of a platform, named in the environment,
  with a start pose. Not a decision-making policy (the RL sense) and not an AI coding agent.
- **environment** — the YAML file: world, agents, PX4 firmware, namespaces, router port; no
  action (`environments/`, spec `environment`).
- **bundle** — an environment built for `docker compose`: `build/<name>/` (spec `bundle`).
- **session** — a running bundle, from `up` to `down`: one compose project, one gz partition
  (spec `sim-lifecycle`).
- **scenario** — reserved: what happens in a session (task, world events, success criteria).
  Not used for the environment. (OpenSpec's `#### Scenario:` blocks are a different, tool word.)
- **sim-only** — channels no real robot has: `/sim/*` and `/clock` (target; `/ground_truth` moves
  under `/sim/` with `sim-oracle-namespace`).
- **ground truth** — the simulator's true state (pose, map, start pose), for evaluation only.
- **sim control** — what only the simulator can do: sessions, world events, time.
- **PX4 firmware** — `version` (a release tag), `commit` (a full SHA) or the default, resolved at
  `build` to one commit (spec `autopilot`).

*Robot software (the user's):*
- **robot software** — the user's deployed stack (estimation, TF, planners, converters); never
  part of simops.
- **hardware interface** — the topics and links a real robot gives (`/scan`, `/fmu/*`).
- **operator interface** — what a ground station or pilot does (arm, mode, mission): reused
  tools — MAVSDK, px4-ros2, QGC.
- **judge** — the user's test code that decides success from the agent's estimate and ground
  truth; SITL-only, never deployed.

### Principles (draft for review)

1. The simulation gives an agent exactly what real hardware gives; everything else is sim-only
   and kept apart. Deployed robot software never reads sim-only channels.
2. The robot software stack is the user's: simops provides physics, autopilot, sensor bridges.
3. First the world, then the agents: at runtime the world starts empty and agents are added; at
   build the world may know agent poses and sizes (to keep spawn areas free).
4. A platform holds what cannot be separated from the body; an environment only picks platforms,
   poses and firmware.
5. Reuse real-world tools for the operator interface; simops builds only sim control and ground
   truth.
6. The bundle is the artifact: plain `docker compose` runs it; simops' job is to build it.

### Stack and conventions (draft for review)

- Supported: PX4 1.18 and later on gz Jetty over zenoh, native macOS GUI; PX4 1.17 and earlier
  would need a second (Harmonic + noVNC) stack.
- Artifacts and code in English; conversation may be in any language.
- A behavior change goes through an OpenSpec change; small fixes and pure cleanups may be plain
  commits.
- Unit tests (`pixi run test`) touch neither Docker nor the network nor an autopilot build;
  Docker tests (`-m docker`) use images that already exist.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — project context only (`skip_specs: true`).

## Impact

- `openspec/config.yaml`, AGENTS.md.
- Every later change is authored against this context; `openspec instructions <artifact>` shows it.
