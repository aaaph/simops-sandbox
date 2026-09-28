# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Firmware from the environment`
- TO: `### Requirement: Firmware from the platform`

## MODIFIED Requirements

### Requirement: One PX4 per agent
Every agent SHALL get its own PX4 SITL, attached to that agent in the world by its environment
name, running the airframe and the firmware from its platform's `agent.yaml`
(`autopilot.px4`). A platform whose `agent.yaml` has no `autopilot.px4.airframe` SHALL fail
loading the environment that uses it, naming that `agent.yaml`.

Known gap: every agent gets a PX4, so every platform needs a PX4 airframe.

#### Scenario: Airframe from the platform
- **WHEN** `rover1` uses `rover_differential_lidar_px4`, whose airframe is 50000
- **THEN** `px4-rover1` starts with airframe 50000 attached to model `rover1`

#### Scenario: Platform without an airframe
- **WHEN** an agent's platform `agent.yaml` has no `autopilot.px4.airframe`
- **THEN** loading the environment fails naming that `agent.yaml` and `autopilot.px4.airframe`

### Requirement: Firmware from the platform
A platform's `agent.yaml` SHALL name the PX4 firmware its airframe runs on, under
`autopilot.px4`: PX4 SHALL be built from `repo` (default: the upstream PX4-Autopilot repository),
chosen by one of:
- `version`: a release tag, written `v1.18.0` or `1.18.0`, pre-release suffixes included
  (`v1.18.0-rc1`);
- `commit`: a full 40-character commit SHA;
- neither: the default firmware.

Each agent's PX4 SHALL run the firmware of its platform; agents on platforms with different
firmware run different firmware. `build` SHALL resolve each firmware to one commit, and the PX4
image SHALL be tagged by that commit's first 12 characters, so the same firmware reached by
version or by commit, or named by several platforms, is one image and switching back to it
needs no rebuild. Unknown keys under `autopilot` SHALL fail loading, naming the key.

#### Scenario: Version resolves to its commit
- **WHEN** the platform sets `version: v1.18.0-rc1`
- **THEN** PX4 runs from image `simops-sandbox-px4:<first 12 characters of the commit v1.18.0-rc1 points to>`

#### Scenario: Version without the v
- **WHEN** the platform sets `version: 1.18.0-rc1`
- **THEN** it resolves exactly like `v1.18.0-rc1`

#### Scenario: Ref names the image
- **WHEN** the platform sets `commit: 4dbd2e069a5c30c2e53e47e842095d2576dc38c4`
- **THEN** PX4 runs from image `simops-sandbox-px4:4dbd2e069a5c`

#### Scenario: Unknown version
- **WHEN** the platform sets a `version` the repository has no tag for
- **THEN** `build` fails naming the version and the repository

#### Scenario: Short commit
- **WHEN** the platform sets `commit` to fewer than 40 hex characters
- **THEN** loading fails asking for the full SHA

#### Scenario: Old `ref` key
- **WHEN** the platform sets `autopilot.px4.ref`
- **THEN** loading fails with a message naming `version` and `commit`

#### Scenario: Both version and commit
- **WHEN** the platform sets both `autopilot.px4.version` and `autopilot.px4.commit`
- **THEN** loading fails, saying only one of them may be given

#### Scenario: Two platforms, two firmwares
- **WHEN** `rover1` and `rover2` use platforms whose `agent.yaml` name different versions
- **THEN** `px4-rover1` and `px4-rover2` run from the images of their own platform's firmware

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
of this stack cannot build. A `version` below 1.18 SHALL fail loading before any image is built;
a `commit` whose `git describe` version is below 1.18 SHALL fail the image build before PX4 is
compiled. Both messages SHALL name the version found and the 1.18 minimum.

#### Scenario: Old version
- **WHEN** the platform sets `version: v1.17.0`
- **THEN** loading fails naming 1.17.0 and the 1.18 minimum, and no image build starts

#### Scenario: Pre-release of 1.18
- **WHEN** the platform sets `version: v1.18.0-rc1`
- **THEN** it is accepted

#### Scenario: Old commit
- **WHEN** the platform sets a `commit` that `git describe` places before 1.18
- **THEN** the PX4 image build stops before compiling, naming that version and the 1.18 minimum
