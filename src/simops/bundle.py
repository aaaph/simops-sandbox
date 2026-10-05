"""The bundle: an environment built for docker compose in build/<name>/."""

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict

from simops import ROOT
from simops.agent import entity_factory
from simops.environment import Environment
from simops.world import EmptySpec, WorldFile
from worldgen import empty, room
from worldgen.world import SdfWorld

if TYPE_CHECKING:
    from simops.firmware import PX4Firmware


def zenoh_gz(port: int = 7447) -> str:
    """gz-transport's zenoh config: every peer goes through the router, no multicast."""
    return f'mode="peer";connect/endpoints=["tcp/localhost:{port}"];scouting/multicast/enabled=false'


def compose(
    environment: Environment, world_stem: str, world_name: str, firmware: dict[PX4Firmware, tuple[str, str]]
) -> dict:
    """Describe the environment as a compose file; paths are relative to the bundle directory.

    `firmware` maps each platform's PX4 firmware to what it resolved to: (tag or commit, commit).
    """
    name = environment.name
    gz = {"GZ_PARTITION": name, "GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE": zenoh_gz()}
    port = environment.network.router_port

    def beside_router(*restart_with: str) -> dict:
        # Sharing the router's network namespace (localhost:7447 is the router): when the
        # router restarts, a container is left in the old namespace with no network, so it
        # restarts with it -- and with the world, which loses the agent when it restarts.
        deps = {s: {"condition": "service_started", "restart": True} for s in ("zenoh-router", *restart_with)}
        return {"network_mode": "service:zenoh-router", "depends_on": deps}

    after_spawn = beside_router("world")
    after_spawn["depends_on"]["spawn"] = {"condition": "service_completed_successfully", "restart": True}

    world_image = {
        "build": {"context": str(ROOT), "dockerfile": "infra/world.Dockerfile"},
        "image": "simops-sandbox-world",
    }
    # PX4 per agent: attaches to its agent once `spawn` has put it in the world; /fmu/* on the router
    autopilots = {
        f"px4-{agent}": {
            "build": {
                "context": str(ROOT),
                "dockerfile": "infra/px4.Dockerfile",
                "args": {
                    "PX4_REPO": spec.platform.px4.repo,
                    "PX4_REF": firmware[spec.platform.px4.firmware][0],
                },
            },
            # one image per commit, however it was named and by however many platforms
            "image": f"simops-sandbox-px4:{firmware[spec.platform.px4.firmware][1][:12]}",
            **after_spawn,
            "environment": {
                **gz,
                "PX4_GZ_WORLD": world_name,
                "PX4_GZ_MODEL_NAME": agent,
                "PX4_SYS_AUTOSTART": str(spec.platform.px4.airframe),
                "PX4_INSTANCE": str(i),
                "PX4_MAVLINK_PORT": str(environment.network.mavlink_port + i),  # its API link, on the host
                **({"PX4_ZENOH_NAMESPACE": agent} if environment.namespaces else {}),
            },
        }
        for i, (agent, spec) in enumerate(environment.agents.items())
    }
    ros = {"build": {"context": str(ROOT), "dockerfile": "infra/ros.Dockerfile"}, "image": "simops-sandbox-ros"}
    services = {
        "zenoh-router": {
            **ros,
            "restart": "always",
            "ports": [f"{port}:7447/tcp", f"{port}:7447/udp"],
            # connects and sessions at debug, the rest at info: docker compose logs zenoh-router
            "environment": {
                "RUST_LOG": "zenoh=info,zenoh_link_tcp::unicast=debug,"
                "zenoh_transport::unicast::manager=debug,zenoh::net::routing::dispatcher::face=debug"
            },
            "command": "zenoh-router",
        },
        "world": {
            **world_image,
            **beside_router(),
            "environment": {"SIM_WORLD": world_stem, **gz},
            "volumes": ["./worlds:/sim/worlds:ro", "./platforms:/sim/platforms:ro"],
        },
        # adds the agents to the running world, exits; again whenever the world restarts
        "spawn": {
            **world_image,
            **beside_router("world"),
            "environment": gz,
            "volumes": ["./platforms:/sim/platforms:ro", "./spawn.sh:/sim/spawn.sh:ro"],
            "command": ["sh", "/sim/spawn.sh"],
        },
        **autopilots,
        # the sim's stand-in for the agents' sensor drivers: the world's clock and their entries, merged
        "sim-sensors": {
            **ros,
            **beside_router("world"),
            "environment": {
                **gz,
                "BRIDGE_CONFIG": "/sim/bridge.yaml",
                "ZENOH_CONFIG_OVERRIDE": 'mode="client";connect/endpoints=["tcp/localhost:7447"]',
            },
            "volumes": ["./bridge.yaml:/sim/bridge.yaml:ro"],
            "command": "sim-sensors",
        },
    }
    # how a running session is found from its containers, however the bundle was started
    mav = environment.network.mavlink_port
    labels = {
        "simops.session": name,
        "simops.router_port": str(port),
        "simops.mavlink_ports": f"{mav}-{mav + len(environment.agents) - 1}",
    }
    return {"name": name, "services": {s: spec | {"labels": labels} for s, spec in services.items()}}


