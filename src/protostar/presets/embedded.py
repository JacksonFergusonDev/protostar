"""Preset module for host-side embedded hardware interfacing."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class EmbeddedPreset(PresetModule):
    """Injects serial communication and hardware telemetry dependencies."""

    cli_flags = ("-e", "--embedded")
    cli_help = "Inject embedded hardware dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Embedded Hardware"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["pyserial", "esptool", "adafruit-blinka"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return []

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return []
