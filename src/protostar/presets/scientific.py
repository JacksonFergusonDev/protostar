"""Dependency presets for data analysis and scientific computing."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class ScientificPreset(PresetModule):
    """Injects core scientific dependencies and standard pipeline directories."""

    cli_flags = ("-s", "--scientific")
    cli_help = "Inject scientific computing dependencies"

    @property
    def name(self) -> str:
        return "Scientific"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends scientific packages, directories, and data artifact ignores."""
        logger.debug("Building Scientific preset layer.")

        packages = [
            "numpy",
            "matplotlib",
            "seaborn",
            "pandas",
            "scipy",
            "ipykernel",
            "astropy",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)

        # Scaffold standard data analysis pipeline directories
        for directory in ["data", "notebooks", "src"]:
            manifest.add_directory(directory)

        # Ignore large or binary data files common in analysis pipelines
        for artifact in ["*.csv", "*.parquet", "*.nc"]:
            manifest.add_vcs_ignore(artifact)
