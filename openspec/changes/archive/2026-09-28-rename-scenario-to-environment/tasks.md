# Tasks

Behavior does not change apart from the `host-env` command name: `pixi run test` and
`pixi run pytest -m docker` must pass after each group. OpenSpec's own files under `.agents/` and
`.claude/` are not touched.

## 1. Files and code

- [x] 1.1 Move `scenarios/` to `environments/` (git mv); reword the header comment of `environments/rover_room.yaml`; verify `pixi run simops build environments/rover_room.yaml` builds `build/rover_room/`
- [x] 1.2 In `sim/simops.py`: the CLI argument and its help (`environment`, "environment YAML file"), messages, docstrings and module docstring examples (`environments/rover_room.yaml`), the type alias `Environment`, the loaded dict named `environment`; "session" where a message means the running thing; the `env` command renamed `host-env`; verify `grep -in 'scenario\|blueprint' sim/simops.py` finds nothing, `pixi run simops --help` lists `host-env` and no `env`, and `pixi run test`
- [x] 1.3 In `sim/tests/` (`test_simops.py`, `test_simops_docker.py`, `conftest.py`): `ENVIRONMENT`, the Docker helper `environment()`, paths and docstrings; verify `grep -rin 'scenario\|blueprint' sim/tests` finds nothing, `pixi run test` and `pixi run pytest -m docker`

## 2. Docs and config

- [x] 2.1 AGENTS.md: section title, text and commands say environment (file) / bundle / session (running), with the vocabulary line and "scenario" reserved for a future action layer, `simops host-env` in the command list; comments in `pixi.toml`, `pytest.ini`, `readme.md`, `platforms/rover_differential_lidar_px4/agent.yaml`; verify every command AGENTS.md shows uses `environments/` and `host-env`, and `git grep -in 'scenario\|blueprint' -- AGENTS.md pixi.toml pytest.ini readme.md platforms` finds only the reserved-word line
- [x] 2.2 Reword the open proposals `session-isolation` and `bundle-manifest-truth` (scenario → environment / session); verify `grep -in 'scenario\|blueprint' openspec/changes/{session-isolation,bundle-manifest-truth}/proposal.md` finds nothing (both are proposal-only, so `openspec validate` cannot pass for them yet)

## 3. Specs

- [x] 3.1 Reword the Purpose sections that say "scenario" in `openspec/specs/{autopilot,bundle,host-access,sim-lifecycle}/spec.md` (the `scenario` spec is retired by this change); verify `openspec validate --specs --strict`

## 4. Integration

- [x] 4.1 Run `pixi run format`, `pixi run test`, `pixi run pytest -m docker`; all pass
