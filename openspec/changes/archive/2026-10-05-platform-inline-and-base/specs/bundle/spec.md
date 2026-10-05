## MODIFIED Requirements

### Requirement: Bundle contents
`simops build <environment>` SHALL write the bundle to `build/<name>/` and print its path, without
starting any container; when `SIMOPS_BUILD_DIR` is set, bundles go to `$SIMOPS_BUILD_DIR/<name>/`
instead, for `build`, `up`, `down` and `run` alike. The bundle SHALL contain `compose.yaml`, `spawn.sh`, `bridge.yaml`,
`worlds/` with the environment's world, and `platforms/` with the directory of every agent's
model (see `platform`, "The model's directory is the model"), under that directory's name, plus
every model those models reference through `model://<name>/` URIs. Each agent SHALL be spawned
from its model's own file in `platforms/`, whatever that file is named. Two agents whose models
lie in different directories of the same name SHALL fail the build, naming both directories.
Building again SHALL replace the previous bundle entirely.

#### Scenario: Platform borrowing meshes
- **WHEN** an agent's platform references another model, `model://<other>/meshes/...`
- **THEN** the bundle contains both that platform and `platforms/<other>/meshes`

#### Scenario: Model not named model.sdf
- **WHEN** an agent's inline platform sets `model: ../models/husky/husky.sdf`
- **THEN** the bundle contains `platforms/husky/husky.sdf` and the agent is spawned from it

#### Scenario: Two agents, one model directory
- **WHEN** `rover1` names `platforms/rover_differential_lidar_px4` and `rover11` has an inline platform whose `model` is that directory's `model.sdf`
- **THEN** the bundle contains `platforms/rover_differential_lidar_px4` once

#### Scenario: Two model directories, one name
- **WHEN** two agents' models are `a/rover/model.sdf` and `b/rover/model.sdf`
- **THEN** the build fails naming `a/rover` and `b/rover`

#### Scenario: Bundles elsewhere
- **WHEN** `SIMOPS_BUILD_DIR=/tmp/bundles simops build rover_room.yaml` runs
- **THEN** the bundle is written to `/tmp/bundles/rover_room/` and nothing to `build/`

#### Scenario: Rebuild drops stale files
- **WHEN** a bundle directory contains a file the current environment does not produce and the environment is built again
- **THEN** the file is gone
