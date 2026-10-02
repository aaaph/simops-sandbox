"""The session: a running bundle, from up to down -- one compose project, one gz partition."""

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from testcontainers.compose import DockerCompose

from simops import build_dir
from simops.bundle import Bundle, build, zenoh_gz

if TYPE_CHECKING:
    from simops.environment import Environment

# one container per line, tab-separated: its compose project, the simops labels of its bundle,
# its service, its bundle directory and its state; a label it lacks prints as an empty field
LABELS = ("com.docker.compose.project", "simops.session", "simops.router_port", "com.docker.compose.service")
PS_FORMAT = (
    "\t".join(
        [*(f'{{{{.Label "{label}"}}}}' for label in LABELS), '{{.Label "com.docker.compose.project.working_dir"}}']
    )
    + "\t{{.State}}"
)
DOCKER_PS = ["docker", "ps", "-a", "--filter", "label=com.docker.compose.project", "--format", PS_FORMAT]


class DockerUnavailableError(Exception):
    """Docker did not answer: never taken for no session running."""


class NotUpError(Exception):
    """No session to act on."""


class SeveralUpError(Exception):
    """Several sessions running and none named."""


def host_env(name: str, port: int, bundle: Path) -> dict[str, str]:
    """Say what gz and ROS on the host need to reach a session through its router, and where its meshes are."""
    return {
        "GZ_PARTITION": name,
        "GZ_TRANSPORT_IMPLEMENTATION": "zenoh",
        "GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE": zenoh_gz(port),
        "ZENOH_CONFIG_OVERRIDE": f'mode="client";connect/endpoints=["tcp/localhost:{port}"]',
        # the GUI loads the agents' meshes (model://<platform>/...) from the bundle
        "GZ_SIM_RESOURCE_PATH": str(bundle / "platforms"),
    }


@dataclass(frozen=True)
class RunningSession:
    """A session found from its containers alone: no environment file, no bundle needed to find it."""

    name: str  # the compose project, the gz partition
    router_port: int | None  # None: a compose project whose bundle has no simops labels
    bundle: Path  # where compose ran from: build/<name>/
    services: dict[str, str]  # service -> container state

    def host_env(self) -> dict[str, str]:
        """Say what gz and ROS on the host need to reach this session."""
        return host_env(self.name, self.router_port or 7447, self.bundle)


def sessions(ps: str) -> dict[str, RunningSession]:
    """Group the containers `DOCKER_PS` lists by compose project."""
    found: dict[str, RunningSession] = {}
    for line in filter(None, ps.splitlines()):
        project, session, port, service, bundle, state = line.split("\t")
        labelled = int(port) if session and port else None
        found.setdefault(project, RunningSession(project, labelled, Path(bundle), {})).services[service] = state
    return found


def read_sessions(command: list[str] = DOCKER_PS) -> dict[str, RunningSession]:
    """List every compose project's containers; Docker not answering is an error, not an empty list."""
    try:
        out = subprocess.run(command, capture_output=True, text=True, check=True).stdout
    except OSError, CalledProcessError:
        raise DockerUnavailableError("Docker does not answer: is it running?") from None
    return sessions(out)


def find(found: dict[str, RunningSession], name: str | None, service: str | None) -> RunningSession:
    """Pick the named session, or the only one; `service` must be running in it (None: any container will do)."""
    labelled = [s for s in found.values() if s.router_port is not None and name in (None, s.name)]
    if service is not None:
        labelled = [s for s in labelled if s.services.get(service) == "running"]
    if not labelled:
        raise NotUpError(f"{name} is not up" if name else "nothing is up")
    if len(labelled) > 1:
        raise SeveralUpError(f"several sessions are up, name one: {', '.join(sorted(s.name for s in labelled))}")
    return labelled[0]


def down(name: str) -> int:
    """Stop and remove every container of the session, exited ones and orphans too, by compose project."""
    return subprocess.run(["docker", "compose", "-p", name, "down", "--remove-orphans"], check=False).returncode


