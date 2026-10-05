# Tasks

## 1. The platform document

- [x] 1.1 In `src/simops/platform.py`, make `Platform` hold values: `model: Path`,
  `bridge: list[dict]`, `px4`; `name` becomes `model.parent.name`; drop `dir` and the `bridge`
  path property; `width()` unchanged. A `PlatformDocument` pydantic model (`extra="forbid"`:
  `model`, `bridge` (a list) and `autopilot` required) replaces `AgentFile`.
  Verify: `pixi run pytest tests/simops/test_platform.py` after 1.3.
- [x] 1.2 Add `resolve(document, here, chain)` and a merge-patch function (RFC 7386, stdlib) in
  `platform.py`: `base` resolved first through `<base>/platform.yaml` (cycle → `ValueError` naming
  the chain), own `model`/`bridge` file/`base` made absolute against `here`, a `bridge` file read
  into its list, then merged over the base. `Platform.parse(document, *, here, origin)` resolves
  and validates once, errors prefixed with `origin` and the bases' `platform.yaml` (see design);
  `Platform.load(dir)` reads `<dir>/platform.yaml`, or fails naming a missing `platform.yaml` and,
  when `agent.yaml` is there, saying it is now `platform.yaml` with `model: model.sdf`, `bridge:
  bridge.yaml`. Verify: the tests in 1.3.
- [x] 1.3 Rewrite `tests/simops/test_platform.py` and the `platform` fixture in
  `tests/simops/conftest.py` around `Platform.parse` with inline documents (in memory): the
  existing rejected/accepted autopilot cases (message now starting with the origin given); bridge
  as list vs as the rover's `bridge.yaml` give equal entries; no `bridge` after merge fails naming it; unknown key
  `brige`; no `model` after merge; `base` + `autopilot.px4.version` override keeps model, bridge,
  airframe; `bridge` replaced, and `bridge: null` fails naming `bridge`; base path stays relative to the base
  ("Model from the base"); invalid value from a base names the base's `platform.yaml`. Cases that
  need files on disk (base of a base, cycle, old `agent.yaml`, missing `platform.yaml`) use
  `tmp_path` platforms and are marked `generating_files`. Verify: `pixi run pytest
  tests/simops/test_platform.py --durations=5` passes, no unit test over ~50 ms.
- [x] 1.4 Migrate `platforms/rover_differential_lidar_px4`: `agent.yaml` → `platform.yaml` with
  `model: model.sdf`, `bridge: bridge.yaml` and the same `autopilot` (comments kept); the
  `platform_dir` fixture writes `platform.yaml` (model/bridge pointing at the PX4 platform's
  files, so no symlinks are needed for them). Verify: `pixi run test` passes and
  `pixi run simops build environments/rover_room.yaml` succeeds (it resolves PX4 tags: network).

## 2. Agents take a directory or an inline platform

- [x] 2.1 In `src/simops/agent.py`, `_platform_dir` takes a path (→ `Platform.load`) or a mapping
  (→ `Platform.parse(mapping, here=<environment dir>, origin=None)`); the environment's top-level
  `autopilot` message in `environment.py` names `autopilot.px4` in the platform's `platform.yaml`
  or inline. Verify: tests in 2.2.
- [x] 2.2 In `tests/simops/test_environment.py` (the `environment` fixture, in memory): an inline
  platform with `model: ../../../platforms/rover_differential_lidar_px4/model.sdf` resolves against
  the environment's directory; inline unknown key `brige` names the agent; inline invalid
  `version: v1.17.0` names the environment file, the agent, 1.17.0 and the minimum; a directory
  agent and an inline agent with `base` load side by side with `namespaces: true`;
  `test_invalid_agent_yaml` becomes the old-`agent.yaml` message and an invalid `platform.yaml`
  (`generating_files`, via `platform_dir`); the `autopilot` moved-key case expects
  `platform.yaml`. Verify: `pixi run pytest tests/simops/test_environment.py` passes.

## 3. The bundle

- [x] 3.1 In `src/simops/bundle.py`: entries come from `spec.platform.bridge`, copied per agent
  before namespacing rewrites them (still each entry once, `/clock` unprefixed); `platforms` maps each model's directory name to `model.parent` (borrowed
  models: `model.parent.parent / <name>`), failing the build when two different directories share
  a name; `spawn.sh` and namespaced copies use the model's own file name. Verify: tests in 3.2 and 3.3.
- [x] 3.2 Three forms, one bundle ("Three forms, one bundle"): test environments
  `tests/simops/environments/rover_platform_{dir,inline,base}.yaml`, all `name: rover_platform`,
  an open field and one `rover1`, whose platform is `../../../platforms/rover_differential_lidar_px4`,
  that platform written out key by key (`model` path, the bridge entries as a list, `autopilot`
  with airframe and version), and `{base: ../../../platforms/rover_differential_lidar_px4}`. A test in
  `tests/simops/test_bundle.py` loads the three (`Environment.load`, reading only) and asserts
  `bundle.build` of each is equal to the directory one — the whole `Bundle`, so compose, spawn,
  bridge, platforms and models at once; `Bundle.write` is a function of it, so equal bundles write
  equal directories and no files are written (`no_network`). Verify: break the inline file on
  purpose (drop one bridge entry) and see the test fail naming the difference, then restore;
  `pixi run pytest tests/simops/test_bundle.py -k forms` passes.
- [x] 3.3 In `tests/simops/test_bundle.py` (in memory, `bundle.build`): two namespaced agents on one platform get each their own rewritten entries and
  `/clock` once, the platform's entries untouched; an inline model named
  `husky.sdf` in its own directory is spawned from `platforms/<dir>/husky.sdf` (model file in
  `tmp_path`, `generating_files`); two model directories with one name fail naming both;
  `rover1` on the directory and `rover11` with `base` + `version: v1.18.0` get PX4 images of
  their own firmware with airframe 50000 (`no_network`). Verify: `pixi run pytest
  tests/simops/test_bundle.py --durations=5` passes.

## 4. Docs and glossary

- [x] 4.1 `AGENTS.md`: the platform paragraph (`platform.yaml`: `model`, `bridge`, `autopilot`,
  `base`; inline platforms; the model's directory is the model), the PX4 version paragraph
  (`autopilot.px4` of the platform), and the
  "Done" list. `openspec/config.yaml` glossary: `platform` (a platform document in
  `platforms/<p>/platform.yaml` or inline; spec: platform), new entries `inline platform` and
  `base platform`, `PX4 firmware` named in the platform's `autopilot.px4`. Comments in
  `environments/*.yaml` that name `agent.yaml`. Verify: `grep -rn "agent\.yaml" AGENTS.md
  openspec/config.yaml environments src` finds only the old-`agent.yaml` message;
  `openspec validate platform-inline-and-base --strict` passes.

## 5. Integration

- [x] 5.1 Checks and a session. Verify: `pixi run lint` and `pixi run test` pass; an environment
  in `tmp_path` with `namespaces: true`, `rover1` on the directory and `rover11` inline with
  `base` and a different pose comes `up` (Docker, existing images), `ros2 topic list` through
  `simops host-env` shows `/clock` once and `/rover1/scan`, `/rover11/scan`; `simops down`
  leaves no container of it.
