import abc
import logging
from typing import TYPE_CHECKING, ClassVar

from protostar.manifest import Severity

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class PresetModule(abc.ABC):
    """Appends module-specific requirements to the environment manifest."""

    cli_flags: ClassVar[tuple[str, ...]] = ()
    """The CLI flags to trigger this preset (e.g., ('-a', '--astro'))."""

    cli_help: ClassVar[str] = ""
    """The help description for the CLI flag."""

    required_metadata: ClassVar[tuple[str, ...]] = ()
    """The metadata keys that MUST be resolved for this preset to function."""

    optional_metadata: ClassVar[tuple[str, ...]] = ()
    """The metadata keys that are nice to have but not strictly required."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the preset."""
        pass

    @property
    def config_key(self) -> str:
        """Returns the dictionary key used in config.toml for overrides."""
        return self.__class__.__name__.replace("Preset", "").lower()

    # --- Decision Note: Configuration Precedence Cascade ---
    # Protostar resolves component activation using the following strict priority (highest to lowest):
    #   1. Explicit CLI Flags (e.g., `--astro` / `--no-astro` override everything)
    #   2. Template Directives (`--from` or `--template` overrides global config)
    #   3. Local `[presets.<name>]` / `[env]` entries in user config.toml
    #   4. Preset / Module hardcoded default fallbacks
    def _apply_overrides(self, manifest: "EnvironmentManifest") -> bool:
        """Applies user-defined overrides from the global configuration if present.

        Returns:
            True if overrides were applied (and defaults should be skipped), False otherwise.
        """
        # Late import to prevent circular dependency at module initialization
        from protostar.config import UserConfig

        config = UserConfig.load()
        overrides = config.presets.get(self.config_key)

        if not isinstance(overrides, dict):
            return False

        manifest.add_diagnostic(
            phase=self.name,
            message="Applying custom configuration overrides. Default dependencies and directories were skipped.",
            severity=Severity.SKIP,
        )

        for dep in overrides.get("dependencies", []):
            manifest.add_dependency(dep)

        for dev_dep in overrides.get("dev_dependencies", []):
            manifest.add_dev_dependency(dev_dep)

        for directory in overrides.get("directories", []):
            manifest.add_directory(directory)

        for file_path, content in overrides.get("files", {}).items():
            manifest.add_file_injection(file_path, content)

        return True

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return []

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return []

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return []

    @property
    def default_files(self) -> dict[str, str]:
        """Returns a dict mapping file paths to their initial content to scaffold."""
        return {}

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends preset-specific dependencies and directories to the manifest.

        Automatically applies configuration overrides if present. Otherwise, injects
        the default packages, directories, and ignores defined by the preset subclass.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        logger.debug(f"Building {self.name} preset layer.")

        if self._apply_overrides(manifest):
            return

        for dep in self.default_dependencies:
            manifest.add_dependency(dep)

        for directory in self.default_directories:
            manifest.add_directory(directory)

        for artifact in self.default_ignores:
            manifest.add_vcs_ignore(artifact)

        for file_path, content in self.default_files.items():
            manifest.add_file_injection(file_path, content)
