# Tasks

## 1. Version parsing and tag resolution (unit, no network)

- [x] 1.1 In `sim/simops.py`, add version parsing (`v1.18.0`, `1.18.0`, `-alpha|beta|rcN`) and ordering, the ≥ 1.18 support check by major.minor, and a pure function turning `git ls-remote --tags` output into `{version: commit}` (peeled `^{}` lines win); unit tests with fixed ls-remote text cover: ordering alpha < beta < rc < release, `1.18.0` = `v1.18.0`, annotated vs lightweight tags, unmatched tags ignored; verify `pixi run test`
- [x] 1.2 Add the default rule (newest 1.18+ release, else newest 1.18+ pre-release) with unit tests for both scenarios of the "Default firmware" requirement; verify `pixi run test`

## 2. Scenario keys

- [x] 2.1 In `load`, replace `ref` with optional `version` / `commit`: `ref` fails naming both new keys, both given fails, `commit` must be 40 hex characters, `version` below 1.18 fails naming the version and the minimum — all offline; unit tests for each; verify `pixi run test`
- [x] 2.2 In `build`, resolve the firmware (`ls_remote(repo)` for `version` and the default, nothing for `commit`), print the resolved version and commit, fail naming version and repository when the tag is unknown or the repository unreachable; `compose` gets `PX4_REF` = tag or commit and image `simops-sandbox-px4:<commit[:12]>`; unit tests monkeypatch `ls_remote` (version, `1.18.0` spelling, unknown version, commit without network); verify `pixi run test` passes with the network off for the unit suite

## 3. PX4 image

- [x] 3.1 In `infra/px4.Dockerfile`, after copying the source into the pixi stage: fetch tags with `--filter=tree:0` when `git describe --tags` finds none, then fail with the found version and the 1.18 minimum when major.minor < 1.18, before installing PX4's Python requirements; verify a build for `version: v1.18.0-rc1` reports `PX4_GIT_TAG_STR "v1.18.0-rc1"` and a build for commit `4dbd2e069a5c30c2e53e47e842095d2576dc38c4` reports a tag starting with `v1.18.0-beta1-` (not `v0.0.0`)
- [x] 3.2 Verify the early failure: a build of a pre-1.18 commit (e.g. `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`, v1.17.0) through `docker build ... --build-arg PX4_REF=<sha>` stops at the version check, naming 1.17 and the minimum, before `pip install`; record the time it took in this task — 2026-09-28: stopped at the check with "PX4 v1.17.0 is not supported, the minimum is 1.18 ..."; 225 s cloning the source + 169 s fetching history for describe, no pip, no compile

## 4. Scenario, images, docs

- [x] 4.1 `scenarios/rover_room.yaml`: `version: v1.18.0-rc1` with its px4_msgs note; retag the existing `simops-sandbox-px4:v1.18.0-rc1` image to its commit tag (`fca3df865af3`) and remove the `v1.18.0-rc1` tag; verify `pixi run simops build scenarios/rover_room.yaml` prints v1.18.0-rc1 and its commit, and `docker compose -f build/rover_room/compose.yaml config --images` names an image that exists
- [x] 4.2 Update the unit and Docker tests that assumed `ref` (Docker tests use `version: v1.18.0-rc1`); verify `pixi run test` and `pixi run pytest -m docker` — found on the way: namespaces failed on rc1, whose board root path is `.` (main: `./fs`, since #28582), so `sim-px4` wrote `pub.csv` where rc1 does not look; it now reads `CONFIG_BOARD_ROOT_PATH` from the build's `boardconfig`; all 7 Docker tests pass on rc1
- [x] 4.3 AGENTS.md: replace the outdated release notes ("no v1.17.0 tag yet", "pinned commit is main with #28843") with the `version`/`commit`/default rule, the 1.18 minimum and its reason (C++14 vs the Jetty env's abseil), and the future Harmonic stack for older PX4; verify `git grep -n 'v1.17.0-rc2\|#28843' AGENTS.md` finds nothing

## 5. Integration

- [x] 5.1 Run `pixi run format`, `pixi run test`, `pixi run pytest -m docker`; all pass
- [x] 5.2 Manually: `simops up` + `gui` on rover_room with v1.18.0-rc1, drive with the QGC joystick; record the result in this task — 2026-09-28: rover_room on v1.18.0-rc1 up and in the GUI; reported working by the user
