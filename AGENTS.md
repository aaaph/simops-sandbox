# simops-sandbox

ROS 2 Lyrical + Gazebo Jetty + PX4 sandbox for a differential rover: the simulation runs in
Docker (`simops`, below), the Mac keeps only the native gz GUI and host ROS, through pixi.

Never clean up with broad `pkill` patterns: other projects on this machine run rerun too, and the
rerun MCP server's own viewer must stay up.

## Known quirks

- If ROS topics look silent while Gazebo publishes (`gz topic -l`), the ros2 daemon holds a stale
  graph: `pixi run ros2 daemon stop`.

## Docker sim: scenarios — world + agents + PX4 in containers, native macOS gz GUI over zenoh

A scenario is one YAML file — world, autopilot firmware, agents (platform + pose), namespaces,
router port — see `scenarios/rover_room.yaml`. `sim/simops.py` builds it into `build/<name>/`
(`compose.yaml`, the merged `bridge.yaml`, the world with the agents placed in it, the platforms it
uses) and runs it as its own compose project, with `GZ_PARTITION=<name>`:

    pixi run simops up scenarios/rover_room.yaml     # returns once every agent is in the world and sim time moves
    pixi run simops gui scenarios/rover_room.yaml    # native gz GUI, right partition and router
    pixi run simops env scenarios/rover_room.yaml | source   # gz/ROS on the host (bash: eval "$(...)")
    pixi run simops run scenarios/rover_room.yaml -- pytest tests/   # up, command, down whatever happens
    pixi run simops down scenarios/rover_room.yaml

**Clean up after yourself:** containers you started to check or verify something, you stop —
`simops down`, or `simops run`, which does it for you. Leave running only what the user asked to
keep up, and never touch containers you did not start.

**The contract is in `openspec/specs/`** — `scenario` (the file format), `bundle` (what `build`
writes), `sim-lifecycle` (`up`/`down`/`run`), `agent-spawn` (first the world, then the agents),
`agent-interface` (topics, namespaces), `host-access` (`env`, `gui`, what host code must use),
`autopilot`. Change behavior through an OpenSpec change, not by editing code alone. Tests:
`pixi run test` (unit, seconds) and `pixi run pytest -m docker` (starts scenarios, minutes).

How it is done, beyond the specs:
- The CLI is Typer; the compose project is driven through testcontainers' `DockerCompose`
  (`up --wait`, exec, logs), except `down`, which adds `--remove-orphans` that `stop()` lacks.
  testcontainers' logger is silenced: simops prints the failures itself.
- A platform (`platforms/<p>/`) is `model.sdf` + `bridge.yaml` + `agent.yaml`; the last holds
  what cannot be separated from the body — for now the PX4 airframe.
