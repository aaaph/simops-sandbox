from pathlib import Path

from setuptools import setup

NAME = "rover_differential_lidar_px4"
SHARE = f"share/{NAME}"

setup(
    name=NAME,
    version="0.1.0",
    packages=[],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{NAME}"]),
        (SHARE, ["package.xml", "model.sdf", "model.config", "bridge.yaml"]),
        (f"{SHARE}/launch", [str(p) for p in Path("launch").glob("*.launch.py")]),
    ],
    install_requires=["setuptools"],
)
