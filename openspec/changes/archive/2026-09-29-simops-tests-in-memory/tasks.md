# Tasks

The unit suite (`pixi run test`, no Docker, no network, no autopilot build) must pass after every
group.

## 1. Baseline

- [x] 1.1 Before touching the code, build both environments in `environments/` with the current code (`pixi run simops build environments/rover_room.yaml` and `.../rover_empty_world.yaml`; network: they resolve the PX4 firmware), copy each `build/<name>/` tree and the command's stdout into the scratchpad, and remove the `build/<name>/` directories this created (leave any that were there before); verify the copies and stdout files exist

## 2. Loading in memory

- [x] 2.1 `Environment.parse(data, *, base, origin)` with the checks and messages of today's `load`; `load(path)` reads the file and calls it (an unreadable file still raises `InvalidEnvironment` naming it); verify `pixi run test`
- [x] 2.2 `Platform.parse(dir, data)` validates the `agent.yaml` document, messages starting with `<dir>/agent.yaml`; `load(dir)` checks the three files and calls it; verify `pixi run test`
- [x] 2.3 `tests/simops/conftest.py`: in-memory fixtures `environment(name, **keys) -> Environment` and `platform(**px4) -> Platform` per design.md; the file-writing ones renamed `environment_file` and `platform_dir`; move `test_environment.py`, `test_platform.py`, `test_session.py` onto the in-memory fixtures, keeping files only for paths relative to the environment file, the `file` world source, an unreadable environment file and an invalid `agent.yaml` read through an environment; verify `pixi run test` and that `grep -n "tmp_path\|environment_file\|platform_dir" tests/simops/test_{environment,platform,session}.py` lists only those tests

## 3. The bundle in memory

- [x] 3.1 worldgen: `room.summary(world, *, clearance, seed, size, obstacles)` and `empty.summary(*, clearance)` return the text `generate` prints after `out: `, and `generate` uses them; verify `pixi run test` and that `worldgen room -o <scratch>/r.sdf --clearance 0.9 --seed 7 --size 12 9` prints the same line as before the change apart from the path
- [x] 3.2 `src/simops/bundle.py`: `build(environment) -> Bundle` computes the fields of design.md and writes nothing; `Bundle.write(dir) -> Path` writes the bundle and prints the world and PX4 lines in today's order; `Bundle.dir` removed; `cli.build_cmd` and `Session.up` write to `build/<name>/`; verify `pixi run test`, then build both environments again and `diff -r` each tree against the baseline of 1.1 (no difference) and compare stdout (identical), and remove the `build/<name>/` directories this created
- [x] 3.3 `tests/simops/test_bundle.py` on `build(environment(...))` in memory — compose wiring, spawn script, merged bridge, namespaced models (`ET.fromstring(bundle.models[...])`), firmware and images, the open field, same seed same world, a nameless `file` world exits naming the source file — keeping on disk only the rover_room bundle's files (platforms and borrowed meshes copied, `worlds/`, `spawn.sh`) and "rebuild drops stale files"; verify `pixi run test` and that `grep -n "\.write(\|tmp_path\|environment_file" tests/simops/test_bundle.py` lists only those tests and the nameless-world input

## 4. Language and docs

- [x] 4.1 `openspec/config.yaml` glossary: bundle is built in memory by `build` and written to `build/<name>/` by `Bundle.write`; AGENTS.md: the note on simops calling worldgen names `room.world` (and `summary`), not `generate`; verify `grep -n "room.generate" AGENTS.md` finds nothing and `openspec validate simops-tests-in-memory --strict` passes

## 5. Integration

- [x] 5.1 Run `pixi run format`, `pixi run lint`, `pixi run test`; all pass, and no `build/<name>/` is left that was not there before
- [x] 5.2 Docker test: `pixi run pytest -m docker` on the images that exist (`simops-sandbox-{ros,world}`, `simops-sandbox-px4:fca3df865af3`; if one is missing, build it first with `docker compose -f build/rover_room/compose.yaml build`, as its own step); all pass, and no `t_*` container or bundle is left
