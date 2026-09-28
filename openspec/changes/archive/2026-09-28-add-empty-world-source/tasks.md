# Tasks

## 1. `src/worldgen/sdf.py`: the shared SDF envelope

- [x] 1.1 Move `gui_section()`, `model()` and `start_marker()` out of `src/worldgen/room.py` into
      a new `src/worldgen/sdf.py`; change `start_marker` to take `clearance` and compute its own
      radius (`clearance / 2 * 1.2`), so every caller passes the same thing. Add `world(name,
      parts) -> str`, the envelope (physics/sensor plugins, GUI, light, `ground_plane`) extracted
      out of `room.py`'s `world_sdf`.
- [x] 1.2 Update `room.py`'s `world_sdf` to build its own `parts` (walls, obstacles,
      `sdf.start_marker(clearance)`) and call `sdf.world("room", parts)`; drop the `walls` keyword
      `world_sdf`/`generate` had (no longer needed — see task 2); verify `pixi run test`
      (`tests/worldgen/test_room.py`) still passes unchanged.

## 2. `src/worldgen/empty.py`: the open field, independent of `room`

- [x] 2.1 Add `src/worldgen/empty.py`: `generate(out: Path, *, clearance: float) -> str` builds its
      own `parts` (`[sdf.start_marker(clearance)]`) and calls `sdf.world("field", parts)` directly
      — no import of `room`; returns its own summary ("open field, clearance ... m"). Add a
      `worldgen empty` command in `src/worldgen/cli.py`. Verify
      `tests/worldgen/test_empty.py::test_open_field` (`<world name="field">`, no `wall_*`/`obs_*`
      models, `start_marker` and `ground_plane` present) and `::test_cli`.

## 3. `empty_world` world source

- [x] 3.1 In `src/simops/world.py`: add `EmptySpec` (no fields, `extra="forbid"`), an
      `empty_world: EmptySpec | None = None` field on `World`, a `model_validator(mode="before")`
      turning a bare `empty_world:` (null) into `{}`, and extend the "exactly one source" check and
      error message to the three fields; verify `pixi run test`
      (`tests/simops/test_environment.py`) passes, including `empty_world` combined with another
      source and `empty_world: {size: [...]}` both failing to load.
- [x] 3.2 Extend `World.source` to return `self.empty_world` unchanged (no `RoomSpec` involved);
      verify `Environment.load(... world={"empty_world": None}).world.source == EmptySpec()`.
- [x] 3.3 In `src/simops/bundle.py`, add `elif isinstance(source, EmptySpec):` between the
      `WorldFile` and `RoomSpec` branches, calling
      `worldgen.empty.generate(sdf, clearance=first.width() * 1.1)`; verify with
      `tests/simops/test_bundle.py::test_empty_world_is_open` asserting the built SDF has
      `start_marker` and `ground_plane` but no `wall_*` or `obs_*` model.

## 4. Example and docs

- [x] 4.1 `environments/rover_empty_world.yaml` (added by the user): fix `name:` to match the file
      (it read `rover_room`) and the `world:` comment to describe the open field; verify
      `pixi run simops build environments/rover_empty_world.yaml` writes a world SDF with only
      `ground_plane` and `start_marker` — no walls, no obstacles.
- [x] 4.2 `openspec/config.yaml`: the "world source" glossary line names `empty_world`, and a new
      "open field" term under World generation names `worldgen.empty`; verify
      `openspec instructions proposal --change add-empty-world-source --json` shows the new
      wording.
