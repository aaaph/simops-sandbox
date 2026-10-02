"""Reaching a session from the host (host-access), its bundle (bundle), finding it (sim-lifecycle)."""

from pathlib import Path

import pytest

from simops import ROOT
from simops.session import (
    DockerUnavailableError,
    NotUpError,
    RunningSession,
    Session,
    SeveralUpError,
    find,
    read_sessions,
    sessions,
    using_mavlink,
)

# `docker ps -a` with PS_FORMAT: two simops sessions (b's world exited), a compose project of
# another tool, and a session from a bundle built before the labels
PS = """\
a\ta\t7447\t14540-14540\tzenoh-router\t/b/a\trunning
a\ta\t7447\t14540-14540\tworld\t/b/a\trunning
a\ta\t7447\t14540-14540\tspawn\t/b/a\texited
b\tb\t7448\t14590-14591\tzenoh-router\t/b/b\trunning
b\tb\t7448\t14590-14591\tworld\t/b/b\texited
other\t\t\t\tdb\t/elsewhere\trunning
old\t\t\t\tworld\t/b/old\trunning
"""


def test_bundle_directory(environment, build_dir, monkeypatch):
    assert Session(environment("elsewhere")).dir == build_dir / "elsewhere"  # SIMOPS_BUILD_DIR, set for tests
    monkeypatch.delenv("SIMOPS_BUILD_DIR")
    assert Session(environment("default")).dir == ROOT / "build/default"


def test_host_env(environment):
    env = Session(environment("rover_room")).host_env()
    assert env["GZ_PARTITION"] == "rover_room"
    assert env["GZ_TRANSPORT_IMPLEMENTATION"] == "zenoh"
    for key in ("GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE", "ZENOH_CONFIG_OVERRIDE"):
        assert "tcp/localhost:7447" in env[key]
    moved = Session(environment("moved", network={"router_port": 7448})).host_env()
    for key in ("GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE", "ZENOH_CONFIG_OVERRIDE"):
        assert "tcp/localhost:7448" in moved[key]
    assert env["GZ_SIM_RESOURCE_PATH"] == str(Session(environment("rover_room")).dir / "platforms")


def test_containers_grouped_by_session():
    found = sessions(PS)
    assert set(found) == {"a", "b", "other", "old"}
    assert found["a"] == RunningSession(
        "a", 7447, Path("/b/a"), {"zenoh-router": "running", "world": "running", "spawn": "exited"}, (14540, 14540)
    )
    assert found["b"].router_port == 7448
    assert found["other"].router_port is None  # no simops labels


def test_mavlink_ports_in_use():
    found = sessions(PS)
    assert using_mavlink(found, "c", 14540, 14540).name == "a"
    assert using_mavlink(found, "c", 14585, 14590).name == "b"  # ranges overlap at 14590
    assert using_mavlink(found, "c", 14541, 14589) is None
    assert using_mavlink(found, "a", 14540, 14540) is None  # its own ports: up again
    assert found["old"].mavlink_ports is None  # a bundle without the label is not checked


def test_running_session_host_env():
    env = sessions(PS)["b"].host_env()
    assert env["GZ_PARTITION"] == "b"
    assert "tcp/localhost:7448" in env["ZENOH_CONFIG_OVERRIDE"]
    assert env["GZ_SIM_RESOURCE_PATH"] == "/b/b/platforms"


def test_the_one_running_session():
    found = sessions(PS)
    assert find(found, None, "world").name == "a"  # b's world exited, other and old are no simops sessions
    assert find(found, "b", None).name == "b"  # down: any container will do
    assert find(found, "b", "zenoh-router").name == "b"


def test_named_session_not_up():
    with pytest.raises(NotUpError, match="b is not up"):
        find(sessions(PS), "b", "world")
    with pytest.raises(NotUpError, match="old is not up"):  # unlabelled: found by `down <name>` alone
        find(sessions(PS), "old", None)
    with pytest.raises(NotUpError, match="nothing is up"):
        find({}, None, None)


def test_several_sessions_up():
    with pytest.raises(SeveralUpError, match="a, b"):
        find(sessions(PS), None, "zenoh-router")


@pytest.mark.parametrize("command", [["false"], ["/no/such/docker", "ps"]])
def test_docker_not_answering_is_no_empty_list(command):
    with pytest.raises(DockerUnavailableError):
        read_sessions(command)
