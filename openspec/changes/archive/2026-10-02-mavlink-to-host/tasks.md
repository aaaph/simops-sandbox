# Tasks

## 1. PX4 sends its API link to the host

- [x] 1.1 In `sim-px4` (`infra/px4.Dockerfile`): `-t <host IP>` on every `mavlink start` line again,
  and with `PX4_MAVLINK_PORT` set, `udp_offboard_port_remote=$PX4_MAVLINK_PORT` in
  `px4-rc.mavlink`; update the comment. Rebuild the PX4 image as its own step
  (`docker compose -f <a bundle>/compose.yaml build px4-rover1`). Verify: in the PX4 container of
  a session whose agent has `PX4_MAVLINK_PORT=14590` (4.2), `px4-rc.mavlink` has `-t` on the API
  line and `udp_offboard_port_remote=14590`.

## 2. Environment and bundle

- [x] 2.1 `Network.mavlink_port` defaults to 14540 (`src/simops/environment.py`, its comment).
  Verify: `test_defaults` in `tests/simops/test_environment.py` asserts 14540 (unit, in memory).
- [x] 2.2 `src/simops/bundle.py`: drop the published MAVLink ports; set `PX4_MAVLINK_PORT` to
  `mavlink_port + i` in each `px4-<agent>`'s environment; add the label
  `simops.mavlink_ports: "<first>-<last>"`. Verify: unit tests in `tests/simops/test_bundle.py` —
  router ports only in `ports`, `PX4_MAVLINK_PORT` 14590 for one agent with `mavlink_port: 14590`,
  14540/14541 for two with the default, the three labels (in memory, `bundle.build`).

## 3. `up` refuses MAVLink ports a running session uses

- [x] 3.1 `src/simops/session.py`: read `simops.mavlink_ports` into `RunningSession` (None when
  absent), a pure function giving the running session (other than this one) whose range overlaps
  `mavlink_port .. mavlink_port + agents - 1`, and in `Session.up`, before `docker compose up`,
  print `MAVLink ports <first>-<last> are used by session <name>` and return 1. Verify: unit tests in
  `tests/simops/test_session.py` from `docker ps` text — overlapping range found, disjoint and own
  name not, unlabelled session ignored (in memory).

## 4. Docs and Docker tests

- [x] 4.1 `AGENTS.md` MAVLink paragraph (PX4 sends to the host; `udpin://0.0.0.0:<mavlink_port +
  i>`, default 14540; the check in `up`, not in plain compose; no one-client limit),
  `environments/*.yaml` comments (`mavlink_port: 14540`). Verify: `pixi run lint`, `pixi run test`,
  `openspec validate mavlink-to-host --strict` pass.
- [x] 4.2 `tests/simops/test_session_docker.py`: drop the HEARTBEAT sender and its CRC; the MAVLink
  test listens on the session's MAVLink port, receives a MAVLink 2 frame from system 1, closes,
  listens again and receives again; the taken-port test expects `up` of `b` to fail, no container
  of `b`, `a` running. Verify: `pixi run pytest -m docker tests/simops/test_session_docker.py`
  passes (Docker, rebuilt PX4 image from 1.1), no container left.
