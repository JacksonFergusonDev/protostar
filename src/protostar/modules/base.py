import abc
import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class BootstrapModule(abc.ABC):
    """Appends module-specific requirements to the environment manifest.

    Args:
        manifest: The centralized state object to append requirements to.
    """

    cli_flags: ClassVar[tuple[str, ...]] = ()
    """The CLI flags to trigger this module (e.g., ('-p', '--python'))."""

    cli_help: ClassVar[str] = ""
    """The help description for the CLI flag."""

    config_key: ClassVar[str] = ""
    """The global configuration key used to evaluate if this module is active."""

    required_languages: ClassVar[tuple[str, ...] | None] = None
    """A tuple of language module class names required to activate this tooling."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the module."""
        pass

    @property
    def aliases(self) -> list[str]:
        """Returns a list of configuration aliases that map to this module.

        Used for dynamic resolution from the global configuration file.
        """
        return []

    @property
    def collision_markers(self) -> list[Path]:
        """Returns a list of critical filesystem paths to evaluate for collisions during pre-flight.

        Returns:
            A list of Path objects representing critical configuration files or directories
            managed by this module. Defaults to an empty list.
        """
        return []

    def pre_flight(self) -> None:  # noqa: B027
        """Verifies system prerequisites before manifest building begins.

        Raises:
            RuntimeError: If a critical dependency (e.g., 'uv', 'cargo') is missing.
        """
        pass

    @abc.abstractmethod
    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends module-specific requirements to the environment manifest.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        pass
