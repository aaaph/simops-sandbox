"""Run an environment -- world + agents + autopilot, described in one YAML file -- in Docker.

First the world, then the agents: the world starts empty, a one-shot `spawn` service
adds the environment's agents to it, and only then does each agent's autopilot attach.
`build` turns the environment into a bundle in build/<name>/ -- compose.yaml, spawn.sh,
bridge.yaml, the world and the platforms -- that plain `docker compose up` runs too.
`up` builds it, starts it and returns only once every agent is in the world and the
physics moves; if it cannot get there, it prints the log tail and leaves nothing running.
`run` does up, runs a command against the sim, and always tears it down. Every environment's
session is its own compose project and GZ_PARTITION, driven through testcontainers' DockerCompose.

\b
    pixi run simops up environments/rover_room.yaml
    pixi run simops run environments/rover_room.yaml -- pytest tests/
    pixi run simops host-env environments/rover_room.yaml | source   # fish; bash: eval "$(...)"
    pixi run simops down environments/rover_room.yaml
"""  # noqa: D301 -- `\b` keeps click from rewrapping the examples

import logging
import os
from pathlib import Path
from typing import Any

# the repository this editable install lives in: bundles go to build/, images build from infra/
ROOT = Path(__file__).resolve().parents[2]


def build_dir() -> Path:
    """Where bundles go, one directory per environment: $SIMOPS_BUILD_DIR, or build/ in this repository."""
    return Path(os.environ.get("SIMOPS_BUILD_DIR") or ROOT / "build").resolve()


# testcontainers logs every failed compose call at ERROR -- a readiness poll while the world boots
# included; simops prints the failures that matter itself
logging.getLogger("testcontainers").setLevel(logging.CRITICAL)


def describe(err: Any, document: str) -> str:  # noqa: ANN401 -- a pydantic ErrorDetails
    """Say where in the file the problem is and what it is; `document` names what the file is."""
    where = ".".join(str(part) for part in err["loc"])
    if err["type"] == "extra_forbidden":
        return f"`{where}` is not a key {document} defines"
    what = err["msg"].removeprefix("Value error, ")
    return f"{where}: {what}" if where else what
