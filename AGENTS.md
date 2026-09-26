# simops-sandbox

ROS 2 Lyrical + Gazebo Jetty sandbox for a differential rover, run entirely through pixi.

## Running the simulation

- **Start:** `pixi run up` — add `--slam` for slam_toolbox, `--bridge` for the rerun bridge.
  It returns only once the robot is moving in the sim. If it cannot get there, it prints the
  log tail and leaves nothing running. Logs: `.stack/{sim,slam,bridge}.log`.
- **Stop:** `pixi run down` — always, when you are done. It kills everything this repo started,
  including processes that escaped their process group (the rerun viewer does).
- **Health:** `pixi run doctor` names the first broken link: processes, physics, ROS topics.
- The stack stops itself after 30 minutes (`--ttl MINUTES`, `0` disables) in case `down` is forgotten.

Do not start `pixi run bringup`, `slam` or `rerun_bridge` in the background yourself: when the
`ros2 launch` wrapper dies its children re-parent to launchd and keep running. And never clean up
with broad `pkill` patterns — `down` matches only this repo's processes, while other projects on
this machine run rerun too, and the rerun MCP server's own viewer must stay up.

## Known quirks

- The IMU is simulated at 30 Hz, not the real 250: above ~40 Hz the gz server stops stepping as
  soon as anything subscribes to `/imu` — even a bare `gz topic -e`, no ROS involved, and not only
  at startup (macOS, Harmonic and Jetty alike). Keep this in mind for PX4, whose gz_bridge reads
  the IMU at a high rate.
- Gazebo publishes odometry with an all-zero covariance; `sim/odom_covariance.py` fills it in
  before robot_localization sees it.
- If ROS topics look silent while Gazebo publishes (`gz topic -l`), the ros2 daemon holds a stale
  graph: `pixi run ros2 daemon stop`.
- Port 7447 is taken by Docker, so `rmw_zenohd` cannot start; rmw_zenoh works peer-to-peer without it.

## Docker sim: scenarios — world + robots + PX4 in containers, native macOS gz GUI over zenoh

A scenario is one YAML file — world, autopilot firmware, robots (platform + pose), namespaces,
router port — see `scenarios/rover_room.yaml`. `sim/simops.py` builds it into `build/<name>/`
(`compose.yaml`, the merged `bridge.yaml`, the world with the robots placed in it, the platforms it
uses) and runs it as its own compose project, with `GZ_PARTITION=<name>`:

    pixi run simops up scenarios/rover_room.yaml     # returns once every robot is in the world and sim time moves
    pixi run simops gui scenarios/rover_room.yaml    # native gz GUI, right partition and router
    pixi run simops env scenarios/rover_room.yaml | source   # gz/ROS on the host (bash: eval "$(...)")
    pixi run simops run scenarios/rover_room.yaml -- pytest tests/   # up, command, down whatever happens
    pixi run simops down scenarios/rover_room.yaml

**Clean up after yourself:** containers you started to check or verify something, you stop —
`simops down`, or `simops run`, which does it for you. Leave running only what the user asked to
keep up, and never touch containers you did not start.

World: `room: {seed, size, obstacles}` generates a room with `sim/generate_temp_room_world.py`
(same seed, same room), `file: <path>.sdf` takes a ready one. Two scenarios run side by side if
their `name` and `router_port` differ.

A platform (`platforms/<p>/`) is `model.sdf` + `bridge.yaml` + `platform.yaml`; the last holds
what cannot be separated from the body — for now the PX4 airframe. The scenario only picks the
firmware (`autopilot.px4.ref`), the same for every robot.

