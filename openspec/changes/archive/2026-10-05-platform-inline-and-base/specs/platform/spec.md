# Spec Delta

## Purpose

A platform as one document: its model, its bridge entries and its autopilot, written the same way
in a platform directory's `platform.yaml` and inline in an environment, optionally laid over a
base platform.

## ADDED Requirements

### Requirement: Platform document
A platform SHALL be given by one document with the keys:
- `model`: the path to the platform's SDF model (required);
- `bridge`: its bridge entries, as a list of `ros_gz_bridge` entries or as the path to a YAML
  file holding that list (required);
- `autopilot`: its autopilot, as `autopilot` defines it (required);
- `base`: a platform directory the document is laid over (optional; see "Base platform").

Loading SHALL fail on any other key, naming the key and where it is.

#### Scenario: Bridge inline or in a file
- **WHEN** one platform sets `bridge: bridge.yaml` and another the same entries as a list
- **THEN** both platforms have the same bridge entries

#### Scenario: Unknown key
- **WHEN** a platform document sets `brige:`
- **THEN** loading fails naming `brige` and the file or the agent it is written in

#### Scenario: No model
- **WHEN** a platform document, after its base is applied, has no `model`
- **THEN** loading fails naming `model`

#### Scenario: No bridge
- **WHEN** a platform document, after its base is applied, has no `bridge`
- **THEN** loading fails naming `bridge`

### Requirement: Platform directory
A platform directory SHALL hold the platform document as `platform.yaml`. An agent whose
`platform` is a path SHALL use the platform in `<path>/platform.yaml`. A directory without
`platform.yaml` SHALL fail loading, naming the missing file; when it holds an `agent.yaml`, the
message SHALL say that `agent.yaml` is now `platform.yaml` with `model` and `bridge` naming the
platform's files.

#### Scenario: Directory platform
- **WHEN** an agent sets `platform: ../platforms/rover_differential_lidar_px4`
- **THEN** its platform is the document in `platforms/rover_differential_lidar_px4/platform.yaml`

#### Scenario: Old agent.yaml
- **WHEN** an agent's platform directory holds `agent.yaml` and no `platform.yaml`
- **THEN** loading fails naming that directory and saying `agent.yaml` is now `platform.yaml`

### Requirement: Inline platform
An agent's `platform` SHALL also be the platform document itself, written in the environment.
An inline document SHALL give the same platform as a `platform.yaml` with the same content, its
paths resolved as "Paths relative to their own file" says.

#### Scenario: Three forms, one bundle
- **WHEN** three environments, equal but for how `rover1`'s platform is written, give it as
  `../platforms/rover_differential_lidar_px4`, as that platform written out inline (`model`, the
  bridge entries as a list, `autopilot`), and as `{base: ../platforms/rover_differential_lidar_px4}`
- **THEN** the three build equal bundles

### Requirement: Base platform
A platform document with `base: <platform directory>` SHALL be the base platform's document with
this document laid over it: mappings merge key by key, a list or a scalar replaces the base's
value, and `null` removes the base's key (JSON Merge Patch, RFC 7386). A `platform.yaml` MAY have
a `base` of its own; bases apply from the deepest one up. A chain of bases that comes back to a
platform already in it SHALL fail loading, naming the platforms of the chain in order.

#### Scenario: Another firmware on the same body
- **WHEN** an agent's platform is `{base: ../platforms/rover_differential_lidar_px4, autopilot: {px4: {version: v1.18.0}}}`
- **THEN** it has the base's model, bridge entries and airframe 50000, and firmware `v1.18.0`

#### Scenario: Bridge replaced
- **WHEN** an inline platform with a `base` sets `bridge` to one entry
- **THEN** the platform has only that entry, not the base's entries

#### Scenario: Key removed
- **WHEN** an inline platform with a `base` sets `bridge: null`
- **THEN** the base's `bridge` is removed, and loading fails naming `bridge`

#### Scenario: Base of a base
- **WHEN** platform `b`'s `platform.yaml` has `base: ../a` and an agent's inline platform has `base: ../platforms/b`
- **THEN** the agent's platform is `a`'s document, then `b`'s, then the inline one, laid over each other

#### Scenario: Cycle
- **WHEN** platform `a` has `base: ../b` and `b` has `base: ../a`
- **THEN** loading fails naming `a` and `b`

### Requirement: Paths relative to their own file
Every path in a platform document (`model`, `bridge` as a file, `base`) SHALL be resolved against
the directory of the file it is written in: a `platform.yaml`'s own directory, or the
environment file's directory for an inline platform. Paths SHALL be resolved before documents
are merged, so a path taken from a base keeps pointing where the base meant.

#### Scenario: Model from the base
- **WHEN** an inline platform has `base: ../platforms/rover_differential_lidar_px4`, whose `platform.yaml` sets `model: model.sdf`
- **THEN** the model is `platforms/rover_differential_lidar_px4/model.sdf`, not a `model.sdf` next to the environment

#### Scenario: Inline model path
- **WHEN** an environment in `environments/` has an inline platform with `model: ../platforms/rover_differential_lidar_px4/model.sdf`
- **THEN** the model is `platforms/rover_differential_lidar_px4/model.sdf`

### Requirement: The model's directory is the model
The directory of a platform's `model` file SHALL be the model's directory: everything the model
refers to by a relative path or by `model://<that directory's name>/` SHALL be found in it, as
gz finds it.

#### Scenario: Meshes next to the model
- **WHEN** a platform's model refers to `model://rover_differential_lidar_px4/meshes/rover_differential_base.dae` and its `model` is `platforms/rover_differential_lidar_px4/model.sdf`
- **THEN** the mesh is `platforms/rover_differential_lidar_px4/meshes/rover_differential_base.dae`

### Requirement: Platform errors name where they are written
An invalid platform SHALL fail loading the environment with a message naming the platform as the
agent gives it — the `platform.yaml` of a directory, or the environment file and the agent for an
inline platform — then, when it has bases, the `platform.yaml` of each base it is laid over, the
key and why.

#### Scenario: Invalid inline autopilot
- **WHEN** agent `rover1`'s inline platform sets `autopilot: {px4: {airframe: 50000, version: v1.17.0}}`
- **THEN** loading fails with a message naming the environment file, `rover1`, 1.17.0 and the 1.18 minimum

#### Scenario: Invalid platform.yaml
- **WHEN** an agent's platform directory's `platform.yaml` sets `autopilot.px4.version: v1.17.0`
- **THEN** loading fails with a message naming that `platform.yaml`, 1.17.0 and the 1.18 minimum

#### Scenario: Invalid value from the base
- **WHEN** an inline platform has `base: ../platforms/old` and `old/platform.yaml` sets `autopilot.px4.version: v1.17.0`
- **THEN** loading fails with a message naming the environment file, the agent, `old/platform.yaml` and 1.17.0
