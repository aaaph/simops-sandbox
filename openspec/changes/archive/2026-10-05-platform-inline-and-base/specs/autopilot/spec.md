## MODIFIED Requirements

### Requirement: One PX4 per agent
Every agent SHALL get its own PX4 SITL, attached to that agent in the world by its environment
name, running the airframe and the firmware from its platform's `autopilot.px4` (see
`platform`). A platform without `autopilot.px4.airframe` SHALL fail loading the environment that
uses it, naming where the platform is written.

Known gap: every agent gets a PX4, so every platform needs a PX4 airframe.

#### Scenario: Airframe from the platform
- **WHEN** `rover1` uses `rover_differential_lidar_px4`, whose airframe is 50000
- **THEN** `px4-rover1` starts with airframe 50000 attached to model `rover1`

#### Scenario: Platform without an airframe
- **WHEN** an agent's platform `platform.yaml` has no `autopilot.px4.airframe`
- **THEN** loading the environment fails naming that `platform.yaml` and `autopilot.px4.airframe`

#### Scenario: Airframe from an inline platform
- **WHEN** `rover1`'s inline platform sets `autopilot: {px4: {airframe: 4001}}`
- **THEN** `px4-rover1` starts with airframe 4001

### Requirement: Firmware from the platform
A platform's `autopilot.px4` SHALL name the PX4 firmware its airframe runs on: PX4 SHALL be built
from `repo` (default: the upstream PX4-Autopilot repository), chosen by one of:
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
- **WHEN** `rover1` and `rover2` use platforms whose `autopilot.px4` name different versions
- **THEN** `px4-rover1` and `px4-rover2` run from the images of their own platform's firmware

#### Scenario: Firmware overridden over a base
- **WHEN** `rover1` names `rover_differential_lidar_px4` and `rover2` has an inline platform with that `base` and `autopilot: {px4: {version: v1.18.0}}`
- **THEN** `px4-rover1` runs `v1.18.0-rc1` and `px4-rover2` runs `v1.18.0`, both with airframe 50000
