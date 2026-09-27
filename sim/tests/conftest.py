"""Shared test fixtures."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

BUILD = Path(__file__).resolve().parents[2] / "build"


@pytest.fixture(autouse=True)
def remove_new_bundles() -> Iterator[None]:
    """Remove the build/<name>/ bundles a test created; bundles that were there before stay.

    A scenario someone keeps up needs its bundle for `down`, so only new ones go. Autouse
    fixtures are set up first and torn down last, after a test's own `down`.
    """
    before = set(BUILD.iterdir()) if BUILD.exists() else set()
    yield
    for bundle in (set(BUILD.iterdir()) if BUILD.exists() else set()) - before:
        shutil.rmtree(bundle, ignore_errors=True)
