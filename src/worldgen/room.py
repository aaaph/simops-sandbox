"""Rooms: an SDF world with walls and randomly scattered boxes and cylinders.

Every gap is at least `clearance` wide, and a flood fill over the inflated configuration space
proves the whole room stays reachable from the spawn point (the origin). The same seed gives
the same room. worldgen knows nothing of simops: the caller says how wide the robot is.
"""

import math
import random
import re
import sys
from collections import deque
from pathlib import Path

WALL_H, WALL_T = 2.5, 0.15

Obstacle = tuple[float, float, float, bool, float]  # x, y, radius, is a box, yaw


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


def place_obstacles(
    rng: random.Random,
    size: tuple[float, float],
    count: int,
    radius: tuple[float, float],
    box_ratio: float,
    clearance: float,
    spawn_clear: float,
    cell: float,
) -> list[Obstacle]:
    """Sample obstacles as discs, every gap at least `clearance` plus two cells of slack.

    A box is later drawn inscribed in its disc, so the clearance math holds for any yaw.
    """
    sx, sy = size
    slack = clearance + 2 * cell  # so the discretised check cannot fail on a corridor passable by a hair
    obs: list[Obstacle] = []
    for _ in range(count * 200):
        if len(obs) == count:
            break
        r = rng.uniform(*radius)
        m = r + WALL_T / 2 + slack
        x, y = rng.uniform(-sx / 2 + m, sx / 2 - m), rng.uniform(-sy / 2 + m, sy / 2 - m)
        if math.hypot(x, y) < spawn_clear + r:
            continue
        if any(math.hypot(x - px, y - py) < r + pr + slack for px, py, pr, _, _ in obs):
            continue
        is_box = rng.random() < box_ratio
        obs.append((x, y, r, is_box, rng.uniform(0, math.pi / 2)))
    return obs


def unreachable_cells(size: tuple[float, float], obs: list[Obstacle], clearance: float, cell: float) -> int:
    """Count free cells a robot `clearance` wide cannot reach from the origin (flood fill)."""
    sx, sy = size
    rad = clearance / 2
    nx, ny = int(sx / cell), int(sy / cell)

    def free(i: int, j: int) -> bool:
        x, y = -sx / 2 + (i + 0.5) * cell, -sy / 2 + (j + 0.5) * cell
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
    return sum(grid[i][j] and not seen[i][j] for i in range(nx) for j in range(ny))


def world_sdf(rng: random.Random, size: tuple[float, float], obs: list[Obstacle], clearance: float) -> str:
    """Write the room as an SDF world: walls, obstacles, a start marker, plugins for gz and PX4."""
    sx, sy = size
    h = WALL_H / 2
    wall_x = f"<box><size>{sx + WALL_T:.3f} {WALL_T} {WALL_H}</size></box>"
    wall_y = f"<box><size>{WALL_T} {sy:.3f} {WALL_H}</size></box>"
    grey = "0.7 0.7 0.7 1"
    parts = [
        model("wall_n", 0, sy / 2, h, 0, wall_x, grey),
        model("wall_s", 0, -sy / 2, h, 0, wall_x, grey),
        model("wall_e", sx / 2, 0, h, 0, wall_y, grey),
        model("wall_w", -sx / 2, 0, h, 0, wall_y, grey),
    ]
    oh = WALL_H / 2  # obstacles are half wall height, tall enough for any lidar plane
    for n, (x, y, r, is_box, yaw) in enumerate(obs):
        if is_box:
            # inscribe the box in the disc of radius r: half-diagonal == r
            ang = rng.uniform(0.6, 1.0)  # aspect, keeps them from being needle-thin
            w, d = 2 * r * math.cos(ang), 2 * r * math.sin(ang)
            geom, rgba = f"<box><size>{w:.3f} {d:.3f} {oh:.3f}</size></box>", "0.8 0.5 0.2 1"
        else:
            geom = f"<cylinder><radius>{r:.3f}</radius><length>{oh:.3f}</length></cylinder>"
            rgba = "0.2 0.4 0.8 1"
        parts.append(model(f"obs_{n}", x, y, oh / 2, yaw, geom, rgba))
    parts.append(start_marker(clearance / 2 * 1.2))
    return f"""<?xml version="1.0"?>
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
    <!-- baro, mag and GPS for PX4: a world that lists its own plugins skips server.config -->
    <plugin filename="gz-sim-air-pressure-system" name="gz::sim::systems::AirPressure"/>
    <plugin filename="gz-sim-magnetometer-system" name="gz::sim::systems::Magnetometer"/>
    <plugin filename="gz-sim-navsat-system" name="gz::sim::systems::NavSat"/>
    <spherical_coordinates>
      <surface_model>EARTH_WGS84</surface_model>
      <world_frame_orientation>ENU</world_frame_orientation>
      <latitude_deg>47.397971057728974</latitude_deg>
      <longitude_deg>8.546163739800146</longitude_deg>
      <elevation>0</elevation>
    </spherical_coordinates>

    {gui_section()}

    <!-- arrow keys -> /cmd_vel; space or s -> stop. Codes are Qt keys, as KeyPublisher sends them -->
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
    <plugin filename="gz-sim-triggered-publisher-system"
            name="gz::sim::systems::TriggeredPublisher">
      <input type="gz.msgs.Int32" topic="/keyboard/keypress">
        <match field="data">83</match>
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
  </world>
</sdf>
"""


def generate(
    out: Path,
    *,
    clearance: float,
    seed: int = 0,
    size: tuple[float, float] = (10.0, 8.0),
    obstacles: int = 28,
    box_ratio: float = 0.7,
    radius: tuple[float, float] = (0.15, 0.4),
    spawn_clear: float | None = None,
    cell: float = 0.05,
) -> str:
    """Generate a room, write it to `out` and return a one-line summary.

    `clearance` is the narrowest gap a robot needs (its width plus a margin); `spawn_clear`, the
    free radius around the origin, defaults to it. Raises ValueError if the room is not reachable.
    """
    rng = random.Random(seed)
    spawn = spawn_clear if spawn_clear is not None else clearance
    obs = place_obstacles(rng, size, obstacles, radius, box_ratio, clearance, spawn, cell)
    if (walled_off := unreachable_cells(size, obs, clearance, cell)) != 0:
        msg = f"{walled_off} free cells are walled off from the spawn point"
        raise ValueError(msg)
    out.write_text(world_sdf(rng, size, obs, clearance))
    boxes = sum(o[3] for o in obs)
    short = len(obs) < obstacles
    fit = f" (fit only {len(obs)}/{obstacles}: room too small or clearance too big)" if short else ""
    return (
        f"{out}: {boxes} boxes + {len(obs) - boxes} cylinders, {size[0]}x{size[1]} m, "
        f"clearance {clearance:.2f} m verified, seed {seed}{fit}"
    )
