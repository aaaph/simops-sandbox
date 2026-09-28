"""The bundle: an environment built for docker compose in build/<name>/."""

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from simops import ROOT
from simops.agent import entity_factory
from simops.environment import Environment
from simops.world import WorldFile
from worldgen import room


def zenoh_gz(port: int = 7447) -> str:
    """gz-transport's zenoh config: every peer goes through the router, no multicast."""
    return f'mode="peer";connect/endpoints=["tcp/localhost:{port}"];scouting/multicast/enabled=false'


def compose(environment: Environment, world_stem: str, world_name: str, px4_ref: str, px4_commit: str) -> dict:
    """Describe the environment as a compose file; paths are relative to the bundle directory."""
    name, px4 = environment.name, environment.autopilot.px4
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
                    "PX4_REPO": px4.repo,
                    "PX4_REF": px4_ref,
                },
            },
            "image": f"simops-sandbox-px4:{px4_commit[:12]}",  # one image per commit, however it was named
            **after_spawn,
            "environment": {
                **gz,
                "PX4_GZ_WORLD": world_name,
                "PX4_GZ_MODEL_NAME": agent,
                "PX4_SYS_AUTOSTART": str(spec.platform.px4_airframe),
                "PX4_INSTANCE": str(i),
                **({"PX4_ZENOH_NAMESPACE": agent} if environment.namespaces else {}),
            },
        }
        for i, (agent, spec) in enumerate(environment.agents.items())
    }
    ros = {"build": {"context": str(ROOT), "dockerfile": "infra/ros.Dockerfile"}, "image": "simops-sandbox-ros"}
    return {
        "name": name,
        "services": {
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
            # the sim's stand-in for the agents' sensor drivers: their bridge.yaml, merged
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
        },
    }


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


def prepare_agents(environment: Environment, world: str, out: Path) -> list[dict]:
    """Write spawn.sh for every agent; return everyone's bridge entries.

    With namespaces, each agent gets its own copy of the model whose gz topics sit
    under /<agent>, and the bridge maps them to ROS names under /<agent> too.
    """
    bridge, spawns = [], []
    for agent, spec in environment.agents.items():
        platform = spec.platform.name
        entries = yaml.safe_load(spec.platform.bridge.read_text())
        if environment.namespaces:
            model = ET.parse(spec.platform.model)
            for el in model.iter():
                if el.tag in ("topic", "odom_topic") and el.text:  # sensors, odometry: not model-scoped
                    el.text = namespaced(agent, el.text)
            platform = f"{platform}.{agent}"
            shutil.copytree(spec.platform.dir, out / "platforms" / platform)
            model.write(out / "platforms" / platform / "model.sdf", xml_declaration=True)
            for e in entries:
                if e["gz_topic_name"] != "/clock":  # one clock for the whole world
                    e["gz_topic_name"] = namespaced(agent, e["gz_topic_name"])
                    e["ros_topic_name"] = namespaced(agent, e["ros_topic_name"])
        bridge += [e for e in entries if e not in bridge]
        request = entity_factory(agent, f"/sim/platforms/{platform}/model.sdf", spec.pose)
        spawns.append(f"spawn {agent} '{request}'")
    (out / "spawn.sh").write_text(SPAWN.format(world=world, agents="\n".join(spawns)))
    return bridge


class Bundle(BaseModel):
    """An environment built for docker compose in build/<name>/."""

    model_config = ConfigDict(frozen=True)

    environment: Environment
    dir: Path
    compose: dict
    world_name: str


def build(environment: Environment) -> Bundle:
    """Write the bundle build/<name>/: compose.yaml, spawn.sh, bridge.yaml, worlds/, platforms/."""
    out = ROOT / "build" / environment.name
    shutil.rmtree(out, ignore_errors=True)
    (out / "worlds").mkdir(parents=True)
    # the platforms and the models they borrow from (meshes of another platform: model://<name>/...)
    platforms = {agent.platform.dir for agent in environment.agents.values()}
    for platform in list(platforms):
        borrowed = re.findall(r"model://([^/<]+)/", (platform / "model.sdf").read_text())
        platforms |= {platform.parent / name for name in borrowed}
    for p in platforms:
        shutil.copytree(p, out / "platforms" / p.name)

    source = environment.world.source
    if isinstance(source, WorldFile):
        sdf = out / "worlds" / source.path.name
        shutil.copy(source.path, sdf)
    else:
        sdf = out / "worlds" / "room.sdf"
        # ponytail: clearance from the first agent's platform; pass the widest if they differ a lot
        first = next(iter(environment.agents.values())).platform
        room_args = {"size": source.size} if source.size is not None else {}
        if source.obstacles is not None:
            room_args["obstacles"] = source.obstacles
        print(room.generate(sdf, clearance=first.width() * 1.1, seed=source.seed, **room_args), flush=True)
    world_el = ET.parse(sdf).find("world")
    if world_el is None or not world_el.get("name"):
        sys.exit(f"{sdf}: no <world name=...>")
    world_name = world_el.get("name", "")
    bridge = prepare_agents(environment, world_name, out)
    (out / "bridge.yaml").write_text(yaml.safe_dump(bridge, sort_keys=False))
    px4_ref, px4_commit = environment.autopilot.px4.resolve()
    print(f"PX4 {px4_commit}" if px4_ref == px4_commit else f"PX4 {px4_ref} = {px4_commit}", flush=True)
    spec = compose(environment, sdf.stem, world_name, px4_ref, px4_commit)
    (out / "compose.yaml").write_text(yaml.safe_dump(spec, sort_keys=False))
    return Bundle(environment=environment, dir=out, compose=spec, world_name=world_name)
