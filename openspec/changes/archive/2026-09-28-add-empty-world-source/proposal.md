# Proposal

## Why

The only ready-to-use example, `environments/rover_room.yaml`, is a walled room scattered with
obstacles. Getting an agent moving and checking its start pose is easier with nothing to run
into at all — not even walls — before ever touching obstacle avoidance.

## What Changes

- A third world source, `empty_world`: an open field — no walls, no obstacles, just the ground
  and the red start marker. No fields at all: there is nothing to size, seed or count once there
  is nothing to bound.
- The SDF envelope every world type shares (physics/sensor plugins, GUI, light, `ground_plane`)
  moves out of `room.py` into a new `src/worldgen/sdf.py`; `room.py` and a new `src/worldgen/empty.py`
  each build their own parts and call it, independently of each other. See design.md.
- `worldgen empty`, a new CLI command next to `worldgen room`, generates an open field standalone.
- `empty_world` is its own type (`EmptySpec`) end to end: `World.source` returns it as-is, and
  `src/simops/bundle.py` gets a third branch calling `worldgen.empty.generate(...)` directly — it
  is not folded into `RoomSpec`.
- Add `environments/rover_empty_world.yaml`, the same shape as `rover_room.yaml` but with
  `empty_world:`.
- `openspec/config.yaml`'s glossary entry for "world source" lists the third option.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `environment`: "Exactly one world source" now allows `generate_room`, `file` or `empty_world`.

## Impact

- `src/worldgen/sdf.py` (new file): `world(name, parts)`, `model()`, `start_marker()`,
  `gui_section()` — moved out of `room.py`, shared by every world type.
- `src/worldgen/room.py`: builds its own `parts` (walls, obstacles, marker) and calls
  `sdf.world("room", parts)`; otherwise unchanged behavior.
- `src/worldgen/empty.py` (new file): `generate(out, *, clearance)`, builds its own `parts` (just
  a marker) and calls `sdf.world("room", parts)` — does not import `room`.
- `src/worldgen/cli.py`: a new `worldgen empty` command.
- `src/simops/world.py`: new `EmptySpec` (no fields), a third field on `World`, the "exactly one"
  check and `source` extended.
- `src/simops/bundle.py`: a third `isinstance(source, EmptySpec)` branch alongside `WorldFile` and
  the `RoomSpec` fallback, calling `worldgen.empty.generate`.
- `tests/worldgen/test_empty.py` (new file), `tests/simops/test_environment.py`,
  `tests/simops/test_bundle.py`: `empty_world` / open-field coverage.
- `environments/rover_empty_world.yaml` (added by the user during apply; this change fixes its
  `name:` and comment).
- `openspec/config.yaml`: the "world source" glossary line, and a new "open field" glossary term.
