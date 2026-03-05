"""Preset module for REST API backend development."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class ApiPreset(PresetModule):
    """Injects backend framework dependencies and standard router directories."""

    cli_flags = ("--api",)
    cli_help = "Inject REST API backend dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "REST API"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends web framework packages, schema directories, and security ignores.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building REST API preset layer.")

        packages = [
            "fastapi",
            "uvicorn",
            "pydantic",
            "httpx",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)

        # Scaffold domain-driven design topologies for API routing and schemas
        for directory in ["api/routers", "core", "schemas"]:
            manifest.add_directory(directory)

        # Mitigate credential leakage for local testing environments
        for artifact in [".env", "*.pem", "*.key"]:
            manifest.add_vcs_ignore(artifact)
