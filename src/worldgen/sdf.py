"""SDF as text: the envelope every worldgen world shares and the XML of one static model.

Physics, sensor plugins, the GUI, the arrow-key drive triggers, the sun and the ground plane are
the same regardless of what a world holds (a room's walls and obstacles, an open field's start
marker, a future maze's corridors); `envelope()` wraps them around the models. What the models
are is `worldgen.world`'s concern; worldgen knows nothing of simops.
"""

import re
import sys
from pathlib import Path


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


def envelope(name: str, models: list[str]) -> str:
    """Wrap `models` (model/light XML snippets) in the envelope every world type shares."""
    return f"""<?xml version="1.0"?>
<sdf version="1.8">
  <world name="{name}">
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

{chr(10).join(models)}
  </world>
</sdf>
"""
