"""Preset module for astrophysics and observational data pipelines."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class AstroPreset(PresetModule):
    """Injects core astrophysics dependencies and standard observational directories."""

    cli_flags = ("-a", "--astro")
    cli_help = "Inject astrophysics dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Astrophysics"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends observational packages, directories, and FITS file ignores."""
        logger.debug("Building Astrophysics preset layer.")

        packages = [
            "astropy",
            "sunpy",
            "gwpy",
            "astroquery",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)

        # Scaffold directories for standard observational data formats
        for directory in ["data/catalogs", "data/fits"]:
            manifest.add_directory(directory)

        # Ignore bulky telescope image artifacts
        for artifact in ["*.fits", "*.fit", "*.fts"]:
            manifest.add_vcs_ignore(artifact)
