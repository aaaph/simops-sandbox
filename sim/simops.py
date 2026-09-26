#!/usr/bin/env python3
"""Run a scenario -- world + robots + autopilot, described in one YAML file -- in Docker.

First the world, then the robots: the world starts empty, a one-shot `spawn` service
adds the scenario's robots to it, and only then does each robot's autopilot attach.
`build` turns the scenario into a bundle in build/<name>/ -- compose.yaml, spawn.sh,
bridge.yaml, the world and the platforms -- that plain `docker compose up` runs too.
`up` builds it, starts it and returns only once every robot is in the world and the
physics moves; if it cannot get there, it prints the log tail and leaves nothing running.
`run` does up, runs a command against the sim, and always tears it down. Every scenario
is its own compose project and GZ_PARTITION.

    pixi run simops up scenarios/rover_room.yaml
    pixi run simops run scenarios/rover_room.yaml -- pytest tests/
    pixi run simops env scenarios/rover_room.yaml | source   # fish; bash: eval "$(...)"
    pixi run simops down scenarios/rover_room.yaml
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parent.parent


def load(path: Path) -> dict:
    """Read a scenario, resolving its paths against the file's own directory."""
    sc = yaml.safe_load(path.read_text())
    base = path.resolve().parent
    if "file" in sc["world"]:
        sc["world"]["file"] = (base / sc["world"]["file"]).resolve()
    for robot in sc["robots"].values():
        robot["platform"] = (base / robot["platform"]).resolve()
        robot["meta"] = yaml.safe_load((robot["platform"] / "platform.yaml").read_text())
    sc.setdefault("namespaces", False)
    sc.setdefault("network", {}).setdefault("router_port", 7447)
    if len(sc["robots"]) > 1 and not sc["namespaces"]:
        sys.exit(f"{path}: several robots publish the same topics -- set `namespaces: true`")
    return sc


def zenoh_gz(port: int = 7447) -> str:
    """gz-transport's zenoh config: every peer goes through the router, no multicast."""
    return f'mode="peer";connect/endpoints=["tcp/localhost:{port}"];scouting/multicast/enabled=false'