def namespaced(agent: str, topic: str) -> str:
    """Put a gz or ROS topic under /<agent>; relative gz topics are absolute from the root."""
    return f"/{agent}/{topic.lstrip('/')}"


SPAWN = """#!/bin/sh
# First the world, then the agents: add the environment's agents to the running world.
# Generated by simops (src/simops/bundle.py).
set -e
. /opt/gz/activate.sh
W={world}

present() {{
	timeout 10 gz topic -e -t "/world/$W/pose/info" -n 1 | grep -q "name: \\"$1\\""
}}

# The reply to create can get lost over zenoh (gz-transport#868) although the world
# acted on it: do not wait on the reply, look for the model in the world instead.
spawn() {{
	for _ in 1 2 3 4 5; do
		present "$1" && {{ echo "$1 is in /world/$W"; return 0; }}
		timeout 10 gz service -s "/world/$W/create" --reqtype gz.msgs.EntityFactory \\
			--reptype gz.msgs.Boolean --timeout 5000 --req "$2" >/dev/null 2>&1 || true
		sleep 2
	done
	echo "$1 did not appear in /world/$W" >&2
	return 1
}}

until timeout 10 gz topic -e -t "/world/$W/pose/info" -n 1 >/dev/null 2>&1; do sleep 1; done
{agents}
"""


def agents(environment: Environment) -> tuple[list[str], list[dict], dict[str, Path], dict[str, str]]:
    """Say how to spawn every agent; return the spawn lines, everyone's bridge entries, and the copies.

    With namespaces, each agent gets its own copy of its platform, `<p>.<agent>`, whose model's gz
    topics sit under /<agent>, and the bridge maps them to ROS names under /<agent> too. The copies
    are the model directories to copy and the rewritten model of each, by its path in platforms/.
    """
    bridge, spawns, copies, models = [], [], {}, {}
    for agent, spec in environment.agents.items():
        platform, sdf = spec.platform.name, spec.platform.model.name
        entries = [dict(e) for e in spec.platform.bridge]  # the platform's own, shared by its agents
        if environment.namespaces:
            model = ET.parse(spec.platform.model)
            for el in model.iter():
                if el.tag in ("topic", "odom_topic") and el.text:  # sensors, odometry: not model-scoped
                    el.text = namespaced(agent, el.text)
            platform = f"{platform}.{agent}"
            copies[platform] = spec.platform.model.parent
            models[f"{platform}/{sdf}"] = ET.tostring(
                model.getroot(), encoding="us-ascii", xml_declaration=True
            ).decode()
            for e in entries:
                e["gz_topic_name"] = namespaced(agent, e["gz_topic_name"])
                e["ros_topic_name"] = namespaced(agent, e["ros_topic_name"])
        bridge += [e for e in entries if e not in bridge]
        request = entity_factory(agent, f"/sim/platforms/{platform}/{sdf}", spec.pose)
        spawns.append(f"spawn {agent} '{request}'")
    return spawns, bridge, copies, models


