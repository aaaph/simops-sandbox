# syntax=docker/dockerfile:1
# ROS 2 Lyrical from robostack, one image for the stack's ROS side (each
# service picks its command in the compose file sim/simops.py generates):
#   zenoh-router  rmw_zenohd, the router every ROS node and gz-transport peer
#                 connects through; same zenoh-c as the macOS pixi env
#   sim-sensors   ros_gz_bridge: the sim's stand-in for the rover's sensor
#                 drivers — lidar, /clock and ground truth on ROS 2, as the
#                 platform's bridge.yaml says. Same conda-forge gz Jetty as
#                 world/px4 on the gz side.
FROM ghcr.io/prefix-dev/pixi:0.81.0

WORKDIR /opt/ros
RUN pixi init --platform linux-aarch64 --platform linux-64 \
    -c https://prefix.dev/robostack-lyrical -c https://prefix.dev/conda-forge \
    && pixi add ros-lyrical-ros-gz-bridge ros-lyrical-rmw-zenoh-cpp \
    && pixi shell-hook > /opt/ros/activate.sh \
    && pixi clean cache --yes

# gz side: GZ_PARTITION and the router endpoint come from compose, as for the
# world. ROS side: rmw_zenoh, router endpoint from compose too.
ENV GZ_TRANSPORT_IMPLEMENTATION=zenoh \
    RMW_IMPLEMENTATION=rmw_zenoh_cpp

# bash: some of the env's activation scripts use `source`.
COPY --chmod=755 <<'EOF' /usr/local/bin/zenoh-router
#!/bin/bash
. /opt/ros/activate.sh
exec "$CONDA_PREFIX/lib/rmw_zenoh_cpp/rmw_zenohd"
EOF

COPY --chmod=755 <<'EOF' /usr/local/bin/sim-sensors
#!/bin/bash
. /opt/ros/activate.sh
exec "$CONDA_PREFIX/lib/ros_gz_bridge/parameter_bridge" \
	--ros-args -p "config_file:=${BRIDGE_CONFIG:?set BRIDGE_CONFIG to a bridge.yaml}"
EOF
