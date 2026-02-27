"""Preset module for host-side embedded hardware interfacing."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class EmbeddedPreset(PresetModule):
    """Injects serial communication and hardware telemetry dependencies."""

    cli_flags = ("-e", "--embedded")
    cli_help = "Inject embedded hardware dependencies"

    @property
    def name(self) -> str:
        return "Embedded Hardware"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends host-side board communication packages."""
        logger.debug("Building Embedded Hardware preset layer.")

        packages = [
            "pyserial",
            "esptool",
            "adafruit-blinka",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)
