# Design

## Context

See proposal.md — Why. Today `src/worldgen/` is `sdf.py` (the shared envelope `world(name,
parts: list[str])`, `model(...)` and `start_marker(...)` returning XML), `room.py` (placement on
`(x, y, r, is_box, yaw)` tuples, the flood fill, `world_sdf` building wall and obstacle XML) and
`empty.py`. simops calls only `room.generate` and `empty.generate`. The rng is drawn in this
order: per obstacle `r, x, y, is_box, yaw` during placement, then one aspect per box inside
`world_sdf`. Tests pin determinism, reachability and model names (`wall_*`, `obs_*`,
`start_marker`), not bytes.

## Goals / Non-Goals

**Goals:** typed parts, one place per responsibility, the same obstacles and start marker for the
same seed, public `generate` signatures unchanged.
**Non-Goals:** a reachability check that reads walls as parts (the maze change needs it; rooms
keep checking against their bounds), new shapes, the maze itself.

## Decisions

### Layout: parts in `world.py`, XML in `sdf.py`, policy in the world types

```
src/worldgen/
  sdf.py     envelope(name, models: list[str]) and model(...): XML only, no domain
  world.py   Shape, Obstacle, Wall, StartMarker, SdfWorld: what a world is made of, .sdf() each
  room.py    place_obstacles, unreachable_cells, shape_boxes, room_walls, generate: no XML
  empty.py   generate: SdfWorld("field", [StartMarker(clearance)])
```

Dependencies: `room`, `empty` -> `world` -> `sdf`. Parts are frozen dataclasses (stdlib), not
pydantic: they are built by code, never loaded from user input, so there is nothing to validate
at a trust boundary.

### No builder class: one constructor
`SdfWorld(name, parts).sdf()` instead of `builder().add_walls(...).add_obstacles(...).sdf()`.
Parts are order-independent, Python has keyword and default arguments, and a fluent builder
would be a mutable list with one `add_*` method per part type. Assembly reads the same:
`SdfWorld("room", [*room_walls(size), *obstacles, StartMarker(clearance)])`.

### `SdfWorld`, not `World`
simops already has `simops.world.World` (the environment's `world:`); the src-layout change chose
distinct names across the two contexts (`RoomSpec` vs `Room`). "SDF world" is the glossary's own
phrase for what worldgen produces.

### `Wall`: stored as SDF needs it, built from a segment
Fields `name, x, y, length, yaw, thickness=0.15, height=2.5`, rendered as a box
`length x thickness x height` at `(x, y, height/2)` turned by `yaw`. `Wall.from_ab(name, a, b)`
sets the centre to the midpoint, `yaw = atan2`, `length = |ab| + thickness` (square end caps), so
any polyline of walls closes its corners. Alternative, `along="x" | "y"` with the current sizes,
would keep the SDF bytes but has no meaning for a maze's segments.

### `Obstacle`: one type, the shape a field
Fields `name, x, y, radius, shape: Shape, yaw=0, aspect=pi/4`. `Shape` is a `StrEnum` (`BOX`,
`CYLINDER`); `sdf()` matches on it; a new shape is one member and one case, inscribed in the
disc. A box is `2r cos(aspect) x 2r sin(aspect)` (half-diagonal `r`); `pi/4` is square, so a
former cylinder turned into a box by `replace(o, shape=Shape.BOX)` is valid without inventing
proportions. Alternative, `BoxObstacle` / `CylinderObstacle` classes: changing a shape would mean
rebuilding the object field by field. Heights and colours stay as today (`WALL_H / 2`; orange
boxes, blue cylinders), keyed by shape.

### A world type is a pure function; `generate` writes it
`room.world(*, clearance, seed, ...)` and `empty.world(*, clearance)` return an `SdfWorld` and
touch no file (`room.world` raises `ValueError` when the room is not reachable);
`generate(out, ...)` writes `world(...).sdf()` to `out` and returns the summary, its signature
unchanged for simops and the CLI. Parts are frozen dataclasses, so two worlds compare by value:
unit tests assert on `SdfWorld`s and their parts in memory; only the CLI tests, whose behavior is
writing `-o`, use files. Alternative, tests that write and parse SDF: they test the XML twice and
need `tmp_path` for what is a pure computation.

### Same rng stream
`place_obstacles` returns `Obstacle`s with the shape and yaw it draws today and the default
aspect; `unreachable_cells` reads `x, y, radius`; `shape_boxes(rng, obstacles)` then draws one
aspect per box, in order, from `uniform(0.6, 1.0)` as `world_sdf` does now. The rng is consumed
exactly as before, so obstacle models and the start marker come out byte-identical.

## Risks / Trade-offs

- [The SDF of every room changes (walls), so "byte-identical to before" cannot be the check] →
  compare the `obs_*` and `start_marker` model blocks byte for byte against HEAD's output, and
  test the walls geometrically (spec: room walls are joined with no gap).
- [East and west walls get `thickness` longer and overlap the corners] → the overlap lies inside
  the north and south walls; the free space of the room, which the flood fill checks, is unchanged.
- [A future shape not inscribed in the disc would silently break the room's guarantees] → the
  `worldgen` spec makes inscription a requirement; a test asserts it for every `Shape` member.
