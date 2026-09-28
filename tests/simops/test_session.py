"""What host tools need to reach a session (spec: host-access)."""

from pathlib import Path

from simops.environment import Environment
from simops.session import Session

ENVIRONMENT = Path(__file__).resolve().parents[2] / "environments/rover_room.yaml"


def test_host_env(variant):
    env = Session(Environment.load(ENVIRONMENT)).host_env()
    assert env["GZ_PARTITION"] == "rover_room"
    assert env["GZ_TRANSPORT_IMPLEMENTATION"] == "zenoh"
    for key in ("GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE", "ZENOH_CONFIG_OVERRIDE"):
        assert "tcp/localhost:7447" in env[key]
    moved = Session(Environment.load(variant("moved", network={"router_port": 7448}))).host_env()
    for key in ("GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE", "ZENOH_CONFIG_OVERRIDE"):
        assert "tcp/localhost:7448" in moved[key]
