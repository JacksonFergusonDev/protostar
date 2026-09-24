"""Pure typed declarations for managed contributions and template provenance."""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .errors import ConfigurationError


class TemplateOrigin(StrEnum):
    """Origin of the selected template bytes."""

    BUILT_IN = "built-in"
    LOCAL = "local"
    REMOTE = "remote"


@dataclass(frozen=True)
class TemplateReference:
    """Stable source identity plus informational revision provenance."""

    origin: TemplateOrigin
    locator: str
    digest: str
    display_name: str | None = None
    version: str | None = None
    source_revision: str | None = None

    @property
    def identity(self) -> str:
        """Returns a marker-safe source identity independent of payload revision."""
        return hashlib.sha256(
            f"{self.origin.value}:{self.locator}".encode()
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Returns deterministic provenance without trust or interpolation answers."""
        return {
            "origin": self.origin.value,
            "locator": self.locator,
            "digest": self.digest,
            "display_name": self.display_name,
            "version": self.version,
            "source_revision": self.source_revision,
        }


class StructuredFormat(StrEnum):
    """Explicit format of a managed structured contribution."""

    TOML = "toml"
    YAML = "yaml"


@dataclass(frozen=True)
class StructuredContribution:
    """A structured configuration contribution from one stable producer."""

    producer: str
    content: str
    resolver_footprint: ResolverFootprint | None = None
    format: StructuredFormat = StructuredFormat.TOML

    def to_dict(self) -> dict[str, Any]:
        """Serializes contribution intent."""
        return {
            "format": self.format.value,
            "producer": self.producer,
            "content": self.content,
            "resolver_footprint": self.resolver_footprint.to_dict()
            if self.resolver_footprint
            else None,
        }


def region_tag(identity: str) -> str:
    """Returns a deterministic 8-character hex tag for an append region identity."""
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]


@dataclass(frozen=True)
class PyprojectPayload:
    """A managed pyproject.toml payload, optionally tied to a tooling module.

    Attributes:
        content: TOML text merged into pyproject.toml.
        requires: Config key of the tool this payload configures. The payload is
            injected only while that tool is active; None means always.
    """

    content: str
    requires: str | None = None


@dataclass(frozen=True)
class AppendContribution:
    """A text region whose identity remains stable across payload revisions."""

    id: str
    content: str

    @property
    def tag(self) -> str:
        """Deterministic 8-character hex tag used in delimiter markers."""
        return region_tag(self.id)

    def to_dict(self) -> dict[str, str]:
        """Serializes stable region identity, delimiter tag, and desired bytes."""
        return {"id": self.id, "tag": self.tag, "content": self.content}


def validate_target(path: str) -> None:
    """Rejects escaping targets and the reserved engine state path."""
    target = Path(path)
    posix = PurePosixPath(path)
    win = PureWindowsPath(path)
    if (
        target.is_absolute()
        or posix.is_absolute()
        or bool(win.drive)
        or bool(win.root)
        or ".." in target.parts
        or not target.parts
        or any(part in ("protostar.lock", "uv.lock") for part in target.parts)
    ):
        raise ConfigurationError(
            f"Unsupported contribution target '{path}'.",
            hint="Use a relative workspace path outside reserved protostar.lock and resolver-owned uv.lock paths.",
        )


def validate_region_id(identity: str) -> None:
    """Requires a marker-safe stable identifier."""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:/-]*", identity):
        raise ConfigurationError(
            f"Invalid append identity '{identity}'.",
            hint="Use letters, numbers, underscores, dots, slashes, colons, or hyphens.",
        )


def validate_configuration(content: str) -> dict[str, Any]:
    """Parses configuration and rejects embedded operations/resolver bypasses."""
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise ConfigurationError(
            "Invalid structured TOML contribution.",
            hint="Correct the TOML payload syntax.",
        ) from e

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if "__replace__" in value or "__remove__" in value:
                raise ConfigurationError(
                    "Template control sentinels are unsupported.",
                    hint="Remove __replace__/__remove__; declare configuration values directly.",
                )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    project = data.get("project", {})
    tool = data.get("tool", {})
    uv = tool.get("uv", {}) if isinstance(tool, dict) else {}
    if (
        not isinstance(project, dict)
        or not isinstance(tool, dict)
        or not isinstance(uv, dict)
    ):
        raise ConfigurationError(
            "Configuration ancestors project, tool, and tool.uv must be tables.",
            hint="Declare TOML tables rather than replacing dependency-containing ancestors with scalar values.",
        )
    if (
        "dependency-groups" in data
        or (
            isinstance(project, dict)
            and any(k in project for k in ("dependencies", "optional-dependencies"))
        )
        or (isinstance(uv, dict) and "sources" in uv)
    ):
        raise ConfigurationError(
            "Generic configuration cannot manage dependency tables.",
            hint="Use dependencies, dev.dev_dependencies, docs_dependencies, or dependency_includes instead; uv sources and optional groups are unsupported.",
        )
    if "protostar" in tool:
        raise ConfigurationError(
            "The complete tool.protostar subtree is reserved for project intent.",
            hint="Remove recipe contributions from the template; edit the project recipe directly.",
        )
    return data


class DependencyGroup(StrEnum):
    """Supported dependency identities and uv installation targets."""

    MAIN = "main"
    DEV = "dev"
    DOCS = "docs"

    @property
    def cli_args(self) -> list[str]:
        """Returns uv add arguments for this group."""
        return {self.MAIN: [], self.DEV: ["--dev"], self.DOCS: ["--group", "docs"]}[
            self
        ]

    @property
    def label(self) -> str:
        """Returns the human-facing group label."""
        return {
            self.MAIN: "standard",
            self.DEV: "development",
            self.DOCS: "documentation",
        }[self]


@dataclass(frozen=True)
class DependencyInclude:
    """An explicitly declared dependency-group include edge."""

    group: DependencyGroup
    include: DependencyGroup

    def to_dict(self) -> dict[str, str]:
        """Serializes the include edge."""
        return {"group": self.group.value, "include": self.include.value}


@dataclass(frozen=True)
class ResolverFootprint:
    """Possible resolver-managed paths, declared before execution."""

    paths: tuple[str, ...] = ("pyproject.toml", "uv.lock")

    def to_dict(self) -> dict[str, list[str]]:
        """Serializes the bounded resolver footprint."""
        return {"paths": sorted(self.paths)}
