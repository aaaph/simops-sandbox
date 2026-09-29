"""What host tools need to reach a session (spec: host-access), and where its bundle is (spec: bundle)."""

from simops import ROOT
from simops.session import Session


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
