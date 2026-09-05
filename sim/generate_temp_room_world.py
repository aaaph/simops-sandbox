#!/usr/bin/env python3
"""Generate an SDF world: a rectangular room with randomly scattered boxes and cylinders.

Every gap is at least --clearance wide, and a flood fill over the inflated
configuration space proves the whole room stays reachable from the spawn point.
"""

import argparse
import math
import random
import re
import sys
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

from scipy.spatial.transform import Rotation as Rot

p = argparse.ArgumentParser()
p.add_argument("--seed", type=int, default=0)  # same seed -> same map
p.add_argument("--size", type=float, nargs=2, default=[10.0, 8.0], metavar=("X", "Y"))
p.add_argument("--obstacles", type=int, default=28)
p.add_argument("--box-ratio", type=float, default=0.7)  # share of boxes vs cylinders
p.add_argument("--radius", type=float, nargs=2, default=[0.15, 0.4], metavar=("MIN", "MAX"))
p.add_argument("--clearance", type=float)  # default: robot width + 10%
p.add_argument("--platform", default="rover_differential_lidar")
p.add_argument("--spawn-clear", type=float)  # defaults to --clearance
p.add_argument("--robot", default="")  # "" to leave the room empty
p.add_argument("--cell", type=float, default=0.05)  # flood-fill resolution
p.add_argument("-o", "--out", default="worlds/temp_room.sdf")
a = p.parse_args()


def robot_width(platform: str) -> float | None:
    """Widest Y extent of the platform's collision shapes, in metres.

    Every geometry is treated as a box (sphere -> 2r cube, cylinder -> 2r x 2r x l),
    rotated by its link pose, so wheels sticking out past the chassis are counted.
    """
    path = Path(__file__).parent.parent / "platforms" / platform / "model.sdf"
    if not path.exists():
        return None

    def nums(el: ET.Element, tag: str) -> list[float]:
        """Read the numbers in <tag>, empty if it is missing -- SDF leaves plenty optional."""
        child = el.find(tag)
        return [float(x) for x in (child.text or "").split()] if child is not None else []

    def pose_of(el: ET.Element) -> list[float]:
        return (nums(el, "pose") + [0.0] * 6)[:6]

    lo = hi = 0.0
    for link in ET.parse(path).getroot().iter("link"):
        _lx, ly, _lz, lr, lp, lyaw = pose_of(link)
        for col in link.iter("collision"):
            _cx, cy, _cz, cr, cp, cyaw = pose_of(col)
            geom = col.find("geometry")
            if geom is None:
                continue
            if (b := geom.find("box")) is not None:
                ex, ey, ez = [v / 2 for v in nums(b, "size")]
            elif (c := geom.find("cylinder")) is not None:
                ex = ey = nums(c, "radius")[0]
                ez = nums(c, "length")[0] / 2
            elif (s := geom.find("sphere")) is not None:
                ex = ey = ez = nums(s, "radius")[0]
            else:
                continue  # meshes: no cheap extent, chassis boxes cover us

            # row of the rotation matrix that maps body axes onto world Y
            row = Rot.from_euler("xyz", [lr + cr, lp + cp, lyaw + cyaw]).as_matrix()[1]
            centre = ly + cy
            reach = abs(row[0]) * ex + abs(row[1]) * ey + abs(row[2]) * ez
            lo, hi = min(lo, centre - reach), max(hi, centre + reach)
    return hi - lo


WALL_H, WALL_T = 2.5, 0.15
sx, sy = a.size
rng = random.Random(a.seed)
if a.clearance is None:
    w = robot_width(a.platform)
    if w is None:
        p.error(f"platform '{a.platform}' not found; pass --clearance explicitly")
    a.clearance = w * 1.1
    print(f"platform {a.platform}: width {w:.2f} m -> clearance {a.clearance:.2f} m")
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
    print(f"warning: fit only {len(obs)}/{a.obstacles}, room too small or --clearance too big")

# --- the guarantee: erode free space by the robot radius, flood fill from spawn,
# --- and require that nothing free is cut off
rad = a.clearance / 2
nx, ny = int(sx / a.cell), int(sy / a.cell)


def free(i: int, j: int) -> bool:
    """Report whether cell (i, j) is clear of walls and obstacles for the eroded robot."""
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


