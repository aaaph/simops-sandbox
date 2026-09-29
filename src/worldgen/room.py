"""Rooms: an SDF world with walls and randomly scattered boxes and cylinders.

Every gap is at least `clearance` wide, and a flood fill over the inflated configuration space
proves the whole room stays reachable from the spawn point (the origin). The same seed gives
the same room. worldgen knows nothing of simops: the caller says how wide the robot is.
"""

import math
import random
from collections import deque
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from worldgen.world import WALL_T, Obstacle, SdfWorld, Shape, StartMarker, Wall

if TYPE_CHECKING:
    from pathlib import Path

SIZE, OBSTACLES = (10.0, 8.0), 28


def place_obstacles(
    rng: random.Random,
    size: tuple[float, float],
    count: int,
    radius: tuple[float, float],
    box_ratio: float,
    clearance: float,
    spawn_clear: float,
    cell: float,
) -> list[Obstacle]:
    """Sample obstacle footprints, every gap at least `clearance` plus two cells of slack.

    Every shape is inscribed in its footprint, so the clearance math holds for any shape and yaw.
    """
    sx, sy = size
    slack = clearance + 2 * cell  # so the discretised check cannot fail on a corridor passable by a hair
    obs: list[Obstacle] = []
    for _ in range(count * 200):
        if len(obs) == count:
            break
        r = rng.uniform(*radius)
        m = r + WALL_T / 2 + slack
        x, y = rng.uniform(-sx / 2 + m, sx / 2 - m), rng.uniform(-sy / 2 + m, sy / 2 - m)
        if math.hypot(x, y) < spawn_clear + r:
            continue
        if any(math.hypot(x - o.x, y - o.y) < r + o.radius + slack for o in obs):
            continue
        shape = Shape.BOX if rng.random() < box_ratio else Shape.CYLINDER
        obs.append(Obstacle(f"obs_{len(obs)}", x, y, r, shape, rng.uniform(0, math.pi / 2)))
    return obs


def unreachable_cells(size: tuple[float, float], obs: list[Obstacle], clearance: float, cell: float) -> int:
    """Count free cells a robot `clearance` wide cannot reach from the origin (flood fill)."""
    sx, sy = size
    rad = clearance / 2
    nx, ny = int(sx / cell), int(sy / cell)

    def free(i: int, j: int) -> bool:
        x, y = -sx / 2 + (i + 0.5) * cell, -sy / 2 + (j + 0.5) * cell
        if abs(x) > sx / 2 - WALL_T / 2 - rad or abs(y) > sy / 2 - WALL_T / 2 - rad:
            return False
        return all(math.hypot(x - o.x, y - o.y) > o.radius + rad for o in obs)

    grid = [[free(i, j) for j in range(ny)] for i in range(nx)]
    seen = [[False] * ny for _ in range(nx)]
    start = (nx // 2, ny // 2)
    q = deque([start])
    seen[start[0]][start[1]] = True
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            u, v = i + di, j + dj
            if 0 <= u < nx and 0 <= v < ny and grid[u][v] and not seen[u][v]:
                seen[u][v] = True
                q.append((u, v))
    return sum(grid[i][j] and not seen[i][j] for i in range(nx) for j in range(ny))


def shape_boxes(rng: random.Random, obs: list[Obstacle]) -> list[Obstacle]:
    """Give each box its proportions, in placement order; the aspect keeps boxes from being needle-thin."""
    return [replace(o, aspect=rng.uniform(0.6, 1.0)) if o.shape is Shape.BOX else o for o in obs]


def room_walls(size: tuple[float, float]) -> list[Wall]:
    """Build the four walls between the room's corners; their end caps close the corners."""
    sx, sy = size
    nw, ne, se, sw = (-sx / 2, sy / 2), (sx / 2, sy / 2), (sx / 2, -sy / 2), (-sx / 2, -sy / 2)
    return [
        Wall.from_ab("wall_n", nw, ne),
        Wall.from_ab("wall_s", se, sw),
        Wall.from_ab("wall_e", ne, se),
        Wall.from_ab("wall_w", sw, nw),
    ]


def world(
    *,
    clearance: float,
    seed: int = 0,
    size: tuple[float, float] = SIZE,
    obstacles: int = OBSTACLES,
    box_ratio: float = 0.7,
    radius: tuple[float, float] = (0.15, 0.4),
    spawn_clear: float | None = None,
    cell: float = 0.05,
) -> SdfWorld:
    """Generate a room: walls, then obstacles, then the start marker. Touches no file.

    `clearance` is the narrowest gap a robot needs (its width plus a margin); `spawn_clear`, the
    free radius around the origin, defaults to it. Raises ValueError if the room is not reachable.
    """
    rng = random.Random(seed)
    spawn = spawn_clear if spawn_clear is not None else clearance
    obs = place_obstacles(rng, size, obstacles, radius, box_ratio, clearance, spawn, cell)
    if (walled_off := unreachable_cells(size, obs, clearance, cell)) != 0:
        msg = f"{walled_off} free cells are walled off from the spawn point"
        raise ValueError(msg)
    return SdfWorld("room", [*room_walls(size), *shape_boxes(rng, obs), StartMarker(clearance)])


def generate(
    out: Path,
    *,
    clearance: float,
    seed: int = 0,
    size: tuple[float, float] = SIZE,
    obstacles: int = OBSTACLES,
    **options: Any,  # noqa: ANN401 -- the rest of world()'s options, passed through
) -> str:
    """Generate a room (see `world`), write it to `out` and return a one-line summary."""
    room = world(clearance=clearance, seed=seed, size=size, obstacles=obstacles, **options)
    out.write_text(room.sdf())
    obs = [p for p in room.parts if isinstance(p, Obstacle)]
    boxes = sum(o.shape is Shape.BOX for o in obs)
    short = len(obs) < obstacles
    fit = f" (fit only {len(obs)}/{obstacles}: room too small or clearance too big)" if short else ""
    return (
        f"{out}: {boxes} boxes + {len(obs) - boxes} cylinders, {size[0]}x{size[1]} m, "
        f"clearance {clearance:.2f} m verified, seed {seed}{fit}"
    )
