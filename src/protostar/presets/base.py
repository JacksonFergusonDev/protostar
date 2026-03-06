import abc
import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class PresetModule(abc.ABC):
    """Appends module-specific requirements to the environment manifest.

    Args:
        manifest: The centralized state object to append requirements to.
    """

    cli_flags: ClassVar[tuple[str, ...]] = ()
    """The CLI flags to trigger this preset (e.g., ('-a', '--astro'))."""

    cli_help: ClassVar[str] = ""
    """The help description for the CLI flag."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the preset."""
        pass

    @property
    def config_key(self) -> str:
        """Returns the dictionary key used in config.toml for overrides."""
        return self.__class__.__name__.replace("Preset", "").lower()

    def _apply_overrides(self, manifest: "EnvironmentManifest") -> bool:
        """Applies user-defined overrides from the global configuration if present.

        Returns:
            True if overrides were applied (and defaults should be skipped), False otherwise.
        """
        # Late import to prevent circular dependency at module initialization
        from protostar.config import ProtostarConfig

        config = ProtostarConfig.load()
        overrides = config.presets.get(self.config_key)

        if not isinstance(overrides, dict):
            return False

        logger.debug(f"Applying custom configuration overrides for {self.name} preset.")

        for dep in overrides.get("dependencies", []):
            manifest.add_dependency(dep)

        for dev_dep in overrides.get("dev_dependencies", []):
            manifest.add_dev_dependency(dev_dep)

        for directory in overrides.get("directories", []):
            manifest.add_directory(directory)

        return True

    @abc.abstractmethod
    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends preset-specific dependencies and directories to the manifest.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        pass
