# Spec Delta

## MODIFIED Requirements

### Requirement: Firmware from the scenario
PX4 SHALL be built from `autopilot.px4.repo` (default: the upstream PX4-Autopilot repository),
the same firmware for every agent, chosen by one of:
- `version`: a release tag, written `v1.18.0` or `1.18.0`, pre-release suffixes included
  (`v1.18.0-rc1`);
- `commit`: a full 40-character commit SHA;
- neither: the default firmware.

`build` SHALL resolve the choice to one commit, and the PX4 image SHALL be tagged by that commit's
first 12 characters, so the same firmware reached by version or by commit is one image and
switching back to it needs no rebuild.

#### Scenario: Version resolves to its commit
- **WHEN** the scenario sets `version: v1.18.0-rc1`
- **THEN** PX4 runs from image `simops-sandbox-px4:<first 12 characters of the commit v1.18.0-rc1 points to>`

#### Scenario: Version without the v
- **WHEN** the scenario sets `version: 1.18.0-rc1`
- **THEN** it resolves exactly like `v1.18.0-rc1`

#### Scenario: Ref names the image
- **WHEN** the scenario sets `commit: 4dbd2e069a5c30c2e53e47e842095d2576dc38c4`
- **THEN** PX4 runs from image `simops-sandbox-px4:4dbd2e069a5c`

#### Scenario: Unknown version
- **WHEN** the scenario sets a `version` the repository has no tag for
- **THEN** `build` fails naming the version and the repository

#### Scenario: Short commit
- **WHEN** the scenario sets `commit` to fewer than 40 hex characters
- **THEN** loading fails asking for the full SHA

## ADDED Requirements

### Requirement: Default firmware
With neither `version` nor `commit`, simops SHALL use the newest release tag of PX4 1.18 or later
without a pre-release suffix, or, when none exists, the newest 1.18+ pre-release tag.

#### Scenario: No stable 1.18 yet
- **WHEN** the repository's newest 1.18+ tags are `v1.18.0-beta2` and `v1.18.0-rc1`, and no `v1.18.0`
- **THEN** the default firmware is `v1.18.0-rc1`

#### Scenario: Stable released
- **WHEN** the repository has `v1.18.0` and `v1.18.1-rc1`
- **THEN** the default firmware is `v1.18.0`

### Requirement: Supported PX4 versions
simops SHALL support PX4 1.18 and later, compared by major.minor: 1.18 pre-releases and commits
after them are supported. PX4 1.17 and earlier compile as C++14, which the gz Jetty toolchain
of this stack cannot build. A `version` below 1.18 SHALL fail `build` before any image is built;
a `commit` whose `git describe` version is below 1.18 SHALL fail the image build before PX4 is
compiled. Both messages SHALL name the version found and the 1.18 minimum.

#### Scenario: Old version
- **WHEN** the scenario sets `version: v1.17.0`
- **THEN** `build` fails naming 1.17.0 and the 1.18 minimum, and no image build starts

#### Scenario: Pre-release of 1.18
- **WHEN** the scenario sets `version: v1.18.0-rc1`
- **THEN** it is accepted

#### Scenario: Old commit
- **WHEN** the scenario sets a `commit` that `git describe` places before 1.18
- **THEN** the PX4 image build stops before compiling, naming that version and the 1.18 minimum

### Requirement: PX4 knows its version
The PX4 in the image SHALL report the version it was built from: the tag for a `version`, the
`git describe` of the commit for a `commit` — never `v0.0.0`.

#### Scenario: Built from a tag
- **WHEN** PX4 is built for `version: v1.18.0-rc1`
- **THEN** its build reports the tag `v1.18.0-rc1`

#### Scenario: Built from a commit
- **WHEN** PX4 is built for a `commit` after `v1.18.0-beta1`
- **THEN** its build reports a version starting with `v1.18.0-beta1-`
