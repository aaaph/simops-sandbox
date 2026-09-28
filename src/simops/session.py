"""The session: a running bundle, from up to down -- one compose project, one gz partition."""

import os
import re
import subprocess
import time
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from testcontainers.compose import DockerCompose

from simops import ROOT
from simops.bundle import Bundle, build, zenoh_gz

if TYPE_CHECKING:
    from simops.environment import Environment


class Session:
    """The session of an environment: its compose project under build/<name>/."""

    def __init__(self, environment: Environment) -> None:
        """Name the session after its environment."""
        self.environment = environment
        self.dir = ROOT / "build" / environment.name

    def project(self) -> DockerCompose:
        """Open the bundle as a compose project (its name is set in compose.yaml)."""
        return DockerCompose(self.dir, compose_file_name=str(self.dir / "compose.yaml"), wait=True)

    def host_env(self) -> dict[str, str]:
        """Say what gz and ROS on the host need to reach this session through its router."""
        port = self.environment.network.router_port
        return {
            "GZ_PARTITION": self.environment.name,
            "GZ_TRANSPORT_IMPLEMENTATION": "zenoh",
            "GZ_TRANSPORT_ZENOH_CONFIG_OVERRIDE": zenoh_gz(port),
            "ZENOH_CONFIG_OVERRIDE": f'mode="client";connect/endpoints=["tcp/localhost:{port}"]',
        }

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
        name = self.environment.name
        print(f"starting {name} (images are built on first use; a PX4 build takes ~10 min)", flush=True)
        try:
            self.project().start()  # up --wait: every service runs, `spawn` exited 0
        except CalledProcessError as e:
            print(e.stderr.decode(errors="ignore").strip(), "\nlast log lines:")
            self.log_tail()
            self.down()
            return 1
        deadline = time.monotonic() + timeout
        while not self.ready(bundle):
            if time.monotonic() > deadline:
                print(f"agents not in the world after {timeout:.0f} s; last log lines:")
                self.log_tail()
                self.down()
                return 1
            time.sleep(3)
        print(f"{name} up. GUI: `simops gui <environment>`, stop: `simops down <environment>`", flush=True)
        return 0

    def down(self) -> int:
        """Stop and remove the session's containers."""
        # DockerCompose.stop() leaves orphans: services dropped from a rebuilt bundle must go too
        command = [*self.project().docker_compose_command(), "down", "--remove-orphans"]
        return subprocess.run(command, check=False).returncode

    def run(self, timeout: float, command: list[str]) -> int:
        """Up, run the command against the session, down whatever happens."""
        if self.up(timeout):
            return 1
        try:
            return subprocess.run(command, env=os.environ | self.host_env(), check=False).returncode
        finally:
            self.down()
