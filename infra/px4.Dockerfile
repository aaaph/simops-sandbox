# syntax=docker/dockerfile:1
# gz Harmonic + PX4 SITL built with the zenoh module (px4_sitl_zenoh), so PX4
# topics reach rmw_zenoh without an XRCE agent. Upstream images ship only
# px4_sitl_default (XRCE). Point PX4_REPO/PX4_REF at a fork to build a branch.
ARG PX4_REPO=https://github.com/PX4/PX4-Autopilot.git
ARG PX4_REF=main

FROM scratch AS px4-src
ARG PX4_REPO PX4_REF
ADD --keep-git-dir=true ${PX4_REPO}#${PX4_REF} /px4

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive RUNS_IN_DOCKER=true

COPY --from=px4-src /px4/Tools/setup /tmp/px4-setup
RUN bash /tmp/px4-setup/ubuntu.sh --no-nuttx \
    && rm -rf /var/lib/apt/lists/* /tmp/px4-setup

COPY --from=px4-src /px4 /px4
RUN make -C /px4 px4_sitl_zenoh

# PX4 joining a running world: it spawns its vehicle (PX4_SIM_MODEL, looked up
# under PX4_GZ_MODELS by the world's gz server) and drives it over gz-transport.
COPY --chmod=755 <<'EOF' /usr/local/bin/sim-px4
#!/bin/sh
set -e
B=/px4/build/px4_sitl_zenoh

# Docker Desktop: localhost stays in the VM, so point MAVLink at the host's QGC.
HOST_IP=$(getent ahostsv4 host.docker.internal | awk '/STREAM/ {print $1; exit}')
if [ -n "$HOST_IP" ]; then
	sed -i -E "s/(mavlink start -x)( -t [^ ]+)? -u/\1 -t $HOST_IP -u/" "$B/etc/init.d-posix/px4-rc.mavlink"
fi

export PX4_GZ_STANDALONE=1
export PX4_PARAM_ZENOH_ENABLE=1  # px4_sitl_zenoh dials the router on localhost:7447
cd "$B/rootfs"
exec ../bin/px4 -d
EOF
CMD ["sim-px4"]
