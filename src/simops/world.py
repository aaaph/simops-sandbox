"""How an environment names its world: a generated room, an open field, or a ready-made SDF file."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator


class RoomSpec(BaseModel):
    """A room worldgen generates: the same seed gives the same room."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int = 0
    size: tuple[float, float] | None = None
    obstacles: int | None = None


class WorldFile(BaseModel):
    """A ready-made SDF world."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Path


class EmptySpec(BaseModel):
    """An open field: no walls, no obstacles, just the ground and the start marker."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# the session's one clock: gz publishes it from the world, whatever the agents (spec: agent-interface)
CLOCK = {
    "ros_topic_name": "/clock",
    "gz_topic_name": "/clock",
    "ros_type_name": "rosgraph_msgs/msg/Clock",
    "gz_type_name": "gz.msgs.Clock",
    "direction": "GZ_TO_ROS",
}


class World(BaseModel):
    """The environment's `world:` -- exactly one world source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generate_room: RoomSpec | None = None
    file: Path | None = None
    empty_world: EmptySpec | None = None

    @model_validator(mode="before")
    @classmethod
    def _old_room(cls, data: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        if isinstance(data, dict) and "room" in data:
            msg = "`world.room` is now `world.generate_room` (or give `file`)"
            raise ValueError(msg)
        return data

    @model_validator(mode="before")
    @classmethod
    def _bare_empty_world(cls, data: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        # `empty_world:` with nothing after the colon parses as None; tell that apart from omitted.
        if isinstance(data, dict) and data.get("empty_world") is None and "empty_world" in data:
            data["empty_world"] = {}
        return data

    @field_validator("file")
    @classmethod
    def _relative_to_environment(cls, path: Path | None, info: ValidationInfo) -> Path | None:
        base = (info.context or {}).get("base")
        return (base / path).resolve() if path is not None and base is not None else path

    @model_validator(mode="after")
    def _one_source(self) -> World:
        given = sum(s is not None for s in (self.generate_room, self.file, self.empty_world))
        if given != 1:
            msg = "give exactly one world source: `generate_room`, `file` or `empty_world`"
            raise ValueError(msg)
        return self

    @property
    def bridge(self) -> list[dict]:
        """The world's own bridge entries, the same for every world source: its clock."""
        return [dict(CLOCK)]

    @property
    def source(self) -> RoomSpec | WorldFile | EmptySpec:
        """The world source this environment names."""
        if self.generate_room is not None:
            return self.generate_room
        if self.empty_world is not None:
            return self.empty_world
        return WorldFile(path=self.file or Path())
