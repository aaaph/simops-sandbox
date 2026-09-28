# Design

## Context

`World` (`src/simops/world.py`) holds `generate_room: RoomSpec | None` and `file: Path | None`,
enforces "exactly one is set" in a `model_validator(mode="after")`, and exposes whichever is set
through a `source` property. `src/simops/bundle.py` reads `environment.world.source`, branches on
`isinstance(source, WorldFile)`, and otherwise treats it as a `RoomSpec` (`source.size`,
`source.obstacles`, `source.seed`) to call `worldgen.room.generate`, which used to draw four wall
models unconditionally (`world_sdf` in `src/worldgen/room.py`) inside one big literal SDF
document — physics/sensor plugins, GUI, light, `ground_plane` and walls all in one f-string. See
proposal.md for why an empty world needs its own name in the environment file.

## Decisions

**`empty_world` is an open field, not a walled room with zero obstacles.** Tried the walled
version first (`generate_room: {obstacles: 0}` under the hood); running it showed walls where
none were expected.

**The SDF envelope every world type shares moves to its own module, `src/worldgen/sdf.py`; `room`
and `empty` each depend on it, never on each other.** `sdf.py` owns `world(name, parts) -> str`
(physics, sensor plugins, GUI, the arrow-key triggers, the sun, `ground_plane` — wraps whatever
`parts` a caller supplies) plus the per-model snippet builders every world type would need
(`model()`, `start_marker()`, `gui_section()`). `room.py` keeps its own concerns — obstacle
sampling, the reachability flood fill, walls — and calls `sdf.world("room", parts)` with its own
`parts` (walls + obstacles + a marker). `empty.py` calls the same `sdf.world(...)`, with its own
name (`"field"`) and its own, much shorter `parts` (just a marker), and imports nothing from
`room.py`. Tried first:
`empty.py` calling `room.generate(..., obstacles=0, walls=False)` — rejected once written, because
it makes the open field a special case of a room (a `walls` flag `room.py` has to carry for a
caller that isn't drawing a room at all), backwards from how the two are meant to stand as peers,
and awkward for a future third type (`worldgen maze`, on the roadmap in AGENTS.md) that would
otherwise have to bolt itself onto `room.py` too or start the same argument over again.

**`start_marker` takes `clearance` and computes its own radius, not a pre-computed radius.** Both
`room.py` and `empty.py` need "a marker sized off how wide the robot is"; computing
`clearance / 2 * 1.2` in each caller would duplicate the one place that conversion should live.

**`EmptySpec` is its own type, all the way through — `World.source` returns it as-is, `bundle.py`
gets a third `isinstance` branch.** A dedicated model, `extra="forbid"`, with **no fields**:
nothing is left to configure once there are no walls to size and no obstacles to count or seed.
`bundle.py`'s branch calls `worldgen.empty.generate(sdf, clearance=...)` directly — `EmptySpec`
never becomes a `RoomSpec` object, so `isinstance(source, RoomSpec)` stays true only for an
environment that actually set `generate_room`.
Alternative considered and rejected: desugar `empty_world` into `RoomSpec(obstacles=0, ...)`
inside `World.source`, so `bundle.py` needs no new branch. Rejected independent of the worldgen
question above — it makes `world.source` lie about what was actually given.

**A bare `empty_world:` (YAML null) is rewritten to `{}` in a `model_validator(mode="before")`
before pydantic sees it.** A declared field `empty_world: EmptySpec | None = None` cannot
otherwise distinguish "given as null" from "omitted" — both leave the field `None`, which the
"exactly one source" check needs to tell apart. The existing `_old_room` before-validator on the
same class is the precedent for this kind of raw-dict fixup.

## Non-Goals

- Configuring `empty_world` at all (no `size`, no `seed`, no `obstacles`): it names one specific
  thing, an open field with a start marker.
- A `walls: false` option on `room.generate` itself: nothing needs a walled room's obstacle
  placement and reachability check without the walls that bound them, now that `empty.py` builds
  an open field independently.
- A formal base class/protocol for world types: `sdf.py`'s `world(name, parts)` plus its snippet
  builders are the shared abstraction a future `maze.py` would use the same way `room.py` and
  `empty.py` do; nothing today calls for more structure than "supply your own `parts`".

## Risks / Trade-offs

- `bundle.py` gains a third branch that partly repeats the `RoomSpec` one (clearance from the
  first agent's platform, call into `worldgen`). Accepted: three lines, and each branch stays
  honest about which source produced it — matching how `WorldFile` already gets its own branch
  instead of being folded into `RoomSpec`.
