# Tasks

## 1. Dependency and marker

- [x] 1.1 Keep `mavsdk-grpc = ">=3.17.4, <4"` in `[pypi-dependencies]` of `pixi.toml` with a
  one-line comment (MAVSDK-Python 3.x API, imported as `mavsdk_grpc`; 4.x needs macOS 15), and its
  entries in `pixi.lock` (already added by hand). Verify: `pixi install` is a no-op and
  `pixi run python -c "from mavsdk_grpc import System"` succeeds.
- [x] 1.2 Add the marker `scenario: runs a scenario in a session (marked docker too)` to
  `pytest.ini`, leaving `addopts` as it is. Verify: `pixi run pytest --markers | grep scenario`
  lists it and `pixi run test` deselects the same tests as before plus the new one.
- [x] 1.3 Document the test kinds: `AGENTS.md` (beside `-m docker`: `-m scenario`, `-m "docker and
  not scenario"`, and that a scenario test is marked both), the `scenario` glossary entry and the
  test conventions in `openspec/config.yaml` (a scenario test is a Docker test marked `scenario`
  too). Verify: `pixi run lint` and `openspec validate square-mission-scenario --strict` pass.

## 2. The square scenario

- [x] 2.1 Write `tests/simops/test_square_scenario.py` (`pytestmark = [docker, scenario]`): an
  open-field environment (`world: {empty_world: }`) written to `tmp_path` (name `t_square`, router
  port 7480, MAVLink port 14800, `rover1` at the origin), `Session.up`, then under `asyncio.run`: MAVSDK `System()`
  connected to `udpin://0.0.0.0:14800` (connect itself bounded too), bounded waits for the connection and for health
  (global position, home, armable), home from telemetry, four `MissionItem`s by keyword for a 5 m
  square (north, north-east, east, home; altitude 0, speed and acceptance radius `nan`), upload,
  arm, start, bounded wait until `mission_progress` reaches the total and `is_mission_finished()`,
  disarm; `Session.down` in `finally`. Verify: `pixi run pytest -m scenario` passes on existing
  images (Docker), and `docker ps` shows no `t_square` container afterwards.
- [x] 2.2 Check the selections. Verify: `pixi run pytest -m "docker and not scenario" --collect-only -q`
  lists the lifecycle tests without the square, and `pixi run pytest -m scenario --collect-only -q`
  lists only the square (no containers started).
- [x] 2.3 `scenarios/square_mission.py`: the same square as a script run by hand against a session
  that is up (`--port`, default 14540; `--side`, default 5), in the style of PX4's MAVSDK examples,
  independent of the test (the test does not import it); `T201` allowed for `scenarios/*.py` in
  `ruff.toml`; `AGENTS.md` names the folder and how to run it. Verify: `pixi run simops up
  environments/rover_empty_world.yaml`, `pixi run python scenarios/square_mission.py` reaches 4/4
  and disarms, `pixi run simops down`.
