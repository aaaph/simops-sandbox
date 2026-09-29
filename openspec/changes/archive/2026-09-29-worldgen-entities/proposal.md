# Proposal

## Why

worldgen's world types are assembled from XML strings: `room.world_sdf` writes `<box><size>…`
itself and decides a box's proportions only while serializing, and the room's obstacles are
anonymous tuples `(x, y, r, is_box, yaw)`. The glossary's world generation terms — room,
obstacle, open field — exist in the docs, but the things a world is made of have no types. This
change makes the code readable and splits the responsibilities: what is in the world, where the
room puts it, and how it becomes SDF. It also lays the ground for `worldgen maze`, which needs
walls defined by segments.

## What Changes

- worldgen gets types for what an SDF world is made of: `Wall`, `Obstacle` (with a `Shape`:
  `BOX` or `CYLINDER`, open to more), `StartMarker`, and `SdfWorld(name, parts)`. Each part
  renders its own SDF; `SdfWorld.sdf()` wraps the parts in the shared envelope.
- `Wall.from_ab(name, a, b)` builds a wall along a segment, extended by half its thickness beyond
  each end, so walls meeting at a point close the corner.
- An `Obstacle` is a footprint disc (position, radius) plus a shape inscribed in it. The room's
  placement and reachability check read only the footprint, so changing an obstacle's shape
  (`dataclasses.replace(o, shape=Shape.BOX)`) never breaks the room's guarantees.
- `room.py` loses all XML: it places obstacles, checks reachability and assembles an `SdfWorld`.
  `empty.py` is one `SdfWorld` line. `sdf.py` keeps the envelope and the XML helper.
- Rooms keep their obstacles, sizes and start marker for the same seed. The walls are
  described differently in the SDF (east and west walls rotated by π/2 and `T` longer, overlapping
  the corners the other walls already fill); the room occupies the same space.
- `worldgen room` / `worldgen empty` commands and `room.generate` / `empty.generate` keep their
  signatures; simops is untouched.
- The glossary gains wall, obstacle shape, start marker and SDF world, pointing to the new
  `worldgen` spec.

## Capabilities

### New Capabilities

- `worldgen`: what an SDF world is made of (walls, obstacles with a shape, the start marker),
  how parts are assembled into a world, and the room's guarantees (clearance, reachability, same
  seed same room) stated in terms of obstacle footprints.

### Modified Capabilities

None. The `environment` and `bundle` requirements on generated worlds hold unchanged.

## Impact

- `src/worldgen/`: new `world.py` (the parts and `SdfWorld`); `room.py`, `empty.py`, `sdf.py`
  reworked; `cli.py` unchanged.
- `tests/worldgen/`: `test_room.py` builds `Obstacle`s instead of tuples; new tests for
  `Wall.from_ab` and obstacle shapes.
- `openspec/config.yaml` (glossary), AGENTS.md (worldgen layout line).
- No change to simops, the environment format, the bundle layout or the CLI.
