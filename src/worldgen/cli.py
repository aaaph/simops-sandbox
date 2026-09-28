"""The worldgen command."""

from pathlib import Path  # noqa: TC003 -- Typer reads the annotations at runtime
from typing import Annotated

import typer

from worldgen import room

app = typer.Typer(no_args_is_help=True, add_completion=False, rich_markup_mode=None)


@app.callback()
def main() -> None:
    """Generate SDF worlds; knows nothing of simops."""


@app.command("room")
def room_cmd(
    *,
    out: Annotated[Path, typer.Option("-o", "--out", help="SDF file to write")],
    clearance: Annotated[float, typer.Option(help="narrowest gap a robot needs, metres (its width + margin)")],
    seed: Annotated[int, typer.Option(help="same seed, same room")] = 0,
    size: Annotated[tuple[float, float], typer.Option(help="room X Y, metres")] = (10.0, 8.0),
    obstacles: Annotated[int, typer.Option(help="how many to place")] = 28,
    box_ratio: Annotated[float, typer.Option(help="share of boxes vs cylinders")] = 0.7,
    radius: Annotated[tuple[float, float], typer.Option(help="obstacle radius MIN MAX, metres")] = (0.15, 0.4),
    spawn_clear: Annotated[float | None, typer.Option(help="free radius at the origin (def: --clearance)")] = None,
    cell: Annotated[float, typer.Option(help="flood-fill resolution, metres")] = 0.05,
) -> None:
    """Generate a room: walls and scattered obstacles, every gap passable, all reachable from the origin."""
    try:
        summary = room.generate(
            out,
            clearance=clearance,
            seed=seed,
            size=size,
            obstacles=obstacles,
            box_ratio=box_ratio,
            radius=radius,
            spawn_clear=spawn_clear,
            cell=cell,
        )
    except ValueError as e:
        raise typer.BadParameter(str(e)) from None
    print(summary)
