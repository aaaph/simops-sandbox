# Design

## Context

Since `mavlink-port`, agent `i`'s PX4 API link is published on the host at
`mavlink_port + i` (UDP), and PX4 keeps the first host client that writes to it as its partner
for its lifetime (known gap in `host-access`). The rover's platform has a navsat sensor and every
worldgen world has spherical coordinates and the NavSat system, so PX4 gets a global position and
a home: missions work. `Session.up` returns once the agent is in the world, not once it can arm.

## Goals / Non-Goals

**Goals:** one scenario test that drives the rover through a mission with the operator tools a
user would use, kept apart from the lifecycle tests by its marker.

**Non-Goals:** a judge (estimate vs ground truth); readiness "can arm" inside `simops up`; a
shared pytest fixture; Linux in the pixi lock; running scenarios in parallel.

## Decisions

- **`mavsdk-grpc` 3.17.4, not `mavsdk` 4.** 4.x needs a `macosx_15_0` wheel (pixi declares macOS
  14) and has a new API; `mavsdk-grpc` keeps the API of PX4's own examples, has wheels for macOS 14
  arm64 and every manylinux, and its `grpcio`/`protobuf` come from PyPI without touching the
  conda env (checked: `grpcio` 1.84 has cp314 wheels). Cost: a `mavsdk_server` process per
  `System()` on gRPC port 50051, and the maintenance branch of MAVSDK-Python.
- **Markers `docker` + `scenario`.** The test starts containers, so the rule "a test that starts
  containers is `docker`" and `addopts = -m "not docker"` stay as they are; `scenario` only adds a
  way to select. A `scenario`-only marker would need `addopts` and the conventions rewritten, and
  a forgotten marker would start containers in `pixi run test`. "Scenario" is the glossary's
  reserved word for exactly this (a task and its success criteria in a session).
- **MAVSDK listens where the agent's PX4 sends,** `udpin://0.0.0.0:<mavlink_port>` (since
  `mavlink-to-host`; the first try, `udpout` to a published port, deadlocked: `mavsdk_server` waits
  for the vehicle to speak first and PX4 waited for its client).
- **The test reads like PX4's example, under `asyncio.run` inside a plain `test_*`** (no
  pytest-asyncio). Every wait is bounded with `asyncio.wait_for`: `connect()` itself (it returns only once
  `mavsdk_server` has heard the vehicle), connection, health (global
  position, home, `is_armable`; GPS fix and EKF take a while), mission finished. A lost link then
  fails the test instead of hanging it, and `down` runs in `finally`.
- **The square for a rover:** corners 5 m north, north-east, east of home and home again,
  converted with a flat-earth approximation (`5 / 111_320` degrees of latitude, divided by
  `cos(latitude)` for longitude — exact enough at 5 m), `relative_altitude_m = 0`, speed `nan`
  (PX4's rover default), `is_fly_through = False`, acceptance radius `nan` (PX4's), no camera or
  gimbal actions; `MissionItem` with keyword arguments. No RTL and no `in_air` wait: the last
  corner is home; after the mission the test disarms.
- **Pass = mission finished in time** (`mission_progress` reaches `total` and
  `is_mission_finished()`); no position check until there is a judge.
- **Its own small environment, inline:** an open field, `rover1` at the origin, name
  `t_square`, router port 7480, MAVLink port 14800 — outside the lifecycle tests' ports. Written to
  `tmp_path` like the lifecycle tests' environments; not shared with them (they use a room).

## Risks / Trade-offs

- [`mavsdk_server`'s gRPC port 50051 is fixed per `System()`] → one scenario at a time, as for
  sessions; pass another `port` when scenarios run in parallel.
- [The rover may not reach a corner (acceptance radius, turning) and the mission never
  finishes] → the mission wait is bounded; on timeout the test prints the last progress seen. If
  it happens, set `acceptance_radius_m` explicitly.
- [Arming refused (preflight)] → the health wait includes `is_armable`; `arm()` raising fails the
  test with MAVSDK's reason.
