# Proposal

## Why

Host code reaches an agent's PX4 over MAVLink only through PX4 sending to fixed ports on the host
(`host.docker.internal:14540+i`, set by `sim-px4`), which no spec states and nothing reserves: two
sessions each send their instance-0 PX4 (both MAV_SYS_ID 1) to the same host port, and a MAVLink
client there sees two vehicles under one id. Operator-interface tools (MAVSDK, a mission test
next) need one address per agent, and a second session on the same address must not start at all.

## What Changes

- The environment gains `network.mavlink_port` (default 14580): the host UDP port of the first
  agent's PX4 API link; agent `i` (environment order, its PX4 instance) gets `mavlink_port + i`.
- The bundle publishes each agent's PX4 API link (`14580 + i` inside the session) on
  `mavlink_port + i/udp` of the host. The port is chosen on the host side of the mapping only, as
  the router port already is; `sim-px4` stops pointing the API link at the host (`-t`), so PX4
  answers the host client that writes to it first. PX4's own ports stay as they are.
- Known gap: PX4 keeps that first client as its partner for its lifetime, so one host client per
  agent per session (a later one gets no answer until PX4 restarts).
- A session whose MAVLink ports are taken on the host fails `up` (Docker refuses to allocate the
  port) and leaves nothing running, so two sessions never share an agent's MAVLink address.
- Sessions side by side need distinct MAVLink ports as well as distinct names and router ports;
  the Docker tests give each session its own.
- QGC is unaffected: PX4's GCS link still sends to the host's 14550.

Not in this change: a MAVLink client, a mission or any test that drives an agent (the MAVSDK
square mission comes next, on top of this port).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `environment`: `network.mavlink_port` with its default joins the environment's optional keys.
- `bundle`: the compose file publishes each agent's PX4 API link on the host.
- `host-access`: host code reaches agent `i`'s PX4 over MAVLink at `localhost:mavlink_port + i`.
- `sim-lifecycle`: isolation requires distinct MAVLink ports; a taken MAVLink port fails `up`.

## Impact

- `src/simops/environment.py` (`Network.mavlink_port`), `src/simops/bundle.py` (`ports` of
  `zenoh-router`, whose network namespace PX4 shares), the `up` summary line.
- Tests: unit tests on `Environment.parse` and `bundle.build`; Docker tests give each session its
  own MAVLink port, plus one test that a taken port fails `up` and one that PX4 answers on the
  published port.
- Existing environments keep working unchanged (default port); a kept-up `rover_room` holds
  14580, so a second session on the default port no longer starts beside it.
- Docs: glossary (`environment`), `AGENTS.md`, the example environments' comments.
