# Design

## Context

PX4's MAVLink ports are fixed by its `px4-rc.mavlink` (checked in the built
`simops-sandbox-px4` image): API/offboard link listening on `14580 + instance`, sending to
`14540 + instance`; GCS link listening on `18570 + instance`, sending to 14550. No parameter or
environment variable moves them; only `-i` does. `sim-px4` rewrites every `mavlink start` with
`-t <host.docker.internal>`, so both links send to the Mac, which is how QGC finds a session today.

Every service of a session shares `zenoh-router`'s network namespace (`beside_router` in
`bundle.py`), so container ports of two sessions never collide; only host ports can. The router
port already works this way: 7447 inside, `network.router_port` outside.

## Goals / Non-Goals

**Goals:** one host address per agent's PX4, chosen in the environment; a second session asking
for a taken address fails `up` by itself.

**Non-Goals:** a MAVLink client library or mission (next change); publishing the GCS link (QGC
keeps working through PX4 sending to 14550); `host-env` or the session labels carrying the port
(nothing reads it from a running session yet); moving PX4's own ports.

## Decisions

- **Host side of the mapping only.** `zenoh-router` gets `"<mavlink_port + i>:<14580 + i>/udp"`
  per agent, next to the router port. PX4's ports stay untouched. Alternative —
  configuring PX4's port — needs patching `px4-rc.mavlink` and buys nothing, since the session
  namespaces never collide.
- **Docker is the lock.** A taken host port makes `docker compose up` fail ("port is already
  allocated"), and `Session.up` already prints the log and downs the session on that. Alternative
  — `udpin :14540` on the host with a "no other session up" check through `read_sessions()` —
  needs no bundle change but only the test would honour it, and `up` would not.
- **A field, not a fixed port.** `network.mavlink_port`, default 14580, beside `router_port`. A
  fixed 14580 would let only one session with a PX4 run on a machine, breaking "Environments are
  isolated" and the Docker tests running beside a kept-up `rover_room`.
- **Agent `i` at `mavlink_port + i`,** `i` being the PX4 instance (environment order), the same
  offset PX4 applies inside. No validation of overlap with other sessions or with the router port:
  Docker reports it.
- **The client sends first (`udpout`); `sim-px4` drops `-t` from the API link only.** `-t` marks
  PX4's partner as set (`_src_addr_initialized`), so the link never answers anyone else (spike
  1.1). Without it PX4 takes the first address it hears from (≥ 3 s after start) as its partner;
  through Docker Desktop that is Docker's port proxy, which carries the replies back (spike 1.2).
  The GCS link keeps `-t` for QGC.
- **One client per PX4 lifetime, accepted.** PX4 keeps that partner (address and port) until it
  restarts, and Docker Desktop's proxy gives every host socket its own source port, so a second
  client gets nothing (spike 1.2). Alternatives — a relay in the session that keeps one socket to
  PX4 and answers the latest host client, or PX4 sending to the host (`udpin` on the host, as QGC)
  — were weighed and left: sessions here are disposable, one test or one tool per session.
- **No MAVLink library yet.** The Docker test sends a hand-built MAVLink HEARTBEAT (stdlib
  `socket` + `struct`, X.25 CRC) and expects a MAVLink frame back; no MAVLink library is added in this change.
- `up` prints the agents' MAVLink ports in its summary line beside the router port.

## Risks / Trade-offs

- [A second host client, or one reconnecting from a new socket, gets no answer and no error]
  → stated as a known gap in `host-access`; restart the agent's PX4
  (`docker compose -p <name> restart px4-<agent>`) or the session. A relay is the upgrade path.
- [The API link no longer sends to the host's `14540 + i`] → a host tool listening there
  (`udpin :14540`) now uses `udpout://localhost:<mavlink_port + i>` instead; QGC on 14550 is
  unaffected.
- [A kept-up `rover_room` on 14580 blocks any other session on the default port] → intended;
  Docker tests set their own MAVLink ports, like their router ports.
- [More than 10 agents: PX4's remote API port sticks at 14549] → only the remote port; the local
  (published) one stays `14580 + i`.

## Migration Plan

Existing environments load unchanged with the default. A running session built before this
change has no MAVLink ports published: `up` it again.