**First the world, then the robots** — the principle everything here is built on. The world
starts empty (the world file has no robots); the one-shot `spawn` service adds each robot to the
running world under its scenario name (`/world/<w>/create`, generated `spawn.sh`), and each
`px4-<robot>` starts only after `spawn` succeeded and attaches to its robot (`PX4_GZ_MODEL_NAME`).
The create reply can get lost over zenoh (#868 below), so `spawn.sh` does not wait on it: it looks
for the model in `/world/<w>/pose/info` and retries. When the world restarts, compose reruns
`spawn` and the PX4s with it. `namespaces: true` puts every robot's topics under `/<robot>/` — `/rover1/scan`,
`/rover1/ground_truth`, `/rover1/fmu/out/...` — even with one robot, and is required for more than
one; `/clock` stays global. It works by rewriting the gz `<topic>`/`<odom_topic>` in a per-robot
copy of the model (`platforms/<p>.<robot>/`) and the bridge entries, and, for PX4 (whose zenoh
module has no namespace option), by writing its topic list `fs/zenoh/{pub,sub}.csv` with the
prefix before it starts (`sim-px4` in `px4.Dockerfile`). TF frame ids (`odom`, `base_link`,
`lidar_link`) are not prefixed yet.

Services: `zenoh-router` (ROS 2 and gz-transport both go through it), `world` (gz Jetty server),
`px4-<robot>` (PX4 SITL at the scenario's `ref`, instance `-i N` so the PX4s sharing one network
namespace get their own MAVLink ports), `spawn` (above) and `sim-sensors` (`ros_gz_bridge` with the robots'
`bridge.yaml` merged: `/clock`, `/scan`, `/scan/points`, `/ground_truth` — the sim's stand-in for
the sensor drivers). IMU, odometry and the
wheels are PX4's `/fmu/*`. Images: `simops-sandbox-{ros,world}` and `simops-sandbox-px4:<ref[:12]>`,
built by compose on first use; after a Dockerfile change, `docker compose -f
build/<name>/compose.yaml build`. All of them are built on the same conda-forge gz Jetty as the
macOS pixi env, with gz-transport's zenoh backend, so the native macOS GUI attaches through the
router — no noVNC. The same `GZ_PARTITION` is required on every side: the default is
`<hostname>:<user>`, so the containers and the Mac never see each other without it.

PX4 version: each `ref` is its own image and a full PX4 build (~10 min); switching back to a
built `ref` costs nothing. There is no `v1.17.0` tag yet (latest `v1.17.0-rc2`, 2026-09-26); the
pinned commit is `main` with the Jetty build fix #28843 — check a release has it before pinning.

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
hardcodes `/usr/bin/gcc`). `PX4_REF` defaults to `main`, so a rebuild picks up new PX4 commits.

Only one source of manual control wins in PX4: with QGC's virtual joystick on, sticks sent from
a script on another MAVLink link are ignored.

If `zenoh-router` is restarted outside compose (`docker restart`, or `restart: always` after a
crash), every container in its network namespace is left without network:
`docker compose -p <name> up -d --force-recreate <service>`.

## Planned: simops as a tool

Direction: a generic tool, not robot code — a Python package (library, `simops` CLI, pytest
helper) taken as a dev-dependency by robot repos, the rover here staying as the example. Done:
scenario format, `platform.yaml`, several robots with optional namespaces, bundle,
`up/down/run/env/gui` (`sim/simops.py`). Next, in this order, each when
something needs it:
- `simops.testing.sim_session(scenario)` — pytest fixture over up/down, per-session name and port
  so tests run in parallel; robot helpers (arm, drive, ground truth) on top.
- readiness beyond "in the world": PX4 heartbeat and preflight passed, so `up` means "can arm".
- `show` (services, RTF, PX4 mode, topic rates), `reset`; TF frame prefixes with namespaces.
- `--docker-host ssh://...` for a sim on another machine; the bundle already runs anywhere with
  Docker once its build contexts are images in a registry.
- a single-container target for the cloud (Modal), router reached through a tunnel.

## Checks

`pixi run lint`, `pixi run test`, `pixi run format`. Pre-commit runs the same hooks.