def gui_section() -> str:
    """Default Gazebo GUI plus the KeyPublisher the arrow-key triggers need.

    A <gui> block in the world *replaces* the default layout, so declaring only
    KeyPublisher leaves a window with no 3D view. Reuse the shipped gui.config
    instead of hand-maintaining the plugin list.
    """
    key_pub = '  <plugin filename="KeyPublisher" name="Key Publisher"/>'
    found = sorted(Path(sys.prefix).glob("share/gz/gz-sim*/gui/gui.config"))
    if not found:
        print("warning: gui.config not found, window will have no 3D view")
        return f'<gui fullscreen="0">\n{key_pub}\n    </gui>'
    body = found[-1].read_text()
    body = re.sub(r"<\?xml[^>]*\?>", "", body).strip()
    return f'<gui fullscreen="0">\n{body}\n{key_pub}\n    </gui>'


def start_marker(radius: float) -> str:
    """Visual-only disc at the origin: where the robot starts and odom is zeroed."""
    return f"""    <model name="start_marker">
      <static>true</static>
      <pose>0 0 0.005 0 0 0</pose>
      <link name="link">
        <visual name="v">
          <geometry><cylinder><radius>{radius:.3f}</radius><length>0.01</length></cylinder></geometry>
          <material>
            <ambient>0.8 0.1 0.1 1</ambient>
            <diffuse>0.8 0.1 0.1 1</diffuse>
            <emissive>0.3 0.0 0.0 1</emissive>
          </material>
        </visual>
      </link>
    </model>"""


def model(name: str, x: float, y: float, z: float, yaw: float, geom: str, rgba: str) -> str:
    """One static SDF model: same geometry for collision and visual."""
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

parts.append(start_marker(a.clearance / 2 * 1.2))

robot = (
    f"""    <include>\n      <uri>model://{a.robot}</uri>\n      <pose>0 0 0 0 0 0</pose>\n    </include>\n"""
    if a.robot
    else ""
)

with Path(a.out).open("w") as f:
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
    <!-- IMU sensors are not rendering sensors, so Sensors above never runs them -->
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>

    {gui_section()}

    <!-- arrow keys -> /cmd_vel -->
    <plugin filename="gz-sim-triggered-publisher-system"
            name="gz::sim::systems::TriggeredPublisher">
      <input type="gz.msgs.Int32" topic="/keyboard/keypress">
        <match field="data">16777235</match>
      </input>
      <output type="gz.msgs.Twist" topic="/cmd_vel">
        linear: {{x: 0.5}}, angular: {{z: 0.0}}
      </output>
    </plugin>
    <plugin filename="gz-sim-triggered-publisher-system"
            name="gz::sim::systems::TriggeredPublisher">
      <input type="gz.msgs.Int32" topic="/keyboard/keypress">
        <match field="data">16777237</match>
      </input>
      <output type="gz.msgs.Twist" topic="/cmd_vel">
        linear: {{x: -0.5}}, angular: {{z: 0.0}}
      </output>
    </plugin>
    <plugin filename="gz-sim-triggered-publisher-system"
            name="gz::sim::systems::TriggeredPublisher">
      <input type="gz.msgs.Int32" topic="/keyboard/keypress">
        <match field="data">16777234</match>
      </input>
      <output type="gz.msgs.Twist" topic="/cmd_vel">
        linear: {{x: 0.0}}, angular: {{z: 0.5}}
      </output>
    </plugin>
    <plugin filename="gz-sim-triggered-publisher-system"
            name="gz::sim::systems::TriggeredPublisher">
      <input type="gz.msgs.Int32" topic="/keyboard/keypress">
        <match field="data">16777236</match>
      </input>
      <output type="gz.msgs.Twist" topic="/cmd_vel">
        linear: {{x: 0.0}}, angular: {{z: -0.5}}
      </output>
    </plugin>
    <plugin filename="gz-sim-triggered-publisher-system"
            name="gz::sim::systems::TriggeredPublisher">
      <input type="gz.msgs.Int32" topic="/keyboard/keypress">
        <match field="data">32</match>
      </input>
      <output type="gz.msgs.Twist" topic="/cmd_vel">
        linear: {{x: 0.0}}, angular: {{z: 0.0}}
      </output>
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
        <collision name="c">
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
        </collision>
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
    f"clearance {a.clearance:.2f} m verified, seed {a.seed}"
)
