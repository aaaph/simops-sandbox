"""The session lifecycle against Docker: up, down, run, world restart, namespaces, isolation.

Slow (a minute or more per test) and needs the images built: `pixi run pytest -m docker`.
Each test runs a copy of rover_room under its own name and router port, so it neither
collides with a rover_room someone keeps up nor with another test.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from simops.bundle import build
from simops.environment import Environment
from simops.session import Session
from worldgen import room

pytestmark = pytest.mark.docker

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT = ROOT / "environments/rover_room.yaml"
TIMEOUT = 300


def environment(tmp_path: Path, name: str, port: int, agents: list[str], namespaces: bool = False) -> Session:
    """rover_room renamed, on its own port, with the given agents 2 m apart."""
    sim = yaml.safe_load(ENVIRONMENT.read_text())
    platform = str(ROOT / "platforms/rover_differential_lidar_px4")
    sim |= {
        "name": name,
        "namespaces": namespaces,
        "network": {"router_port": port},
        "agents": {a: {"platform": platform, "pose": [2 * i, 0, 0.2]} for i, a in enumerate(agents)},
    }
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(sim))
    return Session(Environment.load(path))


def containers(sim: Session) -> list[str]:
    """Ids of every container of the environment's session, running or not."""
    out = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={sim.environment.name}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()


def started_at(sim: Session, service: str) -> str:
    """When the service's container last started."""
    cid = sim.project().get_container(service, include_all=True).ID
    assert cid, f"no container for {service}"
    return subprocess.run(
        ["docker", "inspect", "-f", "{{.State.StartedAt}}", cid], capture_output=True, text=True, check=True
    ).stdout.strip()


def ros_topics(sim: Session, expected: set[str], timeout: float = 60) -> set[str]:
    """ROS topics the host sees through the session's router, once `expected` are among them."""
    topics: set[str] = set()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = subprocess.run(
            ["ros2", "topic", "list", "--no-daemon"],
            env=os.environ | sim.host_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        topics = set(out.stdout.split())
        if expected <= topics:
            break
        time.sleep(3)
    return topics


@pytest.fixture
def cleanup():
    """Sessions to tear down after the test, whatever happens."""
    started: list[dict] = []
    yield started
    for sim in started:
        sim.down()


def test_up_and_down(tmp_path, cleanup):
    sim = environment(tmp_path, "t_updown", 7461, ["rover1"])
    cleanup.append(sim)
    assert sim.up(TIMEOUT) == 0
    assert sim.ready(build(sim.environment))  # rover1 in the world, sim time advancing
    assert sim.down() == 0
    assert containers(sim) == []


def test_failed_up_leaves_nothing(tmp_path, cleanup):
    # an agent whose model gz cannot load never appears in the world
    broken = tmp_path / "broken_platform"
    shutil.copytree(ROOT / "platforms/rover_differential_lidar_px4", broken)
    (broken / "model.sdf").write_text('<sdf version="1.9">not a model</sdf>')
    world = tmp_path / "room.sdf"  # a ready-made world: the generator cannot measure the broken model
    room.generate(world, clearance=0.9)
    sim = yaml.safe_load(ENVIRONMENT.read_text())
    sim |= {
        "name": "t_timeout",
        "network": {"router_port": 7462},
        "world": {"file": str(world)},
        "agents": {"rover1": {"platform": str(broken), "pose": [0, 0, 0.2]}},
    }
    path = tmp_path / "t_timeout.yaml"
    path.write_text(yaml.safe_dump(sim))
    sim = Session(Environment.load(path))
    cleanup.append(sim)
    assert sim.up(timeout=1) != 0
    assert containers(sim) == []


def test_ready_on_first_check_ignores_timeout(tmp_path, cleanup):
    sim = environment(tmp_path, "t_quick", 7468, ["rover1"])
    cleanup.append(sim)
    assert sim.up(timeout=1) == 0


def test_run_passes_exit_code_and_cleans_up(tmp_path, cleanup):
    sim = environment(tmp_path, "t_run", 7463, ["rover1"])
    cleanup.append(sim)
    assert sim.run(TIMEOUT, ["sh", "-c", "exit 3"]) == 3
    assert containers(sim) == []


def test_world_restart_brings_agents_back(tmp_path, cleanup):
    sim = environment(tmp_path, "t_restart", 7464, ["rover1"])
    cleanup.append(sim)
    assert sim.up(TIMEOUT) == 0
    px4_before = started_at(sim, "px4-rover1")
    assert (
        subprocess.run([*sim.project().docker_compose_command(), "restart", "world"], check=False).returncode == 0
    )
    deadline = time.monotonic() + TIMEOUT
    while sim.pose_stamp("room") is None:
        assert time.monotonic() < deadline, "rover1 not back in the world"
        time.sleep(3)
    assert started_at(sim, "px4-rover1") != px4_before


def test_namespaces(tmp_path, cleanup):
    sim = environment(tmp_path, "t_pair", 7465, ["rover1", "rover2"], namespaces=True)
    cleanup.append(sim)
    assert sim.up(TIMEOUT) == 0
    expected = {"/rover1/scan", "/rover2/scan", "/clock"}
    topics = ros_topics(sim, expected | {"/rover2/fmu/out/vehicle_status"})
    assert expected <= topics
    assert any(t.startswith("/rover2/fmu/out/") for t in topics)
    assert not {"/scan", "/rover1/clock", "/rover2/clock"} & topics


def test_environments_isolated(tmp_path, cleanup):
    a = environment(tmp_path, "t_iso_a", 7466, ["alpha"], namespaces=True)
    b = environment(tmp_path, "t_iso_b", 7467, ["beta"], namespaces=True)
    cleanup += [a, b]
    assert a.up(TIMEOUT) == 0
    assert b.up(TIMEOUT) == 0
    seen_a = ros_topics(a, {"/alpha/scan"})
    seen_b = ros_topics(b, {"/beta/scan"})
    assert "/alpha/scan" in seen_a
    assert not any(t.startswith("/beta/") for t in seen_a)
    assert "/beta/scan" in seen_b
    assert not any(t.startswith("/alpha/") for t in seen_b)
