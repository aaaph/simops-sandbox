# syntax=docker/dockerfile:1
# The sim's stand-in for the rover's sensor drivers: ros_gz_bridge puts the
# sim's lidar, /clock and ground truth on the ROS 2 bus, as the platform's
# bridge.yaml says. Simulation only — on the real rover the drivers (RPLidar)
# publish the same topics. Same conda-forge gz Jetty as world/px4 on the gz
# side, rmw_zenoh on the ROS side.
FROM ghcr.io/prefix-dev/pixi:latest

WORKDIR /opt/ros
RUN pixi init --platform linux-aarch64 --platform linux-64 \
        -c https://prefix.dev/robostack-lyrical -c https://prefix.dev/conda-forge \
    && pixi add ros-lyrical-ros-gz-bridge ros-lyrical-rmw-zenoh-cpp \
    && pixi shell-hook > /opt/ros/activate.sh \
    && pixi clean cache --yes

# gz-transport 15.1.0 with the zenoh fixes not yet released for Jetty; see the
# header of infra/patches/gz-transport15-zenoh-fixes.patch. The bridge only
# subscribes today; #965 matters once it bridges anything ROS -> gz, since
# ros_gz_bridge relies on IgnoreLocalMessages, which zenoh breaks without it.
COPY infra/build-gz-transport.sh /opt/sim/infra/
COPY infra/patches /opt/sim/infra/patches
RUN ENV_DIR=/opt/ros/.pixi/envs/default /opt/sim/infra/build-gz-transport.sh \
    && pixi clean cache --yes

# gz side: GZ_PARTITION and the router endpoint come from compose, as for the
# world. ROS side: rmw_zenoh, router endpoint from compose too.
ENV GZ_TRANSPORT_IMPLEMENTATION=zenoh \
    RMW_IMPLEMENTATION=rmw_zenoh_cpp

COPY --chmod=755 <<'EOF' /usr/local/bin/sim-sensors
#!/bin/sh
. /opt/ros/activate.sh
exec "$CONDA_PREFIX/lib/ros_gz_bridge/parameter_bridge" \
	--ros-args -p "config_file:=${BRIDGE_CONFIG:?set BRIDGE_CONFIG to a bridge.yaml}"
EOF
CMD ["sim-sensors"]