- Spawning goes through `/world/<w>/create` in the generated `spawn.sh`. The create reply can get
  lost over zenoh (#868 below), so it looks for the model in `/world/<w>/pose/info` and retries.
- Namespaces rewrite the gz `<topic>`/`<odom_topic>` in a per-agent copy of the model
  (`platforms/<p>.<agent>/`) and the bridge entries; for PX4 (whose zenoh module has no namespace
  option) `sim-px4` in `px4.Dockerfile` writes its topic list `<board root>/zenoh/{pub,sub}.csv` (root `.` in 1.18.0-rc1,
  `./fs` on later main) with the prefix before it starts.

Services: `zenoh-router` (ROS 2 and gz-transport both go through it), `world` (gz Jetty server),
`px4-<agent>` (PX4 SITL of the scenario's firmware, instance `-i N` so the PX4s sharing one network
namespace get their own MAVLink ports), `spawn` (above) and `sim-sensors` (`ros_gz_bridge` with the agents'
`bridge.yaml` merged: `/clock`, `/scan`, `/scan/points`, `/ground_truth` — the sim's stand-in for
the sensor drivers). IMU, odometry and the
wheels are PX4's `/fmu/*`. Images: `simops-sandbox-{ros,world}` and `simops-sandbox-px4:<commit[:12]>`,
built by compose on first use; after a Dockerfile change, `docker compose -f
build/<name>/compose.yaml build`. All of them are built on the same conda-forge gz Jetty as the
macOS pixi env, with gz-transport's zenoh backend, so the native macOS GUI attaches through the
router — no noVNC. The same `GZ_PARTITION` is required on every side: the default is
`<hostname>:<user>`, so the containers and the Mac never see each other without it.

PX4 version (spec: `autopilot`): `version: v1.18.0` or `commit: <full SHA>`, or neither for the
newest 1.18+ release (the newest 1.18+ pre-release while there is none). `build` resolves it
with `git ls-remote` (network; a `commit` builds offline) and tags the image by the commit, so
each firmware is one full PX4 build (~10 min) and switching back to a built one costs nothing.
PX4 1.18 is the minimum: 1.17 and earlier compile as C++14, which the conda gz Jetty env's
abseil (C++17) cannot build (v1.17.0 checked 2026-09-28); older PX4 would need the Harmonic +
noVNC variant below as a second stack. A commit build fetches its history (no trees, ~300 MB)
so PX4 reports its `git describe` version and too old a commit stops before the compile.

**Previous variant, gz Harmonic + GUI over noVNC,** is in commit `fb24cde`: `infra/world.Dockerfile`
(targets `world` and `gui`), `infra/px4.Dockerfile` (PX4 built with PX4's `ubuntu.sh`, Harmonic from
the OSRF apt repo, gz-transport over zeromq) and the `world`, `gui`, `px4` services of
the old hand-written `docker-compose.yaml`. It needs nothing on the Mac but a browser (http://localhost:6080/vnc.html,
router publishing `127.0.0.1:6080`), at the cost of software rendering (~2 cores, capped). Bring it
back with `git show fb24cde:<path>`; gz-transport stays inside the shared network namespace
there, so it has none of the zenoh issues below.

**gz-transport is a custom build everywhere** — the macOS pixi env, the `world` image and the `px4`
image. Stock 15.1.0 has two zenoh bugs that upstream fixed but has not released for Jetty (as of
2026-09-25), both carried by `infra/patches/gz-transport15-zenoh-fixes.patch` (its header has the
details), cut down to keep the ABI of the prebuilt gz-sim/gz-gui/PX4 binaries:
- #966 (backport of #867): the GUI deadlocks at startup (gz-transport#741) unadvertising a
  service from inside that service's callback.
- #965 (backport of #961): zenoh loops a process's own publications back synchronously, and PX4's
  gz_bridge — subscribed to the wheel/ESC command topic it publishes, under one non-recursive
  mutex — deadlocks its `rate_ctrl` work queue: wheels never turn, `vehicle_angular_velocity`
  stalls, preflight fails with accelerometer timeouts.

- **Install:** `infra/build-gz-transport.sh` clones 15.1.0, applies the patch, builds it against
  the dependency versions installed in `ENV_DIR` (default: this repo's pixi env) and swaps in the
  library, keeping the conda one as `*.orig`. It refuses to run on any other gz-transport version.
  `world.Dockerfile` and `px4.Dockerfile` run the same script against their own conda env.
- **Revert (macOS):** `infra/build-gz-transport.sh --revert`, or `pixi reinstall`.
- The patch's blank context lines are whitespace-significant: pre-commit's whitespace hooks skip
  `*.patch`, and an edited patch must pass `git apply --check` on a 15.1.0 checkout.
- `pixi install`/`update` that touches gz-transport puts the conda library back; re-run the
  script if the GUI hangs again.
- **To try another PR the same way:** clone the tag matching the installed version, `git fetch
  origin pull/<N>/head` and cherry-pick it, and make sure it changes no public header or class
  layout: only the library is swapped, the gz binaries and PX4 stay as built. The script checks
  that no exported symbol goes missing.

**Waiting on upstream:**
- #966 and #965 released in a conda-forge gz-transport 15 → drop the patch, the script and the
  build steps in both Dockerfiles.
- #868 (Part 2/2) backported → service replies over zenoh stop getting lost. It changes public
  headers and inline request code, so it cannot be patched in like the others. Until then a
  request can wait forever: `px4.Dockerfile` wraps `gz` to bound `gz service` (PX4 spawns its
  vehicle with one), and the macOS `gz service` CLI may hang although the world acted on it.

**Other things the Jetty images work around:** the world needs Mesa from apt (the conda env has
only the glvnd dispatcher, so Ogre segfaults when the rover's gpu_lidar spawns); PX4 needs OpenCV
4 (its optical-flow gz plugin uses C headers OpenCV 5 dropped) and a system gcc (its idlc host tool
hardcodes `/usr/bin/gcc`).

Only one source of manual control wins in PX4: with QGC's virtual joystick on, sticks sent from
a script on another MAVLink link are ignored.

If `zenoh-router` is restarted outside compose (`docker restart`, or `restart: always` after a
crash), every container in its network namespace is left without network:
`docker compose -p <name> up -d --force-recreate <service>`.

## Planned: simops as a tool

Direction: a generic tool, not robot code — a Python package (library, `simops` CLI, pytest
helper) taken as a dev-dependency by robot repos, the rover here staying as the example. Done:
scenario format, `agent.yaml`, several agents with optional namespaces, bundle,
`up/down/run/env/gui` (`sim/simops.py`). Next, in this order, each when
something needs it:
- `simops.testing.sim_session(scenario)` — pytest fixture over up/down, per-session name and port
  so tests run in parallel; agent helpers (arm, drive, ground truth) on top.
- readiness beyond "in the world": PX4 heartbeat and preflight passed, so `up` means "can arm".
- `show` (services, RTF, PX4 mode, topic rates), `reset`; TF frame prefixes with namespaces.
- `--docker-host ssh://...` for a sim on another machine; the bundle already runs anywhere with
  Docker once its build contexts are images in a registry.
- a single-container target for the cloud (Modal), router reached through a tunnel.

## Checks

`pixi run lint`, `pixi run test`, `pixi run format`. Pre-commit runs the same hooks.
