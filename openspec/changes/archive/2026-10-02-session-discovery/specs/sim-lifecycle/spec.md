# Spec Delta

## ADDED Requirements

### Requirement: Commands find the running session
`gui`, `host-env` and `down` SHALL take the environment as optional: an environment file, or a
session name (the environment's name). Without it they SHALL act on the one running session. A
session SHALL be found from its containers alone, whether it was started by `simops up` or by plain
`docker compose` on its bundle. With several sessions running and none named, the command SHALL
list their names, act on none and exit non-zero. If Docker does not answer, the command SHALL say
so and exit non-zero rather than report that nothing is running.

#### Scenario: One session running
- **WHEN** only `rover_room` is up and `simops gui` runs without an argument
- **THEN** it acts on `rover_room`

#### Scenario: Session name instead of the file
- **WHEN** `rover_room` is up and `simops down rover_room` runs
- **THEN** it acts on `rover_room` as `simops down environments/rover_room.yaml` would

#### Scenario: Several sessions running
- **WHEN** `a` and `b` are up and `simops gui` runs without an argument
- **THEN** it prints `a` and `b`, opens no GUI and exits non-zero

#### Scenario: Session started by plain compose
- **WHEN** a bundle was started with `docker compose -f build/<name>/compose.yaml up -d`
- **THEN** `simops gui`, `simops host-env` and `simops down` without an argument find it

#### Scenario: Docker not running
- **WHEN** the Docker daemon does not answer and `simops gui` runs
- **THEN** it says Docker does not answer and exits non-zero

## MODIFIED Requirements

### Requirement: Down
`simops down [environment]` SHALL stop and remove all containers of the session, exited ones and
orphans from an earlier version of its bundle included, and nothing else. It SHALL not need the
session's bundle directory. With no session to stop it SHALL say so and exit 0.

#### Scenario: Down after up
- **WHEN** `simops down` runs after a successful `up`
- **THEN** no container of that session remains and containers of other projects are untouched

#### Scenario: Half-failed session
- **WHEN** a session's `world` container exited and its other containers run
- **THEN** `simops down` removes all of them

#### Scenario: Bundle directory gone
- **WHEN** a session is up and its `build/<name>/` was deleted
- **THEN** `simops down <name>` removes its containers

#### Scenario: Nothing running
- **WHEN** no session is up and `simops down` runs without an argument
- **THEN** it says nothing is up and exits 0
