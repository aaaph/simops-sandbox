#!/usr/bin/env python3
"""Run a scenario -- world + agents + autopilot, described in one YAML file -- in Docker.

First the world, then the agents: the world starts empty, a one-shot `spawn` service
adds the scenario's agents to it, and only then does each agent's autopilot attach.
`build` turns the scenario into a bundle in build/<name>/ -- compose.yaml, spawn.sh,
bridge.yaml, the world and the platforms -- that plain `docker compose up` runs too.
`up` builds it, starts it and returns only once every agent is in the world and the
physics moves; if it cannot get there, it prints the log tail and leaves nothing running.
`run` does up, runs a command against the sim, and always tears it down. Every scenario
is its own compose project and GZ_PARTITION, driven through testcontainers' DockerCompose.

\b
    pixi run simops up scenarios/rover_room.yaml
    pixi run simops run scenarios/rover_room.yaml -- pytest tests/
    pixi run simops env scenarios/rover_room.yaml | source   # fish; bash: eval "$(...)"
    pixi run simops down scenarios/rover_room.yaml
"""  # noqa: D301 -- `\b` keeps click from rewrapping the examples

import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import CalledProcessError
from typing import Annotated

import typer
import yaml
from testcontainers.compose import DockerCompose

ROOT = Path(__file__).resolve().parent.parent
# testcontainers logs every failed compose call at ERROR -- a readiness poll while the world boots
# included; simops prints the failures that matter itself
logging.getLogger("testcontainers").setLevel(logging.CRITICAL)


def load(path: Path) -> dict:
    """Read a scenario, resolving its paths against the file's own directory."""
    sc = yaml.safe_load(path.read_text())
    base = path.resolve().parent
    if "robots" in sc:
        sys.exit(f"{path}: `robots:` is now `agents:`")
    if "file" in sc["world"]:
        sc["world"]["file"] = (base / sc["world"]["file"]).resolve()
    for agent in sc["agents"].values():
        agent["platform"] = (base / agent["platform"]).resolve()
        agent["meta"] = yaml.safe_load((agent["platform"] / "agent.yaml").read_text())
    sc.setdefault("namespaces", False)
    sc.setdefault("network", {}).setdefault("router_port", 7447)
    if len(sc["agents"]) > 1 and not sc["namespaces"]:
        sys.exit(f"{path}: several agents publish the same topics -- set `namespaces: true`")
    check_px4(path, sc.setdefault("autopilot", {}).setdefault("px4", {}))
    return sc


def check_px4(path: Path, px4: dict) -> None:
    """Check how the scenario names its PX4, without the network: `down` and `env` run offline."""
    if "ref" in px4:
        sys.exit(f"{path}: `autopilot.px4.ref` is now `version` (a release tag) or `commit` (a full SHA)")
    if "version" in px4 and "commit" in px4:
        sys.exit(f"{path}: give `autopilot.px4.version` or `commit`, not both")
    if "commit" in px4 and not re.fullmatch(r"[0-9a-f]{40}", str(px4["commit"])):
        sys.exit(f"{path}: `autopilot.px4.commit` must be the full 40-character SHA")
    if "version" in px4:
        v = parse_version(str(px4["version"]))
        if v is None:
            sys.exit(f"{path}: `autopilot.px4.version: {px4['version']}` is not a PX4 version like v1.18.0")
        if v[:2] < MIN_PX4:
            sys.exit(f"{path}: {unsupported(str(px4['version']))}")


def resolve_px4(px4: dict) -> tuple[str, str]:
    """Resolve the scenario's PX4 to (what to build from: tag or commit, the commit); version needs the network."""
    if "commit" in px4:
        return px4["commit"], px4["commit"]
    repo = px4.get("repo", PX4_REPO)
    tags = parse_tags(ls_remote(repo))
    if "version" in px4:
        tag = str(px4["version"])
        tag = tag if tag.startswith("v") else f"v{tag}"
        if tag not in tags:
            sys.exit(f"PX4 {tag}: no such tag in {repo}")
    elif (tag := default_tag(tags)) is None:
        sys.exit(f"{repo} has no tag of PX4 {'.'.join(map(str, MIN_PX4))} or later: set `autopilot.px4.commit`")
    return tag, tags[tag]