class Bundle(BaseModel):
    """An environment built for docker compose; in memory until `write` puts it in a directory."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    environment: Environment
    world_name: str
    world: SdfWorld | Path  # generated, or the ready-made file to copy
    world_file: str  # its name in worlds/
    world_summary: str | None  # what worldgen generated, None for a ready-made file
    compose: dict
    spawn: str
    bridge: list[dict]
    platforms: dict[str, Path]  # name in platforms/ -> the model directory to copy
    models: dict[str, str]  # path in platforms/ (<name>/<model file>) -> the rewritten model
    firmware_lines: list[str]

    def write(self, out: Path) -> Path:
        """Write compose.yaml, spawn.sh, bridge.yaml, worlds/ and platforms/ to `out`, replacing it."""
        shutil.rmtree(out, ignore_errors=True)
        (out / "worlds").mkdir(parents=True)
        for name, source in self.platforms.items():
            shutil.copytree(source, out / "platforms" / name)
        for path, model in self.models.items():
            (out / "platforms" / path).write_text(model)
        sdf = out / "worlds" / self.world_file
        if isinstance(self.world, Path):
            shutil.copy(self.world, sdf)
        else:
            sdf.write_text(self.world.sdf())
        if self.world_summary is not None:
            print(f"world: {self.world_summary}", flush=True)
        for line in self.firmware_lines:
            print(line, flush=True)
        (out / "spawn.sh").write_text(self.spawn)
        (out / "bridge.yaml").write_text(yaml.safe_dump(self.bridge, sort_keys=False))
        (out / "compose.yaml").write_text(yaml.safe_dump(self.compose, sort_keys=False))
        return out


def build(environment: Environment) -> Bundle:
    """Build the environment's bundle in memory: reads the platforms and the world, writes nothing."""
    # the agents' model directories and the models they borrow from, their siblings
    # (meshes of another platform: model://<name>/...)
    dirs = set()
    for agent in environment.agents.values():
        model = agent.platform.model
        dirs |= {model.parent} | {
            model.parent.parent / n for n in re.findall(r"model://([^/<]+)/", model.read_text())
        }
    by_name: dict[str, Path] = {}
    for d in sorted(dirs):
        if (other := by_name.setdefault(d.name, d)) != d:
            sys.exit(f"two model directories are both named {d.name} in platforms/: {other} and {d}")

    source = environment.world.source
    # ponytail: clearance from the first agent's platform; pass the widest if they differ a lot
    clearance = next(iter(environment.agents.values())).platform.width() * 1.1
    world: SdfWorld | Path
    if isinstance(source, WorldFile):
        world, world_file, summary = source.path, source.path.name, None
        world_el = ET.parse(source.path).find("world")
        if world_el is None or not world_el.get("name"):
            sys.exit(f"{source.path}: no <world name=...>")
        world_name = world_el.get("name", "")
    elif isinstance(source, EmptySpec):
        world, world_file = empty.world(clearance=clearance), "room.sdf"
        summary, world_name = empty.summary(clearance=clearance), world.name
    else:
        room_args = {"size": source.size} if source.size is not None else {}
        if source.obstacles is not None:
            room_args["obstacles"] = source.obstacles
        world, world_file = room.world(clearance=clearance, seed=source.seed, **room_args), "room.sdf"
        summary = room.summary(world, clearance=clearance, seed=source.seed, **room_args)
        world_name = world.name

    spawns, bridge, copies, models = agents(environment)
    firmware, firmware_lines = {}, []
    for agent in environment.agents.values():
        px4 = agent.platform.px4.firmware
        if px4 not in firmware:
            ref, commit = firmware[px4] = px4.resolve()
            firmware_lines.append(f"PX4 {commit[:12]}" if ref == commit else f"PX4 {ref} ({commit[:12]})")
    return Bundle(
        environment=environment,
        world_name=world_name,
        world=world,
        world_file=world_file,
        world_summary=summary,
        compose=compose(environment, Path(world_file).stem, world_name, firmware),
        spawn=SPAWN.format(world=world_name, agents="\n".join(spawns)),
        bridge=environment.world.bridge + bridge,  # the world's clock first, then the agents' entries
        platforms=by_name | copies,
        models=models,
        firmware_lines=firmware_lines,
    )
