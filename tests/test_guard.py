"""The guard in conftest.py: a test that reads the examples or writes to build/ fails."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_examples_and_build_are_off_limits(guard):
    # the audit events opening, making and removing files raise, without touching anything
    sys.audit("open", str(ROOT / "environments/rover_room.yaml"), "r", 0)
    sys.audit("open", str(ROOT / "build/x/compose.yaml"), "w", 0)
    sys.audit("os.mkdir", str(ROOT / "build/x"), 0o777, -1)
    sys.audit("open", str(ROOT / "platforms/p/model.sdf"), "r", 0)  # an example platform
    sys.audit("open", str(ROOT / "tests/simops/platforms/p/model.sdf"), "r", 0)  # the tests' own
    sys.audit("open", str(ROOT / "build/x/compose.yaml"), "r", 0)  # reading build/ is fine
    sys.audit("open", "/elsewhere/compose.yaml", "w", 0)
    sys.audit("open", 3, "w", 0)  # a file descriptor
    sys.audit("open", "platforms", None, os.O_RDONLY)  # os.open in a directory fd: rmtree of a bundle
    found = list(guard)
    guard.clear()  # the guard would fail this test otherwise
    assert len(found) == 4, found
    assert found[0].startswith("reads ")
    assert "own environments" in found[0]
    assert found[1].startswith("writes ")
    assert "temporary directories" in found[1]
    assert found[2].startswith("os.mkdir in build/")
    assert found[3].startswith(f"reads {ROOT / 'platforms'}")
    assert "own environments and platforms" in found[3]