def unsupported(version: str) -> str:
    """Say why a PX4 version cannot run on this stack."""
    return (
        f"PX4 {version} is not supported, the minimum is {'.'.join(map(str, MIN_PX4))}: "
        "PX4 1.17 and earlier compile as C++14, the gz Jetty toolchain needs C++17"
    )


# PX4 1.17 and earlier compile as C++14; the conda gz Jetty env's abseil requires C++17
MIN_PX4 = (1, 18)
PX4_REPO = "https://github.com/PX4/PX4-Autopilot.git"
VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(\d+))?")
STAGES = {"alpha": 0, "beta": 1, "rc": 2, None: 3}  # 3: a release


def parse_version(text: str) -> tuple[int, int, int, int, int] | None:
    """Order key of a PX4 version (`v1.18.0`, `1.18.0-rc1`), or None if it is not one."""
    m = VERSION.fullmatch(text)
    if not m:
        return None
    major, minor, patch, stage, n = m.groups()
    return int(major), int(minor), int(patch), STAGES[stage], int(n or 0)


def parse_tags(ls_remote_output: str) -> dict[str, str]:
    """Map each tag of `git ls-remote --tags` to its commit; an annotated tag's peeled line wins."""
    tags: dict[str, str] = {}
    for line in ls_remote_output.splitlines():
        sha, _, ref = line.partition("\t")
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = sha
        else:
            tags.setdefault(name, sha)
    return tags


def default_tag(tags: dict[str, str]) -> str | None:
    """Newest supported release tag, else the newest supported pre-release, else None."""
    supported = {t: v for t in tags if (v := parse_version(t)) and v[:2] >= MIN_PX4}
    releases = [t for t, v in supported.items() if v[3] == STAGES[None]]
    pool = releases or list(supported)
    return max(pool, key=lambda t: supported[t]) if pool else None


def ls_remote(repo: str) -> str:
    """List the repository's tags (network)."""
    out = subprocess.run(["git", "ls-remote", "--tags", repo], capture_output=True, text=True, check=False)
    if out.returncode:
        sys.exit(f"cannot list the tags of {repo} (a `commit` builds offline): {out.stderr.strip()}")
    return out.stdout


def zenoh_gz(port: int = 7447) -> str:
    """gz-transport's zenoh config: every peer goes through the router, no multicast."""
    return f'mode="peer";connect/endpoints=["tcp/localhost:{port}"];scouting/multicast/enabled=false'


def compose(sc: dict, world_stem: str, world_name: str, px4_ref: str, px4_commit: str) -> dict:
    """Describe the scenario as a compose file; paths are relative to the bundle directory."""
    name, px4 = sc["name"], sc["autopilot"]["px4"]
    gz = {"GZ_PARTITION": name, "GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE": zenoh_gz()}
    port = sc["network"]["router_port"]

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
                    "PX4_REPO": px4.get("repo", PX4_REPO),
                    "PX4_REF": px4_ref,
                },
            },
            "image": f"simops-sandbox-px4:{px4_commit[:12]}",  # one image per commit, however it was named
            **after_spawn,
            "environment": {
                **gz,
                "PX4_GZ_WORLD": world_name,
                "PX4_GZ_MODEL_NAME": agent,
                "PX4_SYS_AUTOSTART": str(spec["meta"]["autopilot"]["px4"]["airframe"]),
                "PX4_INSTANCE": str(i),
                **({"PX4_ZENOH_NAMESPACE": agent} if sc["namespaces"] else {}),
            },
        }
        for i, (agent, spec) in enumerate(sc["agents"].items())
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
# First the world, then the agents: add the scenario's agents to the running world.
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
{agents}
"""


def quaternion(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """Turn ROS roll-pitch-yaw (extrinsic x, then y, then z) into a quaternion (x, y, z, w)."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def entity_factory(agent: str, sdf: str, pose: list[float]) -> str:
    """Build the gz.msgs.EntityFactory request that puts one agent into the world."""
    x, y, z, roll, pitch, yaw = (pose + [0.0] * 6)[:6]
    qx, qy, qz, qw = quaternion(roll, pitch, yaw)
    return (
        f'sdf_filename: "{sdf}", name: "{agent}", allow_renaming: false, '
        f"pose: {{position: {{x: {x}, y: {y}, z: {z}}}, orientation: {{x: {qx}, y: {qy}, z: {qz}, w: {qw}}}}}"
    )


