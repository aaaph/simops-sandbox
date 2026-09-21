#!/usr/bin/env python3
"""Start and stop the whole simulation stack as one unit, so nothing is left running.

Built to be driven by an agent. `up` returns only once the robot is in the world
and the physics moves it, or tears everything down and says why -- it either
succeeds or leaves nothing behind. Every part runs in its own process group, recorded in .stack/,
with its log next to it. `down` kills those groups whole, then sweeps for anything
of ours that escaped one (ros2 launch children re-parent to launchd when their
wrapper dies). A watchdog runs `down` after a TTL, for when nobody remembers to.

    pixi run up [--slam] [--bridge] [--ttl MINUTES]
    pixi run down
"""

import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STACK = ROOT / ".stack"
STATE = STACK / "state.json"

PARTS = {
    "sim": ["pixi", "run", "--frozen", "bringup"],
    "slam": ["pixi", "run", "--frozen", "slam"],
    "bridge": ["pixi", "run", "--frozen", "rerun_bridge"],
}
# what the sweep may kill: our processes by name, and only when they run out of this
# repo -- so another project's rerun, the MCP viewer or an editor are never touched
OURS = (
    "gz-sim-main",
    "gz sim",
    "ros2 launch",
    "parameter_bridge",
    "ros_gz_sim/create",
    "ekf_node",
    "async_slam_toolbox_node",
    "robot_state_publisher",
    "frame_publisher.py",
    "odom_covariance.py",
    "rerun_bridge.py",
    "doctor.py",
    "Rerun.app",
    "ros2cli.daemon",
)


def is_ours(cmdline: str, root: str = str(ROOT)) -> bool:
    """Decide whether the sweep may kill a process, from its command line alone."""
    return f"{root}/" in cmdline and any(name in cmdline for name in OURS)


def processes() -> list[tuple[int, int, str]]:
    """Every process as (pid, pgid, command line)."""
    out = subprocess.run(
        ["ps", "-ax", "-o", "pid=,pgid=,command="], capture_output=True, text=True, check=False
    ).stdout
    rows = []
    for line in out.splitlines():
        pid, pgid, cmd = line.strip().split(None, 2)
        rows.append((int(pid), int(pgid), cmd))
    return rows


def odom_stamp() -> float | None:
    """Stamp of one wheel-odometry message straight from Gazebo, or None if none came."""
    try:
        out = subprocess.run(
            ["gz", "topic", "-e", "-t", "/odom", "-n", "1"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except subprocess.TimeoutExpired:
        return None
    sec = re.search(r"sec: (\d+)", out)
    nsec = re.search(r"nsec: (\d+)", out)
    return int(sec.group(1)) + int(nsec.group(1)) * 1e-9 if sec and nsec else None


def ready() -> bool:
    """Ready means the robot is in the world and the physics keeps moving it.

    World stats are not enough: the world steps well before the robot is spawned.
    One odometry message is not enough either -- a sim that wedges after its first
    step publishes exactly one. So: two messages, and time must have moved between them.
    """
    first = odom_stamp()
    if first is None:
        return False
    time.sleep(1.5)
    second = odom_stamp()
    return second is not None and second > first


def start(name: str) -> int:
    """Launch one part in a fresh session; its pid is its process group id."""
    log = (STACK / f"{name}.log").open("w")
    proc = subprocess.Popen(PARTS[name], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return proc.pid


def kill_group(pgid: int, sig: int) -> None:
    """Signal a whole group, ignoring groups that are already gone."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)


def up(args: argparse.Namespace) -> int:
    """Bring the stack up and wait until it is usable; on failure leave nothing running."""
    if STATE.exists():
        print("stack already up (.stack/state.json exists) -- run `pixi run down` first")
        return 1
    STACK.mkdir(exist_ok=True)
    groups = {"sim": start("sim")}
    STATE.write_text(json.dumps({"groups": groups}))

    deadline = time.monotonic() + args.timeout
    while not ready():
        if time.monotonic() > deadline:
            print(f"robot not moving in the sim after {args.timeout:.0f} s; last lines of .stack/sim.log:")
            print("".join((STACK / "sim.log").read_text().splitlines(keepends=True)[-15:]))
            down(argparse.Namespace(after=0.0))
            return 1
        time.sleep(3)

    for part in ("slam", "bridge"):
        if getattr(args, part):
            groups[part] = start(part)
    if args.ttl > 0:
        watchdog = subprocess.Popen(
            [sys.executable, __file__, "down", "--after", str(args.ttl * 60)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        groups["watchdog"] = watchdog.pid
    STATE.write_text(json.dumps({"groups": groups}))

    ttl = f", auto-down in {args.ttl:g} min" if args.ttl > 0 else ""
    print(f"stack up: {', '.join(groups)}{ttl}. Logs in .stack/, stop with `pixi run down`.")
    return 0


def down(args: argparse.Namespace) -> int:
    """Kill the recorded groups, then sweep up anything of ours that escaped them."""
    if args.after:
        time.sleep(args.after)
    own_group = os.getpgid(0)  # the watchdog runs this too, and must not kill itself mid-way
    groups = json.loads(STATE.read_text())["groups"] if STATE.exists() else {}
    targets = [g for g in groups.values() if g != own_group]

    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pgid in targets:
            kill_group(pgid, sig)
        strays = [(p, c) for p, g, c in processes() if is_ours(c) and p != os.getpid() and g != own_group]
        for pid, _ in strays:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, sig)
        time.sleep(3 if sig == signal.SIGTERM else 1)

    STATE.unlink(missing_ok=True)
    left = [c for p, g, c in processes() if is_ours(c) and p != os.getpid() and g != own_group]
    if left:
        print("still running after SIGKILL:\n  " + "\n  ".join(c[:120] for c in left))
        return 1
    print("stack down, nothing of ours left running.")
    return 0


def main() -> int:
    """Parse `up` / `down` and run it."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("up", help="start the stack and wait until the robot is in the world")
    p_up.add_argument("--slam", action="store_true", help="also start slam_toolbox")
    p_up.add_argument("--bridge", action="store_true", help="also start the rerun bridge")
    p_up.add_argument("--ttl", type=float, default=30, help="minutes until auto-down; 0 disables")
    p_up.add_argument("--timeout", type=float, default=120, help="seconds to wait for the physics")
    p_down = sub.add_parser("down", help="stop everything this repo started")
    p_down.add_argument("--after", type=float, default=0.0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    return up(args) if args.cmd == "up" else down(args)


if __name__ == "__main__":
    sys.exit(main())
