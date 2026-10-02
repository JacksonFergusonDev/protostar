from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from protostar.metadata import MetadataKey
from protostar.system_deps import GlobalExecutable

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


@dataclass(frozen=True)
class PathSignal:
    """A workspace file or directory whose presence shows the tool is in use.

    Attributes:
        path: Workspace-relative POSIX path.
    """

    path: str


@dataclass(frozen=True)
class TableSignal:
    """A ``pyproject.toml`` table that configures the tool.

    Attributes:
        keys: Key path of the table, such as ``("tool", "ruff")``.
    """

    keys: tuple[str, ...]


@dataclass(frozen=True)
class SectionSignal:
    """A section of an INI file, such as ``setup.cfg``, that configures the tool.

    Attributes:
        path: Workspace-relative POSIX path of the INI file.
        section: Section name, such as ``mypy`` or ``tool:pytest``.
    """

    path: str
    section: str


@dataclass(frozen=True)
class RequirementSignal:
    """A package in any of the project's dependency lists.

    Attributes:
        name: Canonical package name, such as ``pre-commit``.
    """

    name: str


type Signal = PathSignal | TableSignal | SectionSignal | RequirementSignal


@dataclass(frozen=True)
class ToolInfo:
    """What a tool does, written for someone who has never heard of it.

    One record feeds ``--help``, the editor's tooltip and tool-information
    popup, and the configuration editor, so they can't drift apart.

    Attributes:
        summary: One line saying what the tool does for the project.
        adds: What enabling it adds or changes in the project.
        workflow: The practical consequence for day-to-day work.
        docs_url: The tool's official documentation.
    """

    summary: str
    adds: str
    workflow: str
    docs_url: str


class BootstrapModule(abc.ABC):
    """Appends module-specific requirements to the environment manifest."""

    cli_flags: ClassVar[tuple[str, ...]] = ()
    """The CLI flags to trigger this module (e.g., ('-p', '--python'))."""

    config_key: ClassVar[str] = ""
    """The global configuration key used to evaluate if this module is active."""

    required_metadata: ClassVar[tuple[MetadataKey | str, ...]] = ()
    """The metadata keys that MUST be resolved for this module to function."""

    optional_metadata: ClassVar[tuple[MetadataKey | str, ...]] = ()
    """The metadata keys that are nice to have but not strictly required."""

    @property
    def signals(self) -> tuple[Signal, ...]:
        """What in an existing project shows it already uses this module's tool."""
        return ()

    executables: ClassVar[tuple[GlobalExecutable, ...]] = ()
    """Executables the tool runs, beyond ``system_deps.REQUIRED``.

    Planning reports each one missing from ``PATH`` in
    ``EnvironmentManifest.missing_tools`` instead of failing.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the module."""
        pass

    @abc.abstractmethod
    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends module-specific requirements to the environment manifest.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        pass


class ToolModule(BootstrapModule):
    """Sets up one tool the user can switch on or off.

    ``info`` is abstract, so mypy rejects instantiating a tool that doesn't
    explain itself. A subclass satisfies it with a class attribute.
    """

    @property
    @abc.abstractmethod
    def info(self) -> ToolInfo:
        """What the tool does, for ``--help``, the schema, and the TUI."""

    def add_pyproject_config(self, manifest: EnvironmentManifest, config: str) -> None:
        """Injects a structured configuration payload into pyproject.toml."""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer=f"module:{self.__class__.__name__}"
        )
