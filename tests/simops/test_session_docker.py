"""The session lifecycle against Docker: up, down, run, world restart, namespaces, isolation.

Slow (a minute or more per test) and needs the images built: `pixi run pytest -m docker`.
Each test runs a copy of rover_room under its own name, router port and MAVLink port, so it
neither collides with a rover_room someone keeps up nor with another test.
"""

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from simops.bundle import build
from simops.cli import app
from simops.environment import Environment, Network
from simops.session import Session
from worldgen import room

pytestmark = pytest.mark.docker

ROOT = Path(__file__).resolve().parents[2]
PX4_PLATFORM = str(ROOT / "platforms/rover_differential_lidar_px4")
# the world of these tests: a 25 x 21 m room, as big as sessions in use get
WORLD = {"generate_room": {"size": [25, 21]}}
TIMEOUT = 300


def mavlink_port(router_port: int) -> int:
    """Give the test's own MAVLink port, 10 apart per router port: room for the agents' ranges."""
    return 14600 + (router_port - 7460) * 10


def environment(tmp_path: Path, name: str, port: int, agents: list[str], namespaces: bool = False) -> Session:
    """Give a room with the given agents 2 m apart, under its own name and ports."""
    sim = {
        "name": name,
        "namespaces": namespaces,
        "network": {"router_port": port, "mavlink_port": mavlink_port(port)},
        "world": WORLD,
        "agents": {a: {"platform": PX4_PLATFORM, "pose": [2 * i, 0, 0.2]} for i, a in enumerate(agents)},
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


def mavlink_frame(port: int, timeout: float = 30) -> bytes | None:
    """Listen on the host's port, as MAVSDK's udpin does, for one MAVLink frame from PX4, or None."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", port))  # noqa: S104 -- where Docker Desktop delivers what PX4 sends to the host
        s.settimeout(timeout)
        try:
            return s.recv(65535)
        except TimeoutError:
            return None


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
    sim = {
        "name": "t_timeout",
        "network": {"router_port": 7462, "mavlink_port": mavlink_port(7462)},
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


def test_running_session_found_without_its_file(tmp_path, cleanup):
    sim = environment(tmp_path, "t_found", 7469, ["rover1"])
    cleanup.append(sim)
    assert sim.up(TIMEOUT) == 0
    named = CliRunner().invoke(app, ["host-env", "t_found"])
    assert named.exit_code == 0, named.output
    assert "export GZ_PARTITION='t_found'" in named.output
    assert "tcp/localhost:7469" in named.output
    assert f"export GZ_SIM_RESOURCE_PATH='{sim.dir / 'platforms'}'" in named.output
    # without an argument: this session, unless someone else keeps one up too
    alone = CliRunner().invoke(app, ["host-env"])
    if alone.exit_code == 0:
        assert alone.output == named.output
    else:
        assert "several sessions are up" in alone.output
        assert "t_found" in alone.output
    down = CliRunner().invoke(app, ["down"] if alone.exit_code == 0 else ["down", "t_found"])
    assert down.exit_code == 0, down.output
    assert containers(sim) == []


def test_plain_compose_session_found(tmp_path, cleanup):
    sim = environment(tmp_path, "t_plain", 7470, ["rover1"])
    cleanup.append(sim)
    build(sim.environment).write(sim.dir)
    plain = ["docker", "compose", "-f", str(sim.dir / "compose.yaml"), "up", "-d", "--wait"]
    assert subprocess.run(plain, check=False).returncode == 0
    found = CliRunner().invoke(app, ["host-env", "t_plain"])
    assert found.exit_code == 0, found.output
    assert "tcp/localhost:7470" in found.output
    assert f"export GZ_SIM_RESOURCE_PATH='{sim.dir / 'platforms'}'" in found.output  # compose's working_dir
    shutil.rmtree(sim.dir)  # down needs no bundle
    assert CliRunner().invoke(app, ["down", "t_plain"]).exit_code == 0
    assert containers(sim) == []


def test_mavlink_to_the_host(tmp_path, cleanup):
    sim = environment(tmp_path, "t_mav", 7471, ["rover1"])
    cleanup.append(sim)
    assert sim.up(TIMEOUT) == 0
    for client in ("first", "second"):  # one after another, each on a new socket
        frame = mavlink_frame(mavlink_port(7471))
        assert frame is not None, f"no MAVLink from rover1's PX4 for the {client} client"
        assert frame[0] == 0xFD  # MAVLink 2
        assert frame[5] == 1  # system id: PX4 instance 0


def test_mavlink_port_taken(tmp_path, cleanup):
    a = environment(tmp_path, "t_mav_a", 7472, ["rover1"])
    b = environment(tmp_path, "t_mav_b", 7473, ["rover1"])
    b = Session(
        b.environment.model_copy(update={"network": Network(router_port=7473, mavlink_port=mavlink_port(7472))})
    )
    cleanup += [a, b]
    assert a.up(TIMEOUT) == 0
    assert b.up(TIMEOUT) != 0  # its MAVLink port is a's
    assert containers(b) == []
    assert containers(a)
