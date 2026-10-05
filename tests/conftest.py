"""Shared test fixtures, and the guard that keeps tests out of environments/, platforms/ and build/."""

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES, BUILD = (ROOT / "environments", ROOT / "platforms"), ROOT / "build"  # examples: the repository's own
# audit events that change the filesystem at their path arguments (`open` is looked at on its own)
WRITES = frozenset(
    {"os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.symlink", "shutil.rmtree", "shutil.copytree"}
)
FOUND: list[str] = []  # what tests did that they must not, see `guard`
USE_OWN = (
    "tests use their own environments and platforms (tests/simops/environments/, tests/simops/platforms/, "
    "the `environment` fixture)"
)
USE_TMP = "tests write to pytest's temporary directories (`tmp_path`, `build_dir`), not to build/"


def under(path: Any, root: Path) -> bool:  # noqa: ANN401 -- whatever an audit event carries
    """Whether `path` (a str or PathLike argument of an audit event) lies in `root`; no filesystem access."""
    if not isinstance(path, (str, os.PathLike)):
        return False  # a file descriptor, bytes, None
    # abspath: normalizes `..` without touching the filesystem (resolve() would, on every open)
    return Path(os.path.abspath(path)).is_relative_to(root)  # noqa: PTH100


def audit(event: str, args: tuple) -> None:
    """Record a read of the examples in environments/ or platforms/, or a write to build/ (a sys audit hook)."""
    if event == "open" and args:
        path, mode, flags = (*args, None, None)[:3]
        if isinstance(mode, str):
            writes = any(c in mode for c in "wax+")
        elif isinstance(path, (str, os.PathLike)) and not os.path.isabs(path):  # noqa: PTH117 -- no Path for an audit arg
            return  # os.open of a name inside a directory fd (shutil.rmtree, copytree): its directory is unknown
        else:  # os.open: flags only
            writes = bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
        if any(under(path, examples) for examples in EXAMPLES):
            FOUND.append(f"reads {path}: {USE_OWN}, not the examples")
        elif writes and under(path, BUILD):
            FOUND.append(f"writes {path}: {USE_TMP}")
    elif event in WRITES and any(under(a, BUILD) for a in args):
        FOUND.append(f"{event} in build/ ({args[0]}): {USE_TMP}")


sys.addaudithook(audit)


def pytest_collection_finish(session: pytest.Session) -> None:  # noqa: ARG001 -- the hook's signature
    """Refuse to run when a test module reads the examples or writes to build/ as it is imported."""
    if FOUND:
        raise pytest.UsageError("while collecting, a test module " + "; ".join(FOUND))


@pytest.fixture(autouse=True)
def guard() -> Iterator[list[str]]:
    """Fail a test that read the examples (environments/, platforms/) or wrote to build/, saying what instead."""
    FOUND.clear()
    yield FOUND
    if FOUND:
        found, FOUND[:] = list(FOUND), []
        pytest.fail("this test " + "; ".join(found), pytrace=False)


@pytest.fixture(scope="session", autouse=True)
def build_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Send every bundle simops writes -- `simops build`, `up`, the Docker tests -- to a temporary directory.

    No test writes to the repository's build/, so none touches the bundle of a session someone
    keeps up. The directory is only named here; simops creates it when a test writes a bundle.
    """
    out = tmp_path_factory.getbasetemp() / "build"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SIMOPS_BUILD_DIR", str(out))
        yield out
