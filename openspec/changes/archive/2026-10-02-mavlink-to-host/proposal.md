# Proposal

## Why

`mavlink-port` published each agent's PX4 API link on the host and let PX4 answer the first
client that writes to it. MAVSDK-Python's `mavsdk_server` never writes first: it waits for a
vehicle's HEARTBEAT before it sends anything or opens its gRPC port, so a MAVSDK client and PX4
wait on each other forever (found running the square scenario). The published port also left one
host client per PX4 lifetime.

## What Changes

- **BREAKING** PX4 sends each agent's API link to the host, as stock PX4 SITL does for MAVSDK and
  as the GCS link already does for QGC: agent `i` to the host's UDP port `mavlink_port + i`. Host
  code listens there (`udpin://0.0.0.0:<port>`, how every PX4/MAVSDK example connects), any number
  of clients one after another. The bundle publishes no MAVLink port.
- `network.mavlink_port` defaults to 14540 (was 14580): the port PX4 SITL and MAVSDK examples use.
- Two sessions no longer collide through Docker on a MAVLink port, so `up` checks it: a session
  whose MAVLink ports overlap those of a running session fails `up` before starting anything,
  naming that session. The bundle labels its containers with its MAVLink ports so running
  sessions can be checked from Docker, as the router port already is.
- The known gap "one host client per PX4 lifetime" goes away.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `environment`: default `network.mavlink_port` 14540.
- `bundle`: no MAVLink port published; each agent's PX4 is told its host port; containers carry
  `simops.mavlink_ports`.
- `host-access`: host code listens on `localhost:<mavlink_port + i>`; no one-client gap.
- `sim-lifecycle`: MAVLink ports shared with a running session fail `up` (checked by simops, not
  by Docker).

## Impact

- `infra/px4.Dockerfile` (`sim-px4`: `-t` back on the API link, its remote port from the bundle;
  PX4 image rebuilt, a cached layer), `src/simops/bundle.py`, `src/simops/environment.py`,
  `src/simops/session.py` (labels read, check in `up`).
- Tests: unit (`bundle.build`, labels, the check from `docker ps` output), Docker (PX4 heard on the
  host port; second session on the same port refused).
- Docs: `AGENTS.md` MAVLink paragraph, `environments/*.yaml` comments.
- The change `square-mission-scenario` waits for this one, then connects with `udpin`.
- A session started with plain `docker compose` is not checked (only `simops up` checks).
