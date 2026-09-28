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
from pathlib import Path

# the repository this editable install lives in: bundles go to build/, images build from infra/
ROOT = Path(__file__).resolve().parents[2]
# testcontainers logs every failed compose call at ERROR -- a readiness poll while the world boots
# included; simops prints the failures that matter itself
logging.getLogger("testcontainers").setLevel(logging.CRITICAL)
