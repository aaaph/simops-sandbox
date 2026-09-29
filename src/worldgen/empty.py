"""An open field: the ground and a start marker, no walls, no obstacles.

Its only part -- the start marker -- in the envelope every SDF world shares, the same one `room`
uses. Does not depend on `room`: a room's walls and obstacles are that world type's own
concern.
"""

from typing import TYPE_CHECKING

from worldgen.world import SdfWorld, StartMarker

if TYPE_CHECKING:
    from pathlib import Path


def world(*, clearance: float) -> SdfWorld:
    """Generate an open field: its only part is the start marker. Touches no file."""
    return SdfWorld("field", [StartMarker(clearance)])


def generate(out: Path, *, clearance: float) -> str:
    """Generate an open field, write it to `out` and return a one-line summary."""
    out.write_text(world(clearance=clearance).sdf())
    return f"{out}: open field, clearance {clearance:.2f} m"
