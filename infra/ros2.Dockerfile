FROM ros:lyrical-ros-base

RUN apt-get update && apt-get install -y \
    ros-lyrical-rmw-zenoh-cpp \
    git \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# px4_msgs: message definitions for the /fmu/* topics. The branch must match the
# PX4 version, RIHS01 type hashes are part of the zenoh key expression.
RUN mkdir -p /ws/src \
    && git clone --depth 1 https://github.com/PX4/px4_msgs.git /ws/src/px4_msgs \
    && . /opt/ros/lyrical/setup.sh \
    && cd /ws && colcon build --packages-select px4_msgs \
    && rm -rf /ws/build /ws/log

ENV RMW_IMPLEMENTATION=rmw_zenoh_cpp
ENV ROS_DOMAIN_ID=0

RUN echo "source /opt/ros/lyrical/setup.bash" >> ~/.bashrc \
    && echo "source /ws/install/setup.bash" >> ~/.bashrc
