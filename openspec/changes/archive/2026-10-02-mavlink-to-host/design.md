# Design

## Context

After `mavlink-port`, `sim-px4` drops `-t` from PX4's API link and the bundle publishes
`mavlink_port + i` → `14580 + i`; PX4 then sends nothing until a client writes to it. MAVSDK-Python
3.x's `mavsdk_server` (in `udpout` mode) sends nothing until it has heard a vehicle, and does not
open its gRPC port before that, so `System.connect()` never returns (seen with the square
scenario: no `partner IP` in PX4's log, no gRPC listener). `mavsdk_server` has no option to send
heartbeats first.

PX4's GCS link has always worked the other way round: `-t host.docker.internal` makes it send to
the host's 14550, QGC listens there and answers to the address the messages come from, which
Docker Desktop's NAT carries back to the container. Stock PX4 SITL does the same for its API link
(to `14540 + i`), which is why PX4 and MAVSDK examples connect with `udpin://0.0.0.0:14540`.

## Goals / Non-Goals

**Goals:** MAVSDK (and any MAVLink tool) connects the standard way, any number of times per
session; two sessions on the same MAVLink ports still never run side by side.

**Non-Goals:** Linux hosts (no `host.docker.internal`: PX4 then sends inside the session, as before
this change); the check for sessions started with plain `docker compose up`; per-session
`MAV_SYS_ID` for QGC across sessions.

## Decisions

- **PX4 sends the API link to the host.** `sim-px4` puts `-t <host.docker.internal>` back on every
  `mavlink start` line and, when `PX4_MAVLINK_PORT` is set, rewrites
  `udp_offboard_port_remote=` in `px4-rc.mavlink` to it (idempotent, like the `-t` rewrite). The
  bundle sets `PX4_MAVLINK_PORT=mavlink_port + i` per agent and drops the published MAVLink ports.
  Alternatives: `mavsdk_server` inside the session with its gRPC port published (keeps a Docker
  lock, but a new service, a binary in an image and a server/client version pair to keep);
  `mavsdk` 4 (may send heartbeats first, but macOS 15 and another API, unverified).
- **Default `mavlink_port` 14540**, stock SITL's: a one-agent session behaves for host tools exactly
  like a native PX4 SITL, and PX4/MAVSDK examples run unchanged.
- **The lock moves from Docker to `up`.** Docker cannot see ports PX4 sends to. The bundle labels
  every container `simops.mavlink_ports: "<first>-<last>"`; `up` reads running sessions as it
  already does (`read_sessions`), and refuses — before `docker compose up`, naming the session —
  when another session's range overlaps its own. The same session's name is not a conflict (a
  second `up` of a running session). The overlap test is a pure function over `RunningSession`s,
  unit-tested from `docker ps` text like `sessions()`.
- **Docker tests listen, they do not send.** The hand-built HEARTBEAT and its CRC go; the test binds
  the session's MAVLink port, receives a MAVLink 2 frame from system 1, closes, binds again and
  receives again (a second client). The reply path (host → PX4) is the same NAT that QGC's
  commands use; the square scenario exercises it (mission upload, arm).

## Risks / Trade-offs

- [A session started with plain `docker compose` is not checked] → it still runs; two PX4s on one
  host port show up as two vehicles with system id 1 to the client. Stated in the spec's scope
  (`simops up`), noted in AGENTS.md.
- [A host port the session sends to is already bound by something else] → harmless for PX4 (UDP
  send); the other program receives MAVLink. Not checked.
- [Reply path through Docker Desktop's NAT for the API link] → the same path QGC's commands take on
  14550; verified by the square scenario's mission upload.
- [Bundles built before this change publish MAVLink ports and lack the label] → `up` them again; an
  unlabelled running session is not taken into account by the check.

## Migration Plan

Rebuild the PX4 image (`docker compose -f <bundle>/compose.yaml build px4-<agent>`: only the
`sim-px4` layer changes). Host tools that used `udpout://localhost:<port>` switch to
`udpin://0.0.0.0:<port>`; environments that set `mavlink_port` keep it, others move from 14580 to
14540.