def prepare_agents(sc: dict, world: str, out: Path) -> list[dict]:
    """Write spawn.sh for every agent; return everyone's bridge entries.

    With namespaces, each agent gets its own copy of the model whose gz topics sit
    under /<agent>, and the bridge maps them to ROS names under /<agent> too.
    """
    bridge, spawns = [], []
    for agent, spec in sc["agents"].items():
        platform = spec["platform"].name
        entries = yaml.safe_load((spec["platform"] / "bridge.yaml").read_text())
        if sc["namespaces"]:
            model = ET.parse(spec["platform"] / "model.sdf")
            for el in model.iter():
                if el.tag in ("topic", "odom_topic") and el.text:  # sensors, odometry: not model-scoped
                    el.text = namespaced(agent, el.text)
            platform = f"{platform}.{agent}"
            shutil.copytree(spec["platform"], out / "platforms" / platform)
            model.write(out / "platforms" / platform / "model.sdf", xml_declaration=True)
            for e in entries:
                if e["gz_topic_name"] != "/clock":  # one clock for the whole world
                    e["gz_topic_name"] = namespaced(agent, e["gz_topic_name"])
                    e["ros_topic_name"] = namespaced(agent, e["ros_topic_name"])
        bridge += [e for e in entries if e not in bridge]
        request = entity_factory(agent, f"/sim/platforms/{platform}/model.sdf", spec.get("pose", []))
        spawns.append(f"spawn {agent} '{request}'")
    (out / "spawn.sh").write_text(SPAWN.format(world=world, agents="\n".join(spawns)))
    return bridge


def build(sc: dict) -> dict:
    """Write the bundle build/<name>/: compose.yaml, spawn.sh, bridge.yaml, worlds/, platforms/."""
    out = ROOT / "build" / sc["name"]
    shutil.rmtree(out, ignore_errors=True)
    (out / "worlds").mkdir(parents=True)
    # the platforms and the models they borrow from (meshes of another platform: model://<name>/...)
    platforms = {r["platform"] for r in sc["agents"].values()}
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
        # ponytail: clearance from the first agent's platform; pass the widest if they differ a lot
        first = next(iter(sc["agents"].values()))["platform"].name
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
    bridge = prepare_agents(sc, world_name, out)
    (out / "bridge.yaml").write_text(yaml.safe_dump(bridge, sort_keys=False))
    px4_ref, px4_commit = resolve_px4(sc["autopilot"]["px4"])
    print(f"PX4 {px4_commit}" if px4_ref == px4_commit else f"PX4 {px4_ref} = {px4_commit}", flush=True)
    spec = compose(sc, sdf.stem, world_name, px4_ref, px4_commit)
    (out / "compose.yaml").write_text(yaml.safe_dump(spec, sort_keys=False))
    return spec


def project(sc: dict) -> DockerCompose:
    """Open the scenario's bundle as a compose project (its name is set in compose.yaml)."""
    bundle = ROOT / "build" / sc["name"]
    return DockerCompose(bundle, compose_file_name=str(bundle / "compose.yaml"), wait=True)


def log_tail(sc: dict, lines: int = 15) -> None:
    """Print the last lines each service logged."""
    try:
        out, err = project(sc).get_logs()
    except CalledProcessError:
        return
    tails: dict[str, list[str]] = {}
    for line in (out + err).splitlines():
        tails.setdefault(line.split(" | ", 1)[0].strip(), []).append(line)
    for tail in tails.values():
        print("\n".join(tail[-lines:]))


