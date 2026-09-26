# syntax=docker/dockerfile:1
# PX4 SITL with the zenoh module (px4_sitl_zenoh), built against the same
# conda-forge gz Jetty as world.Dockerfile: its gz_bridge talks to the world
# over gz-transport's zenoh backend, and PX4's own topics reach rmw_zenoh.
# Point PX4_REPO/PX4_REF at a fork to build a branch.
ARG PX4_REPO=https://github.com/PX4/PX4-Autopilot.git
ARG PX4_REF=main

FROM scratch AS px4-src
ARG PX4_REPO PX4_REF
# .git stays: the PX4 build runs git describe and checks its submodules.
ADD --keep-git-dir=true ${PX4_REPO}#${PX4_REF} /px4

FROM ghcr.io/prefix-dev/pixi:0.81.0

# PX4 builds its idlc host tool with a hardcoded /usr/bin/gcc behind ccache
# (msg/CMakeLists.txt); PX4 itself builds with the conda toolchain below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev ccache \
    && rm -rf /var/lib/apt/lists/*

# gz Jetty for gz_bridge and the gz CLI that PX4's startup script calls, plus
# the toolchain (OpenCV 4: PX4 always builds its optical-flow gz plugin, which
# still includes the C API headers OpenCV 5 dropped);
# cached until PX4's Python requirements change.
WORKDIR /opt/gz
RUN pixi init --platform linux-aarch64 --platform linux-64 \
    && pixi add "gz-sim=10.5.*" gz-tools cmake ninja make cxx-compiler git "python=3.12" pip \
    "libopencv=4.13" pkg-config \
    && pixi shell-hook > /opt/gz/activate.sh \
    && pixi clean cache --yes
COPY --from=px4-src /px4/Tools/setup/requirements.txt /tmp/px4-requirements.txt
RUN . /opt/gz/activate.sh \
    && python -m pip install --no-cache-dir -r /tmp/px4-requirements.txt

COPY --from=px4-src /px4 /px4
RUN . /opt/gz/activate.sh \
    && cmake -S /px4 -B /px4/build/px4_sitl_zenoh -G Ninja \
    -DCONFIG=px4_sitl_zenoh -DCMAKE_PREFIX_PATH=$CONDA_PREFIX \
    && cmake --build /px4/build/px4_sitl_zenoh

# gz-transport 15.1.0 with the zenoh fixes not yet released for Jetty; see the
# header of infra/patches/gz-transport15-zenoh-fixes.patch. Swapped in after the
# PX4 build: the patch keeps the ABI, so a patch change does not rebuild PX4.
COPY infra/build-gz-transport.sh /opt/sim/infra/
COPY infra/patches /opt/sim/infra/patches
RUN ENV_DIR=/opt/gz/.pixi/envs/default /opt/sim/infra/build-gz-transport.sh \
    && pixi clean cache --yes

# GZ_PARTITION and the router endpoint come from compose, as for the world.
ENV GZ_TRANSPORT_IMPLEMENTATION=zenoh

# gz-transport 15.1.0 over zenoh can wait forever for a service reply that was
# lost on the way back (fixed upstream in gz-transport#868, not in Jetty yet),
# and PX4's startup script then blocks on `gz service -s .../create` although
# the world has already spawned the model. Bound every `gz service` call; drop
# this wrapper once a gz-transport 15 release carries #868.
COPY --chmod=755 <<'EOF' /opt/sim/bin/gz
#!/bin/sh
if [ "$1" = service ]; then
	exec timeout 15 /opt/gz/.pixi/envs/default/bin/gz "$@"
fi
exec /opt/gz/.pixi/envs/default/bin/gz "$@"
EOF

# PX4 joining a running world: it spawns its vehicle (PX4_SIM_MODEL, looked up
# under PX4_GZ_MODELS by the world's gz server) and drives it over gz-transport.
COPY --chmod=755 <<'EOF' /usr/local/bin/sim-px4
#!/bin/sh
set -e
. /opt/gz/activate.sh
export PATH=/opt/sim/bin:$PATH  # the bounded gz wrapper above
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
