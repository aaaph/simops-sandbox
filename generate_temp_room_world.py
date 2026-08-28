#!/usr/bin/env python3
"""Generate an SDF world: a rectangular room with randomly scattered boxes and cylinders.

Every gap is at least --clearance wide, and a flood fill over the inflated
configuration space proves the whole room stays reachable from the spawn point.
"""

import argparse
import math
import random
from collections import deque

p = argparse.ArgumentParser()
p.add_argument("--seed", type=int, default=0)  # same seed -> same map
p.add_argument("--size", type=float, nargs=2, default=[10.0, 8.0], metavar=("X", "Y"))
p.add_argument("--obstacles", type=int, default=14)
p.add_argument("--box-ratio", type=float, default=0.7)  # share of boxes vs cylinders
p.add_argument(
    "--radius", type=float, nargs=2, default=[0.15, 0.4], metavar=("MIN", "MAX")
)
p.add_argument(
    "--clearance", type=float, default=0.8
)  # narrowest corridor the robot must fit
p.add_argument("--spawn-clear", type=float)  # defaults to --clearance
p.add_argument("--robot", default="vehicle_blue")  # "" to leave the room empty
p.add_argument("--cell", type=float, default=0.05)  # flood-fill resolution
p.add_argument("-o", "--out", default="worlds/temp_room.sdf")
a = p.parse_args()

WALL_H, WALL_T = 2.5, 0.15
sx, sy = a.size
rng = random.Random(a.seed)
a.spawn_clear = a.spawn_clear if a.spawn_clear is not None else a.clearance
# sampler keeps two extra cells of slack so the discretised check below can't
# fail on a corridor that is passable by a hair
slack = a.clearance + 2 * a.cell

# obstacles are sampled as discs; a box is drawn inscribed in its disc, so the
# clearance math holds for any yaw without needing real box-box distance
obs = []
for _ in range(a.obstacles * 200):
    if len(obs) == a.obstacles:
        break
    r = rng.uniform(*a.radius)
    m = r + WALL_T / 2 + slack
    x, y = rng.uniform(-sx / 2 + m, sx / 2 - m), rng.uniform(-sy / 2 + m, sy / 2 - m)
    if math.hypot(x, y) < a.spawn_clear + r:
        continue
    if any(math.hypot(x - px, y - py) < r + pr + slack for px, py, pr, _, _ in obs):
        continue
    is_box = rng.random() < a.box_ratio
    obs.append((x, y, r, is_box, rng.uniform(0, math.pi / 2)))

if len(obs) < a.obstacles:
    print(
        f"warning: fit only {len(obs)}/{a.obstacles}, room too small or --clearance too big"
    )

# --- the guarantee: erode free space by the robot radius, flood fill from spawn,
# --- and require that nothing free is cut off
rad = a.clearance / 2
nx, ny = int(sx / a.cell), int(sy / a.cell)


def free(i, j):
    x, y = -sx / 2 + (i + 0.5) * a.cell, -sy / 2 + (j + 0.5) * a.cell
    if abs(x) > sx / 2 - WALL_T / 2 - rad or abs(y) > sy / 2 - WALL_T / 2 - rad:
        return False
    return all(math.hypot(x - ox, y - oy) > r + rad for ox, oy, r, _, _ in obs)


grid = [[free(i, j) for j in range(ny)] for i in range(nx)]
seen = [[False] * ny for _ in range(nx)]
start = (nx // 2, ny // 2)
q = deque([start])
seen[start[0]][start[1]] = True
while q:
    i, j = q.popleft()
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        u, v = i + di, j + dj
        if 0 <= u < nx and 0 <= v < ny and grid[u][v] and not seen[u][v]:
            seen[u][v] = True
            q.append((u, v))

unreachable = sum(grid[i][j] and not seen[i][j] for i in range(nx) for j in range(ny))
assert unreachable == 0, f"{unreachable} free cells are walled off from the spawn point"


def model(name, x, y, z, yaw, geom, rgba):
    return f"""    <model name="{name}">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 {yaw:.3f}</pose>
      <link name="link">
        <collision name="c"><geometry>{geom}</geometry></collision>
        <visual name="v">
          <geometry>{geom}</geometry>
          <material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse></material>
        </visual>
      </link>
    </model>"""


h = WALL_H / 2
parts = [
    model(
        "wall_n",
        0,
        sy / 2,
        h,
        0,
        f"<box><size>{sx + WALL_T:.3f} {WALL_T} {WALL_H}</size></box>",
        "0.7 0.7 0.7 1",
    ),
    model(
        "wall_s",
        0,
        -sy / 2,
        h,
        0,
        f"<box><size>{sx + WALL_T:.3f} {WALL_T} {WALL_H}</size></box>",
        "0.7 0.7 0.7 1",
    ),
    model(
        "wall_e",
        sx / 2,
        0,
        h,
        0,
        f"<box><size>{WALL_T} {sy:.3f} {WALL_H}</size></box>",
        "0.7 0.7 0.7 1",
    ),
    model(
        "wall_w",
        -sx / 2,
        0,
        h,
        0,
        f"<box><size>{WALL_T} {sy:.3f} {WALL_H}</size></box>",
        "0.7 0.7 0.7 1",
    ),
]
oh = WALL_H / 2  # obstacles are half wall height, tall enough for any lidar plane
for n, (x, y, r, is_box, yaw) in enumerate(obs):
    if is_box:
        # inscribe the box in the disc of radius r: half-diagonal == r
        ang = rng.uniform(0.6, 1.0)  # aspect, keeps them from being needle-thin
        w, d = 2 * r * math.cos(ang), 2 * r * math.sin(ang)
        geom, rgba = (
            f"<box><size>{w:.3f} {d:.3f} {oh:.3f}</size></box>",
            "0.8 0.5 0.2 1",
        )
    else:
        geom, rgba = (
            f"<cylinder><radius>{r:.3f}</radius><length>{oh:.3f}</length></cylinder>",
            "0.2 0.4 0.8 1",
        )
    parts.append(model(f"obs_{n}", x, y, oh / 2, yaw, geom, rgba))

robot = (
    f"""    <include>\n      <uri>model://{a.robot}</uri>\n      <pose>0 0 0 0 0 0</pose>\n    </include>\n"""
    if a.robot
    else ""
)

with open(a.out, "w") as f:
    f.write(f"""<?xml version="1.0"?>
<sdf version="1.8">
  <world name="room">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="c"><geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry></collision>
        <visual name="v">
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
          <material><ambient>0.8 0.8 0.8 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material>
        </visual>
      </link>
    </model>

{chr(10).join(parts)}
{robot}  </world>
</sdf>
""")
boxes = sum(o[3] for o in obs)
print(
    f"{a.out}: {boxes} boxes + {len(obs) - boxes} cylinders, {sx}x{sy} m, "
    f"clearance {a.clearance} m verified, seed {a.seed}"
)
