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

## Checks

`pixi run lint`, `pixi run test`, `pixi run format`. Pre-commit runs the same hooks.
