# syntax=docker/dockerfile:1
# The rover's companion computer (the Pi 5 on the real rover): the ROS 2 nodes
# next to the autopilot, run by the platform's launch/companion.launch.py — PX4
# odometry on /odom and tf, the fixed sensor frames. No simulation in it: the
# sensors come from their drivers (in the sim, the sim-sensors container).
# rmw_zenoh, px4_msgs from the PX4 commit the firmware is built at. Not part of
# docker-compose.yaml for now; build it with that file's PX4_REF:
#   docker build -f infra/companion.Dockerfile --build-arg PX4_REF=<sha> -t companion .
ARG PX4_REPO=https://github.com/PX4/PX4-Autopilot.git
ARG PX4_REF=main

FROM scratch AS px4-src
ARG PX4_REPO PX4_REF
ADD ${PX4_REPO}#${PX4_REF} /px4

FROM ghcr.io/prefix-dev/pixi:latest

WORKDIR /opt/ros
RUN pixi init --platform linux-aarch64 --platform linux-64 \
        -c https://prefix.dev/robostack-lyrical -c https://prefix.dev/conda-forge \
    && pixi add ros-lyrical-rmw-zenoh-cpp \
        ros-lyrical-ros2launch ros-lyrical-launch-ros ros-lyrical-rclpy \
        ros-lyrical-nav-msgs ros-lyrical-tf2-msgs ros-lyrical-geometry-msgs \
        ros-lyrical-rosidl-default-generators ros-lyrical-ament-cmake \
        colcon-common-extensions cmake ninja make cxx-compiler git numpy scipy setuptools \
    && pixi shell-hook > /opt/ros/activate.sh \
    && pixi clean cache --yes
# The env's activation does not set it, and rosidl generators need it.
ENV ROS_DISTRO=lyrical

# px4_msgs the way PX4's own ROS 2 image makes it: the package skeleton from
# PX4/px4_msgs at the commit PX4 pins in Tools/ros2/ros2.repos, its messages
# replaced by the PX4 tree's, so the type hashes match the firmware.
COPY --from=px4-src /px4/msg /tmp/px4/msg
COPY --from=px4-src /px4/srv /tmp/px4/srv
COPY --from=px4-src /px4/Tools/ros2/ros2.repos /tmp/px4/ros2.repos
WORKDIR /opt/ws
RUN . /opt/ros/activate.sh \
    && ref=$(awk '/px4_msgs:/ {f=1} f && /version:/ {print $2; exit}' /tmp/px4/ros2.repos) \
    && git clone -q https://github.com/PX4/px4_msgs.git src/px4_msgs \
    && git -C src/px4_msgs checkout -q "$ref" \
    && rm -rf src/px4_msgs/.git src/px4_msgs/msg src/px4_msgs/srv \
    && mkdir src/px4_msgs/msg src/px4_msgs/srv \
    && cp /tmp/px4/msg/*.msg /tmp/px4/msg/versioned/*.msg src/px4_msgs/msg/ \
    && cp /tmp/px4/srv/*.srv src/px4_msgs/srv/ \
    && colcon build --packages-select px4_msgs --cmake-args -DBUILD_TESTING=OFF \
    && rm -rf build log /tmp/px4

# This repo's nodes and the platform packages (folders of platforms/ that have a
# package.xml; the rest is only served to Gazebo).
COPY ros/src/px4_companion src/px4_companion
COPY platforms src/platforms
RUN . /opt/ros/activate.sh && . install/setup.sh \
    && colcon build --packages-skip px4_msgs \
    && rm -rf build log

# rmw_zenoh; the router endpoint (ZENOH_CONFIG_OVERRIDE) comes from outside.
ENV RMW_IMPLEMENTATION=rmw_zenoh_cpp

# PLATFORM: a platforms/ package. On the rover pass LAUNCH_ARGS=use_sim_time:=false.
COPY --chmod=755 <<'EOF' /usr/local/bin/companion
#!/bin/sh
. /opt/ros/activate.sh
. /opt/ws/install/setup.sh
exec ros2 launch "${PLATFORM:?set PLATFORM to a platforms/ package}" companion.launch.py $LAUNCH_ARGS
EOF
CMD ["companion"]
