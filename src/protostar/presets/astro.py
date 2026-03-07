"""Preset module for astrophysics and observational data pipelines."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class AstroPreset(PresetModule):
    """Injects core astrophysics dependencies and standard observational directories."""

    cli_flags = ("-a", "--astro")
    cli_help = "Inject astrophysics dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Astrophysics"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["astropy", "astroquery", "photutils", "specutils"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["data/catalogs", "data/fits"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return ["*.fits", "*.fit", "*.fts"]
