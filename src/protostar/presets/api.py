"""Preset module for REST API backend development."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class ApiPreset(PresetModule):
    """Injects backend framework dependencies and standard router directories."""

    cli_flags = ("--api",)
    cli_help = "Inject REST API backend dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "REST API"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["fastapi", "uvicorn", "pydantic", "httpx"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["api/routers", "core", "schemas"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return [".env", "*.pem", "*.key"]
