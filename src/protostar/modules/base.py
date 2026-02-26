import abc
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class BootstrapModule(abc.ABC):
    """Abstract base class for all environment bootstrapping modules.

    Modules represent a specific layer of the tech stack (OS, IDE, or Language)
    and are responsible for verifying dependencies and mutating the global
    manifest with required configurations.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the module."""
        pass

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
