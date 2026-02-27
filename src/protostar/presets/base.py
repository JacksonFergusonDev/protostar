import abc
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest


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

    @abc.abstractmethod
    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends preset-specific dependencies and directories to the manifest.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        pass
