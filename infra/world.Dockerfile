# syntax=docker/dockerfile:1
# The world: gz Harmonic server only. Robots are part of the world file; the
# autopilot runs in its own container and attaches to them. Keep the gz version
# in step with px4.Dockerfile, whose gz_bridge talks to this server.
FROM ubuntu:24.04 AS world
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates lsb-release wget \
    && wget -q https://packages.osrfoundation.org/gazebo.gpg \
        -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/gazebo-stable.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gz-harmonic \
    && rm -rf /var/lib/apt/lists/*

# platforms/ and worlds/ are mounted under /sim.
ENV GZ_SIM_RESOURCE_PATH=/sim/platforms:/sim/worlds

# Sim time starts at 0: a large --initial-sim-time wedges the server when a
# sensor is spawned later (gz-sensors catches nextUpdateTime up step by step).
# --headless-rendering: rendering sensors (gpu_lidar) via EGL, no display.
COPY --chmod=755 <<'EOF' /usr/local/bin/sim-world
#!/bin/sh
exec gz sim -s -r --headless-rendering "/sim/worlds/${SIM_WORLD:?set SIM_WORLD to a file in worlds/, without .sdf}.sdf"
EOF
CMD ["sim-world"]

# The gz GUI for the world above, in a browser: macOS cannot attach a native
# GUI across Docker Desktop's NAT, so it runs here on a virtual display and
# noVNC serves it on :6080. Rendering is software (Mesa llvmpipe).
FROM world AS gui
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc python3-websockify \
    && rm -rf /var/lib/apt/lists/*

COPY --chmod=755 <<'EOF' /usr/local/bin/sim-gui
#!/bin/sh
# A stopped container keeps /tmp: drop the previous run's display lock, or
# Xvfb refuses to start and the GUI finds no display.
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
Xvfb :99 -screen 0 1600x900x24 &
until [ -e /tmp/.X11-unix/X99 ]; do sleep 0.1; done
export DISPLAY=:99
x11vnc -display :99 -forever -shared -nopw -quiet &
websockify --web /usr/share/novnc 6080 localhost:5900 &
exec gz sim -g
EOF
CMD ["sim-gui"]
