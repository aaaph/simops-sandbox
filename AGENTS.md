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

## Docker sim: world + PX4 in containers, native macOS gz GUI over zenoh

`docker-compose.yaml`: `zenoh-router` (ROS 2 and gz-transport both go through it), `world` (gz
Jetty server, `worlds/temp_room.sdf`), `px4` (PX4 SITL, spawns
`platforms/rover_differential_lidar_px4` into the world) and `sim-sensors` (`ros_gz_bridge` with the
platform's `bridge.yaml`: `/clock`, `/scan`, `/scan/points`, `/ground_truth` — the sim's stand-in
for the sensor drivers). IMU, odometry and the wheels are PX4's `/fmu/*`. The PX4 commit is pinned
at the top of `docker-compose.yaml`. All of them are built on the same conda-forge gz Jetty as the
macOS pixi env, with gz-transport's zenoh backend, so the native macOS GUI attaches through the
router — no noVNC:

    docker compose up -d world px4 sim-sensors
    GZ_PARTITION=sim GZ_TRANSPORT_IMPLEMENTATION=zenoh \
      GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE='mode="peer";connect/endpoints=["tcp/localhost:7447"];scouting/multicast/enabled=false' \
      pixi run gz sim -g

The same `GZ_PARTITION` is required on every side: the default is `<hostname>:<user>`, so the
containers and the Mac never see each other without it.

**Companion software** — what runs on the rover's Pi 5, in the sim as on the rover, so nothing
simulation-specific in it. A platform is a ROS package in `platforms/<robot>/` (model, bridge.yaml,
`launch/companion.launch.py`; its own nodes too if nobody else needs them); nodes shared by every
PX4 vehicle live in `ros/src/px4_companion` (`px4_odometry`: PX4's EKF on `/odom` and tf
`odom -> base_link`; `frame_publisher`: the sensor frames read from `model.sdf`).
`infra/companion.Dockerfile` builds them with `px4_msgs` from the PX4 commit — use the one pinned
in `docker-compose.yaml`, or the `/fmu` topics silently stop matching. It is not in compose for now:

    docker build -f infra/companion.Dockerfile --build-arg PX4_REF=<sha from docker-compose.yaml> -t simops-sandbox-companion .
    docker run --rm --network container:zenoh-router -e PLATFORM=rover_differential_lidar_px4 \
      -e ZENOH_CONFIG_OVERRIDE='mode="client";connect/endpoints=["tcp/localhost:7447"]' simops-sandbox-companion

**Previous variant, gz Harmonic + GUI over noVNC,** is in commit `fb24cde`: `infra/world.Dockerfile`
(targets `world` and `gui`), `infra/px4.Dockerfile` (PX4 built with PX4's `ubuntu.sh`, Harmonic from
the OSRF apt repo, gz-transport over zeromq) and the `world`, `gui`, `px4` services of
`docker-compose.yaml`. It needs nothing on the Mac but a browser (http://localhost:6080/vnc.html,
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
`docker compose up -d --force-recreate <service>`.

## Checks

`pixi run lint`, `pixi run test`, `pixi run format`. Pre-commit runs the same hooks.
