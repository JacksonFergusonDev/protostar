"""Dependency presets for data analysis and scientific computing."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class ScientificPreset(PresetModule):
    """Injects core scientific dependencies and standard pipeline directories."""

    cli_flags = ("-s", "--scientific")
    cli_help = "Inject scientific computing dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Scientific"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return [
            "numpy",
            "matplotlib",
            "seaborn",
            "pandas",
            "scipy",
            "ipykernel",
            "scikit-learn",
        ]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["data", "notebooks", "src"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return ["*.csv", "*.parquet", "*.nc"]
