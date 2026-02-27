import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from .base import BootstrapModule

logger = logging.getLogger("protostar")


class PythonModule(BootstrapModule):
    """Configures a modern Python environment using uv."""

    @property
    def name(self) -> str:
        return "Python"

    def pre_flight(self) -> None:
        """Ensures 'uv' is installed and accessible."""
        if not shutil.which("uv"):
            raise RuntimeError(
                "Missing dependency: 'uv' is required for Python scaffolding. "
                "Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues uv initialization and ignores virtual environment artifacts."""
        logger.debug("Building Python language layer.")

        artifacts = [
            ".venv/",
            "__pycache__/",
            "*.ipynb_checkpoints",
            ".ruff_cache/",
            ".mypy_cache/",
        ]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)

        if not Path("pyproject.toml").exists():
            manifest.add_system_task(["uv", "init", "--no-workspace"])


class RustModule(BootstrapModule):
    """Configures a Rust environment using Cargo."""

    @property
    def name(self) -> str:
        return "Rust"

    def pre_flight(self) -> None:
        """Ensures 'cargo' is installed and accessible."""
        if not shutil.which("cargo"):
            raise RuntimeError(
                "Missing dependency: 'cargo' is required for Rust scaffolding. "
                "Install it via `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues cargo initialization and ignores target artifacts."""
        logger.debug("Building Rust language layer.")
        manifest.add_vcs_ignore("target/")
        manifest.add_workspace_hide("target/")

        if not Path("Cargo.toml").exists():
            manifest.add_system_task(["cargo", "init"])


class NodeModule(BootstrapModule):
    """Configures a Node.js/TypeScript environment."""

    def __init__(self, package_manager: str = "npm"):
        self.package_manager = package_manager

    @property
    def name(self) -> str:
        return f"Node ({self.package_manager})"

    def pre_flight(self) -> None:
        """Ensures the selected package manager is available."""
        if not shutil.which(self.package_manager):
            raise RuntimeError(
                f"Missing dependency: '{self.package_manager}' is required. "
                "Please install Node.js or the requested package manager."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues package initialization and ignores node_modules."""
        logger.debug(f"Building Node language layer using {self.package_manager}.")

        artifacts = ["node_modules/", "dist/", ".next/"]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)

        if not Path("package.json").exists():
            cmd = [self.package_manager, "init"]
            if self.package_manager == "npm":
                cmd.append("-y")
            manifest.add_system_task(cmd)


class CppModule(BootstrapModule):
    """Configures a C/C++ environment footprint."""

    @property
    def name(self) -> str:
        return "C/C++"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Ignores standard C/C++ build outputs and IDE command caches."""
        logger.debug("Building C/C++ language layer.")

        artifacts = ["build/", "*.o", "*.out", ".cache/", "compile_commands.json"]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)


class LatexModule(BootstrapModule):
    """Configures a LaTeX environment footprint."""

    @property
    def name(self) -> str:
        return "LaTeX"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Ignores LaTeX compiler auxiliary and log files."""
        logger.debug("Building LaTeX language layer.")

        artifacts = [
            "*.aux",
            "*.fdb_latexmk",
            "*.fls",
            "*.log",
            "*.synctex.gz",
            "*.bbl",
            "*.blg",
            "*.out",
        ]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)
