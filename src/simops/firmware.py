"""PX4 firmware: which versions run on this stack, and how a version or commit resolves."""

import re
import subprocess
import sys
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

# PX4 1.17 and earlier compile as C++14; the conda gz Jetty env's abseil requires C++17
MIN_PX4 = (1, 18)
PX4_REPO = "https://github.com/PX4/PX4-Autopilot.git"
VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(\d+))?")
STAGES = {"alpha": 0, "beta": 1, "rc": 2, None: 3}  # 3: a release


class PX4Firmware(BaseModel):
    """`autopilot.px4`: a release tag (`version`), a commit, or neither for the default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str = PX4_REPO
    version: str | None = None
    commit: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_ref(cls, data: Any) -> Any:  # noqa: ANN401 -- pydantic hands in the raw YAML value
        if isinstance(data, dict) and "ref" in data:
            msg = "`autopilot.px4.ref` is now `version` (a release tag) or `commit` (a full SHA)"
            raise ValueError(msg)
        return data

    @model_validator(mode="after")
    def _checks(self) -> PX4Firmware:
        """Check what can be checked offline: `down` and `host-env` never touch the network."""
        if self.version is not None and self.commit is not None:
            msg = "give `autopilot.px4.version` or `commit`, not both"
            raise ValueError(msg)
        if self.commit is not None and not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            msg = "`autopilot.px4.commit` must be the full 40-character SHA"
            raise ValueError(msg)
        if self.version is not None:
            v = parse_version(self.version)
            if v is None:
                msg = f"`autopilot.px4.version: {self.version}` is not a PX4 version like v1.18.0"
                raise ValueError(msg)
            if v[:2] < MIN_PX4:
                raise ValueError(unsupported(self.version))
        return self

    def resolve(self) -> tuple[str, str]:
        """Resolve to (tag or commit to build from, the commit); a version or the default needs the network."""
        if self.commit is not None:
            return self.commit, self.commit
        tags = parse_tags(ls_remote(self.repo))
        if self.version is not None:
            tag = self.version if self.version.startswith("v") else f"v{self.version}"
            if tag not in tags:
                sys.exit(f"PX4 {tag}: no such tag in {self.repo}")
        elif (tag := default_tag(tags)) is None:
            minimum = ".".join(map(str, MIN_PX4))
            sys.exit(f"{self.repo} has no tag of PX4 {minimum} or later: set `autopilot.px4.commit`")
        return tag, tags[tag]


def unsupported(version: str) -> str:
    """Say why a PX4 version cannot run on this stack."""
    return (
        f"PX4 {version} is not supported, the minimum is {'.'.join(map(str, MIN_PX4))}: "
        "PX4 1.17 and earlier compile as C++14, the gz Jetty toolchain needs C++17"
    )


def parse_version(text: str) -> tuple[int, int, int, int, int] | None:
    """Order key of a PX4 version (`v1.18.0`, `1.18.0-rc1`), or None if it is not one."""
    m = VERSION.fullmatch(text)
    if not m:
        return None
    major, minor, patch, stage, n = m.groups()
    return int(major), int(minor), int(patch), STAGES[stage], int(n or 0)


def parse_tags(ls_remote_output: str) -> dict[str, str]:
    """Map each tag of `git ls-remote --tags` to its commit; an annotated tag's peeled line wins."""
    tags: dict[str, str] = {}
    for line in ls_remote_output.splitlines():
        sha, _, ref = line.partition("\t")
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = sha
        else:
            tags.setdefault(name, sha)
    return tags


def default_tag(tags: dict[str, str]) -> str | None:
    """Newest supported release tag, else the newest supported pre-release, else None."""
    supported = {t: v for t in tags if (v := parse_version(t)) and v[:2] >= MIN_PX4}
    releases = [t for t, v in supported.items() if v[3] == STAGES[None]]
    pool = releases or list(supported)
    return max(pool, key=lambda t: supported[t]) if pool else None


def ls_remote(repo: str) -> str:
    """List the repository's tags (network)."""
    out = subprocess.run(["git", "ls-remote", "--tags", repo], capture_output=True, text=True, check=False)
    if out.returncode:
        sys.exit(f"cannot list the tags of {repo} (a `commit` builds offline): {out.stderr.strip()}")
    return out.stdout