def pose_stamp(sc: dict, world: str, agents: list[str]) -> float | None:
    """Sim time of one pose message that has every agent in it, or None."""
    echo = f". /opt/gz/activate.sh && timeout 10 gz topic -e -t /world/{world}/pose/info -n 1"
    try:
        out, _, _ = project(sc).exec_in_container(["sh", "-c", echo], "world")
    except CalledProcessError:  # no pose message within the timeout: the world is not up yet
        return None
    if not all(f'name: "{agent}"' in out for agent in agents):
        return None
    sec, nsec = re.search(r"sec: (\d+)", out), re.search(r"nsec: (\d+)", out)
    return int(sec.group(1)) + int(nsec.group(1)) * 1e-9 if sec and nsec else None


def ready(sc: dict, spec: dict) -> bool:
    """Check the agents are in the world and sim time moves -- a wedged server publishes once and stops."""
    world = next(s for n, s in spec["services"].items() if n.startswith("px4-"))["environment"]["PX4_GZ_WORLD"]
    agents = list(sc["agents"])
    first = pose_stamp(sc, world, agents)
    if first is None:
        return False
    time.sleep(1.5)
    second = pose_stamp(sc, world, agents)
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
    """Build and start the scenario, wait until the agents are in a running sim; on failure leave nothing."""
    spec = build(sc)
    print(f"starting {sc['name']} (images are built on first use; a PX4 build takes ~10 min)", flush=True)
    try:
        project(sc).start()  # up --wait: every service runs, `spawn` exited 0
    except CalledProcessError as e:
        print(e.stderr.decode(errors="ignore").strip(), "\nlast log lines:")
        log_tail(sc)
        down(sc)
        return 1
    deadline = time.monotonic() + timeout
    while not ready(sc, spec):
        if time.monotonic() > deadline:
            print(f"agents not in the world after {timeout:.0f} s; last log lines:")
            log_tail(sc)
            down(sc)
            return 1
        time.sleep(3)
    print(f"{sc['name']} up. GUI: `simops gui <scenario>`, stop: `simops down <scenario>`", flush=True)
    return 0


def down(sc: dict) -> int:
    """Stop and remove the scenario's containers."""
    # DockerCompose.stop() leaves orphans: services dropped from a rebuilt bundle must go too
    return subprocess.run(
        [*project(sc).docker_compose_command(), "down", "--remove-orphans"], check=False
    ).returncode


def run(sc: dict, timeout: float, command: list[str]) -> int:
    """Up, run the command against the sim, down whatever happens."""
    if up(sc, timeout):
        return 1
    try:
        return subprocess.run(command, env=os.environ | host_env(sc), check=False).returncode
    finally:
        down(sc)


app = typer.Typer(help=__doc__, no_args_is_help=True, add_completion=False, rich_markup_mode=None)
Scenario = Annotated[Path, typer.Argument(help="scenario YAML file")]
Timeout = Annotated[float, typer.Option(help="seconds to wait for the agents")]


@app.command("build")
def build_cmd(scenario: Scenario) -> None:
    """Write the bundle to build/<name>/."""
    sc = load(scenario)
    build(sc)
    print(ROOT / "build" / sc["name"])


@app.command("up")
def up_cmd(scenario: Scenario, timeout: Timeout = 300) -> None:
    """Start and wait until the agents are in the world."""
    raise typer.Exit(up(load(scenario), timeout))


@app.command("down")
def down_cmd(scenario: Scenario) -> None:
    """Stop."""
    raise typer.Exit(down(load(scenario)))


@app.command("env")
def env_cmd(scenario: Scenario) -> None:
    """Print exports for gz and ROS on the host."""
    print("\n".join(f"export {k}='{v}'" for k, v in host_env(load(scenario)).items()))


@app.command("gui")
def gui_cmd(scenario: Scenario) -> None:
    """Native gz GUI attached to the running scenario."""
    env = os.environ | host_env(load(scenario))
    raise typer.Exit(subprocess.run(["gz", "sim", "-g"], env=env, check=False).returncode)


# the command after `--` goes through untouched, whatever flags it has
@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run_cmd(ctx: typer.Context, scenario: Scenario, timeout: Timeout = 300) -> None:
    """Up, run the command after --, down."""
    raise typer.Exit(run(load(scenario), timeout, ctx.args))


if __name__ == "__main__":
    app()
