"""The environment: the YAML file naming the world and the agents in it -- the aggregate root."""

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from simops import describe
from simops.agent import Agent
from simops.world import World

if TYPE_CHECKING:
    from pathlib import Path


class InvalidEnvironment(Exception):  # noqa: N818 -- the glossary's word, not "...Error"
    """An environment file that cannot be loaded; the message names the file, the key and why."""


class Network(BaseModel):
    """`network:` -- where host ROS and the gz GUI reach the session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    router_port: int = 7447


class Environment(BaseModel):
    """The world and the agents of a simulation; describes no action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    world: World
    agents: dict[str, Agent]
    namespaces: bool = False
    network: Network = Network()

    @model_validator(mode="before")
    @classmethod
    def _moved_keys(cls, data: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        if isinstance(data, dict) and "robots" in data:
            msg = "`robots:` is now `agents:`"
            raise ValueError(msg)
        if isinstance(data, dict) and "autopilot" in data:
            msg = "`autopilot` is set in each platform's agent.yaml now (`autopilot.px4`), not in the environment"
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
        return cls.parse(data, base=path.resolve().parent, origin=path)

    @classmethod
    def parse(cls, data: Any, *, base: Path, origin: Path) -> Environment:  # noqa: ANN401 -- the raw YAML document
        """Validate an environment document; paths in it are relative to `base`, errors name `origin`."""
        try:
            return cls.model_validate(data, context={"base": base})
        except ValidationError as e:
            errors = "; ".join(describe(err, "an environment") for err in e.errors())
            raise InvalidEnvironment(f"{origin}: {errors}") from None