def compose(sc: dict, world_stem: str, world_name: str) -> dict:
    """Describe the scenario as a compose file; paths are relative to the bundle directory."""
    name, px4 = sc["name"], sc["autopilot"]["px4"]
    gz = {"GZ_PARTITION": name, "GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE": zenoh_gz()}
    port = sc["network"]["router_port"]

    def beside_router(*restart_with: str) -> dict:
        # Sharing the router's network namespace (localhost:7447 is the router): when the
        # router restarts, a container is left in the old namespace with no network, so it
        # restarts with it -- and with the world, which loses the robot when it restarts.
        deps = {s: {"condition": "service_started", "restart": True} for s in ("zenoh-router", *restart_with)}
        return {"network_mode": "service:zenoh-router", "depends_on": deps}

    after_spawn = beside_router("world")
    after_spawn["depends_on"]["spawn"] = {"condition": "service_completed_successfully", "restart": True}

    world_image = {
        "build": {"context": str(ROOT), "dockerfile": "infra/world.Dockerfile"},
        "image": "simops-sandbox-world",
    }
    # PX4 per robot: attaches to its robot once `spawn` has put it in the world; /fmu/* on the router
    autopilots = {
        f"px4-{robot}": {
            "build": {
                "context": str(ROOT),
                "dockerfile": "infra/px4.Dockerfile",
                "args": {
                    "PX4_REPO": px4.get("repo", "https://github.com/PX4/PX4-Autopilot.git"),
                    "PX4_REF": px4["ref"],
                },
            },
            "image": f"simops-sandbox-px4:{px4['ref'][:12]}",
            **after_spawn,
            "environment": {
                **gz,
                "PX4_GZ_WORLD": world_name,
                "PX4_GZ_MODEL_NAME": robot,
                "PX4_SYS_AUTOSTART": str(spec["meta"]["autopilot"]["px4"]["airframe"]),
                "PX4_INSTANCE": str(i),
                **({"PX4_ZENOH_NAMESPACE": robot} if sc["namespaces"] else {}),
            },
        }
        for i, (robot, spec) in enumerate(sc["robots"].items())
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
            # adds the robots to the running world, exits; again whenever the world restarts
            "spawn": {
                **world_image,
                **beside_router("world"),
                "environment": gz,
                "volumes": ["./platforms:/sim/platforms:ro", "./spawn.sh:/sim/spawn.sh:ro"],
                "command": ["sh", "/sim/spawn.sh"],
            },
            **autopilots,
            # the sim's stand-in for the robots' sensor drivers: their bridge.yaml, merged
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


def namespaced(robot: str, topic: str) -> str:
    """Put a gz or ROS topic under /<robot>; relative gz topics are absolute from the root."""
    return f"/{robot}/{topic.lstrip('/')}"


SPAWN = """#!/bin/sh
# First the world, then the robots: add the scenario's robots to the running world.
# Generated by sim/simops.py.
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
{robots}
"""


def entity_factory(robot: str, sdf: str, pose: list[float]) -> str:
    """Build the gz.msgs.EntityFactory request that puts one robot into the world."""
    x, y, z, roll, pitch, yaw = (pose + [0.0] * 6)[:6]
    qx, qy, qz, qw = Rotation.from_euler("xyz", [roll, pitch, yaw]).as_quat()
    return (
        f'sdf_filename: "{sdf}", name: "{robot}", allow_renaming: false, '
        f"pose: {{position: {{x: {x}, y: {y}, z: {z}}}, orientation: {{x: {qx}, y: {qy}, z: {qz}, w: {qw}}}}}"
    )


def prepare_robots(sc: dict, world: str, out: Path) -> list[dict]:
    """Write spawn.sh for every robot; return everyone's bridge entries.

    With namespaces, each robot gets its own copy of the model whose gz topics sit
    under /<robot>, and the bridge maps them to ROS names under /<robot> too.
    """
    bridge, spawns = [], []
    for robot, spec in sc["robots"].items():
        platform = spec["platform"].name
        entries = yaml.safe_load((spec["platform"] / "bridge.yaml").read_text())
        if sc["namespaces"]:
            model = ET.parse(spec["platform"] / "model.sdf")
            for el in model.iter():
                if el.tag in ("topic", "odom_topic") and el.text:  # sensors, odometry: not model-scoped
                    el.text = namespaced(robot, el.text)
            platform = f"{platform}.{robot}"
            shutil.copytree(spec["platform"], out / "platforms" / platform)
            model.write(out / "platforms" / platform / "model.sdf", xml_declaration=True)
            for e in entries:
                if e["gz_topic_name"] != "/clock":  # one clock for the whole world
                    e["gz_topic_name"] = namespaced(robot, e["gz_topic_name"])
                    e["ros_topic_name"] = namespaced(robot, e["ros_topic_name"])
        bridge += [e for e in entries if e not in bridge]
        request = entity_factory(robot, f"/sim/platforms/{platform}/model.sdf", spec.get("pose", []))
        spawns.append(f"spawn {robot} '{request}'")
    (out / "spawn.sh").write_text(SPAWN.format(world=world, robots="\n".join(spawns)))
    return bridge


def build(sc: dict) -> dict:
    """Write the bundle build/<name>/: compose.yaml, spawn.sh, bridge.yaml, worlds/, platforms/."""
    out = ROOT / "build" / sc["name"]
    shutil.rmtree(out, ignore_errors=True)
    (out / "worlds").mkdir(parents=True)
    # the platforms and the models they borrow from (meshes of another platform: model://<name>/...)
    platforms = {r["platform"] for r in sc["robots"].values()}
    for platform in list(platforms):
        borrowed = re.findall(r"model://([^/<]+)/", (platform / "model.sdf").read_text())
        platforms |= {platform.parent / name for name in borrowed}
    for p in platforms:
        shutil.copytree(p, out / "platforms" / p.name)

    world = sc["world"]
    if "file" in world:
        sdf = out / "worlds" / world["file"].name
        shutil.copy(world["file"], sdf)
    else:
        room = world["room"]
        sdf = out / "worlds" / "room.sdf"
        # ponytail: clearance from the first robot's platform; pass the widest if they differ a lot
        first = next(iter(sc["robots"].values()))["platform"].name
        subprocess.run(
            [sys.executable, ROOT / "sim/generate_temp_room_world.py", "--platform", first, "-o", sdf]
            + ["--seed", str(room.get("seed", 0))]
            + (["--size", *map(str, room["size"])] if "size" in room else [])
            + (["--obstacles", str(room["obstacles"])] if "obstacles" in room else []),
            check=True,
            cwd=ROOT,
        )
    world_el = ET.parse(sdf).find("world")
    if world_el is None or not world_el.get("name"):
        sys.exit(f"{sdf}: no <world name=...>")
    world_name = world_el.get("name", "")
    bridge = prepare_robots(sc, world_name, out)
    (out / "bridge.yaml").write_text(yaml.safe_dump(bridge, sort_keys=False))
    spec = compose(sc, sdf.stem, world_name)
    (out / "compose.yaml").write_text(yaml.safe_dump(spec, sort_keys=False))
    return spec


def docker_compose(sc: dict, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """`docker compose` on the scenario's bundle and project."""
    bundle = ROOT / "build" / sc["name"]
    return subprocess.run(
        ["docker", "compose", "-f", bundle / "compose.yaml", "-p", sc["name"], *args],
        capture_output=capture,
        text=True,
        check=False,
    )


def pose_stamp(sc: dict, world: str, robots: list[str]) -> float | None:
    """Sim time of one pose message that has every robot in it, or None."""
    echo = f". /opt/gz/activate.sh && timeout 10 gz topic -e -t /world/{world}/pose/info -n 1"
    out = docker_compose(sc, "exec", "-T", "world", "sh", "-c", echo, capture=True).stdout
    if not all(f'name: "{robot}"' in out for robot in robots):
        return None
    sec, nsec = re.search(r"sec: (\d+)", out), re.search(r"nsec: (\d+)", out)
    return int(sec.group(1)) + int(nsec.group(1)) * 1e-9 if sec and nsec else None


def ready(sc: dict, spec: dict) -> bool:
    """Check the robots are in the world and sim time moves -- a wedged server publishes once and stops."""
    world = next(s for n, s in spec["services"].items() if n.startswith("px4-"))["environment"]["PX4_GZ_WORLD"]
    robots = list(sc["robots"])
    first = pose_stamp(sc, world, robots)
    if first is None:
        return False
    time.sleep(1.5)
    second = pose_stamp(sc, world, robots)
    return second is not None and second > first


def host_env(sc: dict) -> dict[str, str]:
    """Say what gz and ROS on the host need to reach this scenario through its router."""
    port = sc["network"]["router_port"]
    return {
        "GZ_PARTITION": sc["name"],
        "GZ_TRANSPORT_IMPLEMENTATION": "zenoh",
        "GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE": zenoh_gz(port),
        "ZENOH_CONFIG_OVERRIDE": f'mode="client";connect/endpoints=["tcp/localhost:{port}"]',
    }


def up(sc: dict, timeout: float) -> int:
    """Build and start the scenario, wait until the robots are in a running sim; on failure leave nothing."""
    spec = build(sc)
    if docker_compose(sc, "up", "-d").returncode:
        down(sc)
        return 1
    deadline = time.monotonic() + timeout
    while not ready(sc, spec):
        if time.monotonic() > deadline:
            print(f"robots not in the world after {timeout:.0f} s; last log lines:")
            docker_compose(sc, "logs", "--tail", "15")
            down(sc)
            return 1
        time.sleep(3)
    print(f"{sc['name']} up. GUI: `simops gui <scenario>`, stop: `simops down <scenario>`", flush=True)
    return 0


def down(sc: dict) -> int:
    """Stop and remove the scenario's containers."""
    return docker_compose(sc, "down", "--remove-orphans").returncode


def run(sc: dict, timeout: float, command: list[str]) -> int:
    """Up, run the command against the sim, down whatever happens."""
    if up(sc, timeout):
        return 1
    try:
        return subprocess.run(command, env=os.environ | host_env(sc), check=False).returncode
    finally:
        down(sc)


def main() -> int:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd, text in [
        ("build", "write the bundle to build/<name>/"),
        ("up", "start and wait until the robots are in the world"),
        ("down", "stop"),
        ("env", "print exports for gz and ROS on the host"),
        ("gui", "native gz GUI attached to the running scenario"),
        ("run", "up, run the command after --, down"),
    ]:
        p = sub.add_parser(cmd, help=text)
        p.add_argument("scenario", type=Path)
        if cmd in ("up", "run"):
            p.add_argument("--timeout", type=float, default=300, help="seconds to wait for the robots")
    # everything after `--` is the command for `run`, whatever flags it has
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    args = parser.parse_args(argv[:split])
    command = argv[split + 1 :]
    sc = load(args.scenario)

    if args.cmd == "run":
        return run(sc, args.timeout, command)
    if args.cmd == "up":
        return up(sc, args.timeout)
    if args.cmd == "env":
        print("\n".join(f"export {k}='{v}'" for k, v in host_env(sc).items()))
        return 0
    if args.cmd == "gui":
        return subprocess.run(["gz", "sim", "-g"], env=os.environ | host_env(sc), check=False).returncode
    if args.cmd == "build":
        build(sc)
        print(ROOT / "build" / sc["name"])
        return 0
    return down(sc)


if __name__ == "__main__":
    sys.exit(main())
