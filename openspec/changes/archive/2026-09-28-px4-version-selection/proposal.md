# Proposal

## Why

A scenario can only pin PX4 by `ref` — in practice a bare commit — so nobody can say "PX4
v1.18.0", nothing picks a sensible release by default, and a commit-built PX4 reports its own
version as `v0.0.0` (the image's source clone carries no tags). Which PX4 versions can run at all
is also undocumented: checked by building them, v1.17.0 fails against the conda gz Jetty the
stack is built on (PX4 1.17 compiles as C++14, the Jetty env's abseil needs C++17), while
v1.18.0-rc1 builds and runs. A user asking for an older PX4 should hear that at `build`, not
after the compile fails.

## What Changes

- **BREAKING** `autopilot.px4.ref` is replaced by `version` (a PX4 release tag, `v1.18.0` or
  `1.18.0`) or `commit` (a commit SHA); giving both is an error; `ref` fails loading with a
  message naming the new keys.
- With neither, simops uses the newest PX4 release tag of 1.18 or later without a pre-release
  suffix, or, while none exists, the newest 1.18+ pre-release (today: `v1.18.0-rc1`).
- Supported PX4 is 1.18 and later (compared by major.minor, so 1.18 pre-releases and commits
  after them count). A `version` below that fails `build` before any image is built, saying why;
  a `commit` older than 1.18 fails the image build before PX4 is compiled.
- Every choice resolves at `build` to one commit; the PX4 image is tagged by that commit, so the
  same PX4 reached by version or by commit is one image.
- PX4 inside the image knows its version: built from a tag it reports that tag, built from a
  commit it reports `git describe` of that commit (e.g. `v1.18.0-beta1-660-g…`), never `v0.0.0`.
- `scenarios/rover_room.yaml` pins `version: v1.18.0-rc1`; AGENTS.md drops its outdated release
  notes ("no v1.17.0 yet") and records the 1.18 minimum and its reason.

Out of scope: a Harmonic stack (GUI over noVNC) for PX4 before 1.18 — the resolution from version
to stack leaves room for it; recording the resolved version in a bundle manifest
(`bundle-manifest-truth`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scenario`: the scenario file names PX4 by `version` or `commit` instead of `ref`, both optional.
- `autopilot`: firmware selection (version, commit, default), the 1.18 minimum, image per resolved
  commit, PX4 reporting its own version.

## Impact

- `sim/simops.py` (`load`, `compose`), `infra/px4.Dockerfile` (tags for commit builds, early
  version check), `scenarios/rover_room.yaml`, `sim/tests/`, AGENTS.md.
- `build` needs network access to the PX4 repository to resolve a version or the default
  (`git ls-remote`, ~1 s); a `commit` resolves offline.
- Existing images are tagged by commit already; the `v1.18.0-rc1` image built while exploring
  gets its commit tag instead of a rebuild.
