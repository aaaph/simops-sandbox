"""The scenario lifecycle against Docker: up, down, run, world restart, namespaces, isolation.

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
from simops import build, down, host_env, load, pose_stamp, project, ready, run, up

pytestmark = pytest.mark.docker

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/rover_room.yaml"
TIMEOUT = 300


def scenario(tmp_path: Path, name: str, port: int, agents: list[str], namespaces: bool = False) -> dict:
    """rover_room renamed, on its own port, with the given agents 2 m apart."""
    sc = yaml.safe_load(SCENARIO.read_text())
    platform = str(ROOT / "platforms/rover_differential_lidar_px4")
    sc |= {
        "name": name,
        "namespaces": namespaces,
        "network": {"router_port": port},
        "agents": {a: {"platform": platform, "pose": [2 * i, 0, 0.2]} for i, a in enumerate(agents)},
    }
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(sc))
    return load(path)


def containers(sc: dict) -> list[str]:
    """Ids of every container of the scenario's compose project, running or not."""
    out = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={sc['name']}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()


def started_at(sc: dict, service: str) -> str:
    """When the service's container last started."""
    cid = project(sc).get_container(service, include_all=True).ID
    assert cid, f"no container for {service}"
    return subprocess.run(
        ["docker", "inspect", "-f", "{{.State.StartedAt}}", cid], capture_output=True, text=True, check=True
    ).stdout.strip()


def ros_topics(sc: dict, expected: set[str], timeout: float = 60) -> set[str]:
    """ROS topics the host sees through the scenario's router, once `expected` are among them."""
    topics: set[str] = set()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = subprocess.run(
            ["ros2", "topic", "list", "--no-daemon"],
            env=os.environ | host_env(sc),
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
    """Scenarios to tear down after the test, whatever happens."""
    started: list[dict] = []
    yield started
    for sc in started:
        down(sc)


def test_up_and_down(tmp_path, cleanup):
    sc = scenario(tmp_path, "t_updown", 7461, ["rover1"])
    cleanup.append(sc)
    assert up(sc, TIMEOUT) == 0
    assert ready(sc, build(sc))  # rover1 in the world, sim time advancing
    assert down(sc) == 0
    assert containers(sc) == []


def test_failed_up_leaves_nothing(tmp_path, cleanup):
    # an agent whose model gz cannot load never appears in the world
    broken = tmp_path / "broken_platform"
    shutil.copytree(ROOT / "platforms/rover_differential_lidar_px4", broken)
    (broken / "model.sdf").write_text('<sdf version="1.9">not a model</sdf>')
    sc = yaml.safe_load(SCENARIO.read_text())
    sc |= {
        "name": "t_timeout",
        "network": {"router_port": 7462},
        "world": {"file": str(ROOT / "worlds/temp_room.sdf")},
        "agents": {"rover1": {"platform": str(broken), "pose": [0, 0, 0.2]}},
    }
    path = tmp_path / "t_timeout.yaml"
    path.write_text(yaml.safe_dump(sc))
    sc = load(path)
    cleanup.append(sc)
    assert up(sc, timeout=1) != 0
    assert containers(sc) == []


def test_ready_on_first_check_ignores_timeout(tmp_path, cleanup):
    sc = scenario(tmp_path, "t_quick", 7468, ["rover1"])
    cleanup.append(sc)
    assert up(sc, timeout=1) == 0


def test_run_passes_exit_code_and_cleans_up(tmp_path, cleanup):
    sc = scenario(tmp_path, "t_run", 7463, ["rover1"])
    cleanup.append(sc)
    assert run(sc, TIMEOUT, ["sh", "-c", "exit 3"]) == 3
    assert containers(sc) == []


def test_world_restart_brings_agents_back(tmp_path, cleanup):
    sc = scenario(tmp_path, "t_restart", 7464, ["rover1"])
    cleanup.append(sc)
    assert up(sc, TIMEOUT) == 0
    px4_before = started_at(sc, "px4-rover1")
    assert subprocess.run([*project(sc).docker_compose_command(), "restart", "world"], check=False).returncode == 0
    deadline = time.monotonic() + TIMEOUT
    while pose_stamp(sc, "room", ["rover1"]) is None:
        assert time.monotonic() < deadline, "rover1 not back in the world"
        time.sleep(3)
    assert started_at(sc, "px4-rover1") != px4_before


def test_namespaces(tmp_path, cleanup):
    sc = scenario(tmp_path, "t_pair", 7465, ["rover1", "rover2"], namespaces=True)
    cleanup.append(sc)
    assert up(sc, TIMEOUT) == 0
    expected = {"/rover1/scan", "/rover2/scan", "/clock"}
    topics = ros_topics(sc, expected | {"/rover2/fmu/out/vehicle_status"})
    assert expected <= topics
    assert any(t.startswith("/rover2/fmu/out/") for t in topics)
    assert not {"/scan", "/rover1/clock", "/rover2/clock"} & topics


def test_scenarios_isolated(tmp_path, cleanup):
    a = scenario(tmp_path, "t_iso_a", 7466, ["alpha"], namespaces=True)
    b = scenario(tmp_path, "t_iso_b", 7467, ["beta"], namespaces=True)
    cleanup += [a, b]
    assert up(a, TIMEOUT) == 0
    assert up(b, TIMEOUT) == 0
    seen_a = ros_topics(a, {"/alpha/scan"})
    seen_b = ros_topics(b, {"/beta/scan"})
    assert "/alpha/scan" in seen_a
    assert not any(t.startswith("/beta/") for t in seen_a)
    assert "/beta/scan" in seen_b
    assert not any(t.startswith("/alpha/") for t in seen_b)
