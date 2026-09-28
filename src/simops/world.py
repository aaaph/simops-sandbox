"""How an environment names its world: a room for worldgen to generate, or a ready-made SDF file."""

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


class World(BaseModel):
    """The environment's `world:` -- exactly one world source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generate_room: RoomSpec | None = None
    file: Path | None = None

    @model_validator(mode="before")
    @classmethod
    def _old_room(cls, data: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        if isinstance(data, dict) and "room" in data:
            msg = "`world.room` is now `world.generate_room` (or give `file`)"
            raise ValueError(msg)
        return data

    @field_validator("file")
    @classmethod
    def _relative_to_environment(cls, path: Path | None, info: ValidationInfo) -> Path | None:
        base = (info.context or {}).get("base")
        return (base / path).resolve() if path is not None and base is not None else path

    @model_validator(mode="after")
    def _one_source(self) -> World:
        if (self.generate_room is None) == (self.file is None):
            msg = "give exactly one world source: `generate_room` or `file`"
            raise ValueError(msg)
        return self

    @property
    def source(self) -> RoomSpec | WorldFile:
        """The world source this environment names."""
        return self.generate_room if self.generate_room is not None else WorldFile(path=self.file or Path())
