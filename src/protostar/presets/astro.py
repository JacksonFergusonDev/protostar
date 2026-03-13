"""Preset module for astrophysics and observational data pipelines."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.config import ProtostarConfig

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

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return [
            "numpy",
            "scipy",
            "pandas",
            "matplotlib",
            "astropy",
            "astroquery",
            "photutils",
            "specutils",
            "nbdime",
        ]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["data/catalogs", "data/fits", "notebooks", "src"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return ["*.fits", "*.fit", "*.fts", "*.csv", "*.parquet"]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends preset-specific dependencies, attributes, and post-install tasks."""
        logger.debug(f"Building {self.name} preset layer.")

        # Apply defaults and overrides
        super().build(manifest)

        # 1. Inject .gitattributes for binary safety and notebook diffing
        gitattributes_content = (
            "# Astrophysics binary safety\n"
            "*.fits binary\n"
            "*.fit  binary\n"
            "*.fts  binary\n\n"
            "# Improve Jupyter Notebook diffs\n"
            "*.ipynb text eol=lf\n"
        )
        manifest.add_file_injection(".gitattributes", gitattributes_content)

        # 2. nbdime requires a git repository to configure
        if not Path(".git").exists():
            manifest.add_system_task(["git", "init"])

        # 3. Queue nbdime configuration
        config = ProtostarConfig.load()
        if config.python_package_manager == "uv":
            nbdime_cmd = ["uv", "run", "nbdime", "config-git", "--enable"]
        else:
            nbdime_cmd = [".venv/bin/nbdime", "config-git", "--enable"]

        manifest.add_post_install_task(nbdime_cmd)
