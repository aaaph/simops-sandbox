"""The environment: the YAML file naming world, agents and PX4 firmware -- the aggregate root."""

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from simops.agent import Agent
from simops.firmware import PX4Firmware
from simops.world import World

if TYPE_CHECKING:
    from pathlib import Path


class InvalidEnvironment(Exception):  # noqa: N818 -- the glossary's word, not "...Error"
    """An environment file that cannot be loaded; the message names the file, the key and why."""


class Autopilot(BaseModel):
    """`autopilot:` -- one firmware for every agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    px4: PX4Firmware = PX4Firmware()


class Network(BaseModel):
    """`network:` -- where host ROS and the gz GUI reach the session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    router_port: int = 7447


class Environment(BaseModel):
    """World, agents and PX4 firmware of a simulation; describes no action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    world: World
    agents: dict[str, Agent]
    autopilot: Autopilot = Autopilot()
    namespaces: bool = False
    network: Network = Network()

    @model_validator(mode="before")
    @classmethod
    def _no_robots(cls, data: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        if isinstance(data, dict) and "robots" in data:
            msg = "`robots:` is now `agents:`"
            raise ValueError(msg)
        return data

    @model_validator(mode="after")
    def _namespaces_for_several(self) -> Environment:
        if len(self.agents) > 1 and not self.namespaces:
            msg = "several agents publish the same topics -- set `namespaces: true`"
            raise ValueError(msg)
        return self

    @classmethod
    def load(cls, path: Path) -> Environment:
        """Read an environment file; its paths are relative to the file's own directory."""
        try:
            data = yaml.safe_load(path.read_text())
        except OSError as e:
            raise InvalidEnvironment(f"{path}: {e.strerror}") from None
        try:
            return cls.model_validate(data, context={"base": path.resolve().parent})
        except ValidationError as e:
            raise InvalidEnvironment(f"{path}: " + "; ".join(_describe(err) for err in e.errors())) from None


def _describe(err: Any) -> str:  # noqa: ANN401 -- a pydantic ErrorDetails
    """Say where in the file the problem is and what it is."""
    where = ".".join(str(part) for part in err["loc"])
    if err["type"] == "extra_forbidden":
        return f"`{where}` is not a key an environment defines"
    what = err["msg"].removeprefix("Value error, ")
    return f"{where}: {what}" if where else what
