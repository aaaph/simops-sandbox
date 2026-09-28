# Design

## Context

See proposal.md — Why. Today `compose()` passes `autopilot.px4.ref` straight into the PX4 image
build (`PX4_REF`, `ADD <repo>#<ref>`) and tags the image `ref[:12]`. `load()` runs for every
command, including `down`, `env` and `gui`, which must keep working offline and fast.

Checked while exploring (2026-09-27/28): v1.17.0 fails to compile (`CMAKE_CXX_STANDARD 14`
against the conda Jetty env's abseil, which requires C++17); v1.18.0-rc1 (C++17) builds and runs
(`simops up`, 22 `/fmu/out/*` topics on the host). `ADD <repo>#<tag>` brings the tag along, so a
tag build reports it; a commit build has no tags and reports `v0.0.0`.
`git ls-remote --tags` on the PX4 repository answers in ~0.6 s.

## Goals / Non-Goals

**Goals:** see the specs. **Non-Goals:** a second (Harmonic) stack; a manifest; caching tag lists.

## Decisions

### Validate in `load`, resolve in `build`
`load` checks the keys only (`ref` gone, not both `version` and `commit`, `commit` is 40 hex
characters, `version` parses as `vX.Y.Z[-suffix]` with X.Y ≥ 1.18) — offline, so `down`, `env`
and `gui` never touch the network. `build` resolves to a commit (network for `version` and the
default) and hands `compose` the resolved firmware: the ref to build from (the tag name, or the
commit) and the commit for the image tag. `commit` needs no network.
*Alternative:* resolve in `load` — rejected, `down` would fail offline.

### Tags from `git ls-remote --tags <repo>`
One call lists every tag with its commit; for annotated tags the peeled `^{}` line is the commit.
A pure function turns that text into `{version: commit}`, so unit tests feed it fixed text and
never reach the network; `ls_remote(repo)` is the only function that runs git, and tests
monkeypatch it. Works for forks (`repo`) and needs no GitHub API or token.
*Alternative:* GitHub API — rejected: GitHub-only, rate-limited without a token.

### Version order
`vMAJOR.MINOR.PATCH[-(alpha|beta|rc)N]`, compared as `(major, minor, patch, stage, n)` with
stage alpha < beta < rc < release. Tags that do not match (e.g. `v1.18.0-beta1-foo`) are ignored.
Support check uses `(major, minor) >= (1, 18)`, so `v1.18.0-rc1` passes while plain semver would
put it below 1.18.0.

### Commit builds learn their version inside the image
After the source is copied into the pixi stage (which has git), a step fetches tags when
`git describe --tags` finds none, then checks `describe`'s major.minor ≥ 1.18 and fails the build
with the found version and the minimum — before the Python requirements and the ~10 min compile.
The same check runs for tag builds and passes at once. PX4's own build then runs `git describe`
and reports the real version.
*Alternative:* resolve a commit's version on the host — needs the PX4 history on the host (a
clone), too heavy for `build`.

### Image tag: resolved commit
`simops-sandbox-px4:<commit[:12]>` for every choice; build args `PX4_REF=<tag or commit>`. The
v1.18.0-rc1 image built while exploring is retagged to its commit (`fca3df865af3`) instead of
rebuilt.

## Risks / Trade-offs

- [PX4 layout differs between 1.18 builds: the board root path is `.` in v1.18.0-rc1 and `./fs`
  on main since #28582, which moves the zenoh topic lists] → `sim-px4` reads
  `CONFIG_BOARD_ROOT_PATH` from the built `boardconfig` (found during apply).
- [`build`/`up` of a scenario with `version` or the default fails offline] → the error names the
  repository and says a `commit` builds offline.
- [The default moves when PX4 tags a release] → intended; the resolved commit is printed by
  `build`, and a scenario that must not move pins `version` or `commit` (rover_room does).
- [Fetching tags in a commit build pulls history into the image layer] → one-off per commit
  image; fetched with `--filter=tree:0` to skip trees and blobs.
- [Tag naming changes upstream] → unmatched tags are ignored; an explicit `commit` always works.

## Migration Plan

`rover_room.yaml` moves from `ref: 4dbd…` to `version: v1.18.0-rc1`. The old `4dbd2e069a5c`
image stays until the user removes it. No other scenarios exist.
