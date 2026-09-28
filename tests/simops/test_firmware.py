"""PX4 firmware: version order, tags, the default, resolution (spec: autopilot)."""

import pytest

import simops.firmware
from simops.firmware import PX4Firmware, default_tag, parse_tags, parse_version

RC1 = "fca3df865af36124a28c9d607e850f111dbaaea9"  # the commit v1.18.0-rc1 points to


def test_version_order():
    order = ["v1.17.0", "v1.18.0-alpha1", "v1.18.0-beta2", "v1.18.0-beta10", "v1.18.0-rc1", "v1.18.0"]
    assert sorted(order, key=lambda v: parse_version(v) or ()) == order
    assert parse_version("1.18.0") == parse_version("v1.18.0")
    assert parse_version("v1.18.0-beta1-foo") is None
    assert parse_version("main") is None


def test_parse_tags(ls_remote_text):
    tags = parse_tags(ls_remote_text)
    assert tags["v1.18.0-rc1"] == RC1  # peeled: the commit
    assert tags["v1.18.0-beta2"] == "1" * 40  # lightweight: the commit itself
    assert tags["v1.17.0"] == "d6f12ad1c4f70ad3230afd7d86e971421e02fef4"


def test_default_tag(ls_remote_text):
    tags = parse_tags(ls_remote_text)
    assert default_tag(tags) == "v1.18.0-rc1"  # no stable 1.18 yet: newest pre-release
    tags |= {"v1.18.0": "3" * 40, "v1.18.1-rc1": "4" * 40}
    assert default_tag(tags) == "v1.18.0"  # a release wins over any pre-release
    assert default_tag({"v1.17.0": "5" * 40}) is None


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize(
    ("firmware", "resolved"),
    [
        (PX4Firmware(version="v1.18.0-rc1"), ("v1.18.0-rc1", RC1)),
        (PX4Firmware(version="1.18.0-rc1"), ("v1.18.0-rc1", RC1)),
        (PX4Firmware(), ("v1.18.0-rc1", RC1)),  # the default
    ],
)
def test_resolve(firmware, resolved):
    assert firmware.resolve() == resolved


def test_commit_resolves_offline(monkeypatch):
    def offline(_repo):
        raise AssertionError("a commit must not need the network")

    monkeypatch.setattr(simops.firmware, "ls_remote", offline)
    commit = "4dbd2e069a5c30c2e53e47e842095d2576dc38c4"
    assert PX4Firmware(commit=commit).resolve() == (commit, commit)


@pytest.mark.usefixtures("no_network")
def test_unknown_version():
    with pytest.raises(SystemExit, match=r"v1\.18\.7: no such tag in https://github.com/PX4/PX4-Autopilot.git"):
        PX4Firmware(version="v1.18.7").resolve()
