# syntax=docker/dockerfile:1
# The world on gz Jetty with gz-transport's zenoh backend: discovery and data go
# through the zenoh router over TCP instead of multicast, so a native macOS
# `gz sim -g` can attach across Docker Desktop's NAT. Same conda-forge build
# (gz-sim 10.5, zenoh-c 1.9) as the macOS pixi env.
FROM ghcr.io/prefix-dev/pixi:latest

WORKDIR /opt/gz
RUN pixi init --platform linux-aarch64 --platform linux-64 \
    && pixi add "gz-sim=10.5.*" gz-tools \
    && pixi shell-hook > /opt/gz/activate.sh \
    && pixi clean cache --yes

# Rendering sensors (the rover's gpu_lidar) need an EGL/GL implementation: the
# conda env only has the glvnd dispatcher, so without a vendor Ogre segfaults
# the moment such a sensor spawns. Mesa from apt, software (llvmpipe), found by
# conda's glvnd through its vendor file.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libegl-mesa0 libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*
ENV __EGL_VENDOR_LIBRARY_DIRS=/usr/share/glvnd/egl_vendor.d

# gz-transport 15.1.0 with the zenoh fixes not yet released for Jetty; see the
# header of infra/patches/gz-transport15-zenoh-fixes.patch.
COPY infra/build-gz-transport.sh /opt/sim/infra/
COPY infra/patches /opt/sim/infra/patches
RUN ENV_DIR=/opt/gz/.pixi/envs/default /opt/sim/infra/build-gz-transport.sh \
    && pixi clean cache --yes

# platforms/ and worlds/ are mounted under /sim. GZ_PARTITION and the router
# endpoint (GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE) come from compose.
ENV GZ_SIM_RESOURCE_PATH=/sim/platforms:/sim/worlds \
    GZ_TRANSPORT_IMPLEMENTATION=zenoh

# Sim time starts at 0: a large --initial-sim-time wedges the server when a
# sensor is spawned later (gz-sensors catches nextUpdateTime up step by step).
# --headless-rendering: rendering sensors (gpu_lidar) via EGL, no display.
COPY --chmod=755 <<'EOF' /usr/local/bin/sim-world
#!/bin/sh
. /opt/gz/activate.sh
exec gz sim -s -r --headless-rendering "/sim/worlds/${SIM_WORLD:?set SIM_WORLD to a file in worlds/, without .sdf}.sdf"
EOF
CMD ["sim-world"]
