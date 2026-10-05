# Design

## Context

See proposal.md for why. Today `Platform` is a directory (`src/simops/platform.py`): `name`,
`model` and `bridge` are derived from `dir`, `agent.yaml` is parsed into `px4`, and
`bundle.agents()` reads `bridge.yaml` itself (`bundle.py:175`), copies `platform.dir` whole and
spawns `/sim/platforms/<name>/model.sdf`. An agent's `platform` validator
(`agent.py`, `_platform_dir`) only takes a path. Errors from `Platform.parse` are `ValueError`s
starting with `<dir>/agent.yaml`, and `Environment.parse` prefixes them with the environment file
and the pydantic location (`agents.rover1.platform`).

## Goals / Non-Goals

**Goals:**
- One code path for a platform however it is written: directory, inline, with bases.
- `Platform` holds values (model path, bridge entries, autopilot), so `bundle.build` reads no
  platform file but the models it copies, and unit tests build platforms in memory.

**Non-Goals:**
- Fuel URLs, platforms without an autopilot, `diff_drive`, several control modes per platform
  (discussed, later changes).
- Where `/clock` comes from: it stays in the platforms' bridge entries, listed once; the change
  `world-owns-clock` moves it to the world.
- Patching the model's SDF from a document (a base can only replace `model` as a whole).
- Merging lists by key (kustomize's strategic merge): `bridge` is replaced whole.
- `platform:` naming a file instead of a directory.
- Checking that a model refers to nothing outside its directory (absolute mesh paths): such a
  model is broken in the session today too; known gap.

## Decisions

### A platform is resolved to one plain document, then validated once

```
platform: <dir>  --read <dir>/platform.yaml--+
platform: {...}  ----------------------------+--> resolve(doc, here, chain)
                                                  |  base?  -> resolve(base's platform.yaml) first
                                                  |  own paths -> absolute (model, bridge file -> its list)
                                                  |  merge_patch(base_doc, own_doc)
                                                  v
                                             PlatformDocument.model_validate  (extra="forbid")
                                                  v
                                             Platform(model: Path, bridge: list[dict], px4)
```

- Paths are made absolute (and a `bridge` file read into its list) inside `resolve`, per
  document and against that document's directory, before merging — so a base's `model:
  model.sdf` keeps pointing into the base. Validating after the merge means a partial overlay
  (`{base, autopilot: {px4: {version}}}`) is never validated on its own.
- `Platform.load(dir)` reads `platform.yaml` and calls `Platform.parse(document, here=dir,
  origin=<dir>/platform.yaml)`; the agent's validator calls `Platform.parse(mapping,
  here=<environment dir>, origin=None)` for an inline platform. Same shape as `Environment.load`
  / `Environment.parse`.
- Alternative: a pydantic model per document with optional fields, merged as models. Rejected:
  "unset" vs "null removes" vs "default" gets subtle, and merge-patch on plain dicts is the
  well-known semantics.

### JSON Merge Patch, written out

RFC 7386 is a ten-line recursive function over dicts (`null` deletes, dict merges, anything else
replaces); no dependency. Lists replace whole, which is what `bridge` needs now.

### Cycle detection by the chain of platform directories

`resolve` carries the list of resolved `platform.yaml` paths; meeting one again fails with the
chain in order. The same chain is what error messages name ("Platform errors name where they are
written"): `<origin>` then `base <a>/platform.yaml`, ... Inline platforms have no origin of their
own: `Environment.parse` already prefixes the environment file and `agents.<name>.platform`.

### The model's directory replaces the platform directory in the bundle

`Platform.name` becomes `model.parent.name`; the bundle copies `model.parent` (today
`platform.dir`, the same directory for the rover) and spawns `/sim/platforms/<name>/<model file
name>`; a namespaced copy writes its rewritten model under that file name. Borrowed models stay
siblings of the model's directory (`model.parent.parent / <name>`), as now. Two agents whose
model directories differ but share a name fail `build` naming both, instead of one silently
overwriting the other in `platforms/`.

### Old `agent.yaml`

A directory with `agent.yaml` and no `platform.yaml` fails with a message saying `agent.yaml` is
now `platform.yaml` (with `model: model.sdf`, `bridge: bridge.yaml`), like the `room` →
`generate_room` message. Only one platform exists in the repository; it is migrated in this
change.

## Risks / Trade-offs

- [Bridge entries are now shared values: namespacing rewrites them in place today] → copy the
  entries per agent in `bundle.agents()` before rewriting; a unit test with two namespaced agents
  on one platform covers it (existing "Two agents on one platform with namespaces").
- [`model: ../models/foo.sdf` copies the whole `models/` directory into the bundle] → the
  model's directory is the model by definition (gz's own convention, one model per directory);
  stated in the spec, not policed.
- [Errors after the merge cannot say which document set a bad value] → they name the whole
  chain (origin and bases); good enough with chains of one or two.
- [Breaking rename for users with their own platforms] → the old-`agent.yaml` message says
  exactly what to write.

## Migration Plan

`platforms/rover_differential_lidar_px4/agent.yaml` → `platform.yaml` with `model: model.sdf`,
`bridge: bridge.yaml` and the same `autopilot`. Bundles built before keep working; rebuilding
gives the same `bridge.yaml`. Rollback: revert the commit.