class Session:
    """The session of an environment: its compose project in build/<name>/ (see `build_dir`)."""

    def __init__(self, environment: Environment) -> None:
        """Name the session after its environment."""
        self.environment = environment
        self.dir = build_dir() / environment.name

    def project(self) -> DockerCompose:
        """Open the bundle as a compose project (its name is set in compose.yaml)."""
        return DockerCompose(self.dir, compose_file_name=str(self.dir / "compose.yaml"), wait=True)

    def host_env(self) -> dict[str, str]:
        """Say what gz and ROS on the host need to reach this session, from the environment alone."""
        return host_env(self.environment.name, self.environment.network.router_port, self.dir)

    def log_tail(self, lines: int = 15) -> None:
        """Print the last lines each service logged."""
        try:
            out, err = self.project().get_logs()
        except CalledProcessError:
            return
        tails: dict[str, list[str]] = {}
        for line in (out + err).splitlines():
            tails.setdefault(line.split(" | ", 1)[0].strip(), []).append(line)
        for tail in tails.values():
            print("\n".join(tail[-lines:]))

    def pose_stamp(self, world: str) -> float | None:
        """Sim time of one pose message that has every agent in it, or None."""
        echo = f". /opt/gz/activate.sh && timeout 10 gz topic -e -t /world/{world}/pose/info -n 1"
        try:
            out, _, _ = self.project().exec_in_container(["sh", "-c", echo], "world")
        except CalledProcessError:  # no pose message within the timeout: the world is not up yet
            return None
        if not all(f'name: "{name}"' in out for name in self.environment.agents):
            return None
        sec, nsec = re.search(r"sec: (\d+)", out), re.search(r"nsec: (\d+)", out)
        return int(sec.group(1)) + int(nsec.group(1)) * 1e-9 if sec and nsec else None

    def ready(self, bundle: Bundle) -> bool:
        """Check the agents are in the world and sim time moves -- a wedged server publishes once and stops."""
        first = self.pose_stamp(bundle.world_name)
        if first is None:
            return False
        time.sleep(1.5)
        second = self.pose_stamp(bundle.world_name)
        return second is not None and second > first

    def up(self, timeout: float) -> int:
        """Build the bundle, start the session, wait for the agents in a running sim; on failure leave nothing."""
        bundle = build(self.environment)
        bundle.write(self.dir)
        name = self.environment.name
        started = time.monotonic()
        print(f"starting {name} (images are built on first use; a PX4 build takes ~10 min)", flush=True)
        # compose itself, not DockerCompose.start(): that captures the output, and the build and the
        # containers coming up are what to watch here. --wait: every service runs, `spawn` exited 0
        up = [*self.project().docker_compose_command(), "up", "--wait"]
        if subprocess.run(up, check=False).returncode:
            print("last log lines:")
            self.log_tail()
            self.down()
            return 1
        print(f"waiting for {', '.join(self.environment.agents)} in the world and sim time moving", flush=True)
        deadline = time.monotonic() + timeout
        while not self.ready(bundle):
            if time.monotonic() > deadline:
                print(f"agents not in the world after {timeout:.0f} s; last log lines:")
                self.log_tail()
                self.down()
                return 1
            time.sleep(3)
        agents = ", ".join(self.environment.agents)
        port = self.environment.network.router_port
        mav, last = self.environment.network.mavlink_port, len(self.environment.agents) - 1
        print(
            f"{name} up in {time.monotonic() - started:.0f} s: {agents} in world {bundle.world_name!r}, "
            f"router localhost:{port}, mavlink udp localhost:{mav}{f'-{mav + last}' if last else ''}",
            flush=True,
        )
        return 0

    def down(self) -> int:
        """Stop and remove the session's containers."""
        return down(self.environment.name)

    def run(self, timeout: float, command: list[str]) -> int:
        """Up, run the command against the session, down whatever happens."""
        if self.up(timeout):
            return 1
        try:
            return subprocess.run(command, env=os.environ | self.host_env(), check=False).returncode
        finally:
            self.down()
