# Proposal

## Why

Nothing yet shows that an agent can be driven end to end through the operator interface: a
session comes up, PX4 answers on its MAVLink port, but no test arms the rover and runs a mission.
A scenario test on an open field — the rover drives a square by a MAVSDK mission — is the first
example of how a robot software repository uses a session, and the base for the later
`sim_session` fixture and the user's judge.

## What Changes

- A dev dependency `mavsdk-grpc` (PyPI, imported as `mavsdk_grpc`: the MAVSDK-Python 3.x API,
  with its own `mavsdk_server`), already added to `pixi.toml` / `pixi.lock`.
- A test `tests/simops/test_square_scenario.py`: up a session of an open field with one agent
  (its own name, router port and MAVLink port), connect MAVSDK to the agent's PX4 at
  `udpin://0.0.0.0:<mavlink_port>` (where it sends, since `mavlink-to-host`), wait until it can arm, upload four waypoints forming a 5 m
  square from home, arm, start the mission, and pass when the mission finishes within a timeout;
  the session is torn down whatever happens. No judge (no ground-truth check) yet.
- A pytest marker `scenario` for tests that run a scenario in a session. Such a test is marked
  `docker` too (it starts containers), so `pixi run test` still excludes it, `-m scenario` runs
  scenarios alone and `-m "docker and not scenario"` the session lifecycle tests alone.

Not in this change: `linux-64` in pixi's platforms (with CI), a judge, the `sim_session`
fixture, any change to simops itself.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none) — no simops behavior changes; the test exercises what `host-access` ("MAVLink from the
host") and `autopilot` already state. The change sets `skip_specs: true`.

## Impact

- `pixi.toml`, `pixi.lock` (`mavsdk-grpc` and its `grpcio`, `protobuf` from PyPI).
- `pytest.ini` (marker), `tests/simops/test_square_scenario.py`.
- Docs: `AGENTS.md` (test kinds), the `scenario` entry of the glossary and the test conventions in
  `openspec/config.yaml`.
- Runs on existing images; one session, about a few minutes.
