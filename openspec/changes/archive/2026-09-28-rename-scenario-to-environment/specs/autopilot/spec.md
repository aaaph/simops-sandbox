# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Firmware from the scenario`
- TO: `### Requirement: Firmware from the environment`

## MODIFIED Requirements

### Requirement: One PX4 per agent
Every agent SHALL get its own PX4 SITL, attached to that agent in the world by its environment name,
running the airframe from its platform's `agent.yaml` (`autopilot.px4.airframe`).

Known gap: every agent gets a PX4, so every platform needs a PX4 airframe.

#### Scenario: Airframe from the platform
- **WHEN** `rover1` uses `rover_differential_lidar_px4`, whose airframe is 50000
- **THEN** `px4-rover1` starts with airframe 50000 attached to model `rover1`

### Requirement: Firmware from the environment
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
- **WHEN** the environment sets `version: v1.18.0-rc1`
- **THEN** PX4 runs from image `simops-sandbox-px4:<first 12 characters of the commit v1.18.0-rc1 points to>`

#### Scenario: Version without the v
- **WHEN** the environment sets `version: 1.18.0-rc1`
- **THEN** it resolves exactly like `v1.18.0-rc1`

#### Scenario: Ref names the image
- **WHEN** the environment sets `commit: 4dbd2e069a5c30c2e53e47e842095d2576dc38c4`
- **THEN** PX4 runs from image `simops-sandbox-px4:4dbd2e069a5c`

#### Scenario: Unknown version
- **WHEN** the environment sets a `version` the repository has no tag for
- **THEN** `build` fails naming the version and the repository

#### Scenario: Short commit
- **WHEN** the environment sets `commit` to fewer than 40 hex characters
- **THEN** loading fails asking for the full SHA

### Requirement: Distinct instances
Agents SHALL get distinct PX4 instance numbers `0..N-1` in environment order, so PX4s sharing one
network namespace do not collide on their ports.

#### Scenario: Second agent
- **WHEN** an environment has agents `rover1` and `rover2`
- **THEN** `px4-rover1` runs as instance 0 and `px4-rover2` as instance 1

### Requirement: Supported PX4 versions
simops SHALL support PX4 1.18 and later, compared by major.minor: 1.18 pre-releases and commits
after them are supported. PX4 1.17 and earlier compile as C++14, which the gz Jetty toolchain
of this stack cannot build. A `version` below 1.18 SHALL fail `build` before any image is built;
a `commit` whose `git describe` version is below 1.18 SHALL fail the image build before PX4 is
compiled. Both messages SHALL name the version found and the 1.18 minimum.

#### Scenario: Old version
- **WHEN** the environment sets `version: v1.17.0`
- **THEN** `build` fails naming 1.17.0 and the 1.18 minimum, and no image build starts

#### Scenario: Pre-release of 1.18
- **WHEN** the environment sets `version: v1.18.0-rc1`
- **THEN** it is accepted

#### Scenario: Old commit
- **WHEN** the environment sets a `commit` that `git describe` places before 1.18
- **THEN** the PX4 image build stops before compiling, naming that version and the 1.18 minimum
