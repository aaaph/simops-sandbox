"""An open field: the ground and a start marker, no walls, no obstacles.

Its own parts -- just the start marker -- wrapped in `sdf.world`'s shared envelope, the same one
`room` uses. Does not depend on `room`: a room's walls and obstacles are that world type's own
concern.
"""

from typing import TYPE_CHECKING

from worldgen import sdf

if TYPE_CHECKING:
    from pathlib import Path


def generate(out: Path, *, clearance: float) -> str:
    """Generate an open field, write it to `out` and return a one-line summary."""
    out.write_text(sdf.world("field", [sdf.start_marker(clearance)]))
    return f"{out}: open field, clearance {clearance:.2f} m"
