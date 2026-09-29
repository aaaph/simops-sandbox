# Tasks

The unit suite (`pixi run test`, no Docker, no network, no autopilot build) must pass after every
group.

## 1. Baseline

- [x] 1.1 Before touching the code, write reference worlds from the current generator into the scratchpad: `worldgen room -o <scratch>/before_room.sdf --clearance 0.9 --seed 7 --size 12 9` and `worldgen empty -o <scratch>/before_empty.sdf --clearance 0.9`; verify both files exist

## 2. Parts of an SDF world

- [x] 2.1 `src/worldgen/sdf.py`: keep the envelope (renamed `envelope(name, models)`), `model(...)` and `gui_section()`; move `start_marker` out; verify `pixi run lint`
- [x] 2.2 `src/worldgen/world.py`: `Shape` (`StrEnum`: `BOX`, `CYLINDER`), `Obstacle`, `Wall` with `Wall.from_ab`, `StartMarker`, `SdfWorld(name, parts).sdf()` as frozen dataclasses, per design.md; `tests/worldgen/test_world.py`: `from_ab` from (0, 0) to (0, 4) gives centre (0, 2), length 4.15, yaw pi/2, and a horizontal segment gives yaw 0; every `Shape` is inscribed in its disc (box half-diagonal == radius, default aspect square); `replace(o, shape=Shape.BOX)` keeps `x, y, radius`; verify `pixi run test`

## 3. World types on the parts

- [x] 3.1 `src/worldgen/room.py`: `place_obstacles` returns `Obstacle`s (rng drawn as today), `unreachable_cells` takes them, `shape_boxes(rng, obstacles)` draws the box aspects in order, `room_walls(size)` gives the four walls via `Wall.from_ab` between the corners, `generate` assembles `SdfWorld("room", ...)`; no XML left in the module; update `tests/worldgen/test_room.py` to build `Obstacle`s and add "room walls are joined with no gap" (points sampled over the whole 0.15-wide frame around the 10 x 8 rectangle, the four outer corner squares included, each lie inside some wall's rotated box; the test fails if `from_ab` drops the end caps); verify `pixi run test` and `grep -n '<' src/worldgen/room.py` finds no XML
- [x] 3.2 `src/worldgen/empty.py`: `generate` is `SdfWorld("field", [StartMarker(clearance)])`; verify `pixi run test`
- [x] 3.3 Compare against the baseline: regenerate both worlds as in 1.1; the `obs_*` and `start_marker` `<model>` blocks of the room, and the whole open field, are byte-identical to `before_*.sdf`; the room's wall models differ only as design.md says (north/south yaw 0 or pi, east/west turned by pi/2 and 0.15 longer); verify by a throwaway diff in the scratchpad, and `simops build environments/rover_room.yaml` succeeds (network: it resolves the PX4 firmware)

## 4. Language and docs

- [x] 4.1 `openspec/config.yaml` glossary, world generation: add wall (a segment with square end caps), obstacle with its shape (box or cylinder inscribed in its footprint disc), start marker, SDF world (what worldgen produces; simops' world source is a different thing), each pointing to "Spec: worldgen"; verify `openspec instructions proposal --change worldgen-entities --json` shows them
- [x] 4.2 AGENTS.md: the layout line becomes `src/worldgen/` (`world`: the parts of an SDF world, `room`, `empty`: the world types, `worldgen room --help`); verify `openspec validate worldgen-entities --strict`

## 5. Worlds in memory

- [x] 5.1 `room.world(...)` and `empty.world(...)` return an `SdfWorld` without touching a file; `generate(out, ...)` writes it and returns the summary, signatures unchanged; verify `simops build environments/rover_room.yaml` gives the same `worlds/room.sdf` as before this group (network: it resolves the PX4 firmware)
- [x] 5.2 `tests/worldgen/`: unit tests on `SdfWorld`s in memory (same seed equal worlds, different seed not; open field parts are only the start marker; a room's parts are four walls, obstacles and the start marker; one test that the rendered envelope names the world and holds no `<include>`); `tmp_path` only in the two CLI tests; verify `pixi run test` and `grep -c tmp_path tests/worldgen/*.py` counts only the CLI tests

## 6. Integration

- [x] 6.1 Run `pixi run format`, `pixi run lint`, `pixi run test`; all pass
