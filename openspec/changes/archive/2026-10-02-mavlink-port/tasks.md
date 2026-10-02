# Tasks

## 1. Spike: PX4 answers through a published port

- [x] 1.1 Build a bundle of an open-field environment into a scratch `SIMOPS_BUILD_DIR`, add
  `"14590:14580/udp"` to `zenoh-router`'s `ports` in its `compose.yaml` by hand, start it with
  `docker compose up -d --wait`, send a MAVLink HEARTBEAT from the host to `127.0.0.1:14590` (a few
  lines of stdlib, kept in the scratchpad) and record whether PX4's MAVLink frames come back; then
  `docker compose down`. Verify: a received frame with MAVLink magic `0xFD`/`0xFE` and system id 1,
  noted in this task.
  Result: no answer. PX4's `-t` sets `_src_addr_initialized` (mavlink_main.cpp), so the API link
  never takes the proxy's address as its partner and keeps sending to the host's 14540.
- [x] 1.2 Only if 1.1 got no answer: drop `-t` from the API link alone in `sim-px4`
  (`infra/px4.Dockerfile`, GCS link keeps it for QGC), rebuild the PX4 image as its own step
  (`docker compose -f <bundle>/compose.yaml build px4-rover1`) and repeat 1.1. Verify: as in 1.1.
  If it still gets no answer, stop and revisit the design before group 2.
  Result (`-t` dropped from the API link, image rebuilt): the first client gets frames (magic
  0xFD, sysid 1; PX4 logs `partner IP: 192.168.65.1`). A second client, a new socket right after
  or 20 s later, gets nothing: PX4 keeps the first partner (address and port) for its lifetime, and
  Docker Desktop's proxy gives each host socket its own source port. Accepted as a known gap
  (one host client per PX4 lifetime); design and host-access updated.

## 2. Environment: `network.mavlink_port`

- [x] 2.1 Add `mavlink_port: int = 14580` to `Network` in `src/simops/environment.py`, with its
  docstring. Verify: unit tests in `tests/simops/test_environment.py` — `test_defaults` asserts
  14580, a new case loads `network: {mavlink_port: 14590}` with router port 7447 (in memory,
  `Environment.parse`).
- [x] 2.2 Document the key in `environments/*.yaml` comments (beside `router_port`), the glossary's
  `environment` entry in `openspec/config.yaml` and `AGENTS.md` (services, MAVLink, the QGC
  note). Verify: `pixi run lint` and `pixi run test` pass; `openspec validate mavlink-port --strict`.

## 3. Bundle publishes the MAVLink ports

- [x] 3.1 In `src/simops/bundle.py`, add `"<mavlink_port + i>/udp"` → `14580 + i` per agent to
  `zenoh-router`'s `ports`, `i` the agent's PX4 instance. Verify: unit tests on `bundle.build` in
  `tests/simops/test_bundle.py` (in memory) — one agent with `mavlink_port: 14590` publishes
  `14590:14580/udp`; two agents with the default publish `14580:14580/udp` and `14581:14581/udp`.
- [x] 3.2 Add the agents' MAVLink ports to `up`'s summary line in `src/simops/session.py`
  (`mavlink udp localhost:<port>[-<last>]`). Verify: seen in the Docker test run of 4.2.

## 4. Docker tests

- [x] 4.1 Give every session in `tests/simops/test_session_docker.py` its own MAVLink port beside
  its router port (the `environment()` helper and `test_failed_up_leaves_nothing`), so they run
  beside a kept-up `rover_room` on 14580 and `test_environments_isolated` uses two ranges. Verify:
  `pixi run pytest -m docker tests/simops/test_session_docker.py` passes (Docker, existing images).
- [x] 4.2 Add a Docker test: a session with one agent and its own MAVLink port is up, the host
  sends a HEARTBEAT (the 1.1 helper, moved into the test module) to `localhost:<mavlink_port>` and
  receives a MAVLink frame back within a timeout. Verify: `pixi run pytest -m docker -k mavlink`
  passes (Docker, existing images).
- [x] 4.3 Add a Docker test: session `a` is up on MAVLink port P; `up` of session `b` (other name and
  router port, same P) exits non-zero, leaves no container of `b`, and `a` still has its containers.
  Verify: `pixi run pytest -m docker -k mavlink` passes (Docker, existing images).
