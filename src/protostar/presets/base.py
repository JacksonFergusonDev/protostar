import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest


class PresetModule(abc.ABC):
    """Abstract base class for environment dependency and directory presets.

    Presets are decoupled from language modules and evaluate independently
    during the manifest aggregation phase to inject tools and scaffolding.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the preset."""
        pass

    @abc.abstractmethod
    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends preset-specific dependencies and directories to the manifest.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        pass
