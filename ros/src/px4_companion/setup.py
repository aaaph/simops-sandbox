from setuptools import setup

setup(
    name="px4_companion",
    version="0.1.0",
    packages=["px4_companion"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/px4_companion"]),
        ("share/px4_companion", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    entry_points={
        "console_scripts": [
            "px4_odometry = px4_companion.px4_odometry:main",
            "frame_publisher = px4_companion.frame_publisher:main",
        ],
    },
)
