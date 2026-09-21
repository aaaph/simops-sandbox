"""The sweep in stack.down() may only ever match this repo's own processes."""

import pytest
from stack import is_ours

ROOT = "/Users/me/l/simops-sandbox"


@pytest.mark.parametrize(
    "cmdline",
    [
        f"{ROOT}/.pixi/envs/default/libexec/gz/sim10/gz-sim-main -s -r {ROOT}/worlds/temp_room.sdf",
        f"{ROOT}/.pixi/envs/default/lib/robot_localization/ekf_node --ros-args -r __node:=ekf_filter_node",
        f"python3 {ROOT}/sim/odom_covariance.py --ros-args -r __node:=odom_covariance",
        f"{ROOT}/.pixi/envs/default/bin/python sim/rerun_bridge.py --ros-args -p use_sim_time:=true",
        f"{ROOT}/.pixi/envs/default/lib/python3.14/site-packages/rerun_sdk/rerun_cli/Rerun.app/Contents/MacOS/Rerun",
        f"{ROOT}/.pixi/envs/default/bin/python {ROOT}/.pixi/envs/default/bin/ros2 launch launch/bringup.launch.py",
    ],
)
def test_matches_our_stack(cmdline):
    assert is_ours(cmdline, ROOT)


@pytest.mark.parametrize(
    "cmdline",
    [
        # another project's rerun, and the viewer the rerun MCP server runs
        "/Users/me/l/vins-rnd/.venv/lib/python3.13/site-packages/rerun_sdk/rerun_cli/Rerun.app/Contents/MacOS/Rerun",
        "/Users/me/.local/share/uv/tools/rerun-sdk/bin/python /Users/me/.local/bin/rerun viewer-mcp",
        # an editor language server running out of our env: ours by path, not by name
        f"{ROOT}/.pixi/envs/default/bin/ruff server",
        # a sibling repo whose name starts the same way
        "/Users/me/l/simops-sandbox-old/.pixi/envs/default/lib/robot_localization/ekf_node",
        "pixi run --frozen down",
    ],
)
def test_leaves_everything_else_alone(cmdline):
    assert not is_ours(cmdline, ROOT)
