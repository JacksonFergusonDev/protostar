import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from .base import BootstrapModule

logger = logging.getLogger("protostar")


class PythonModule(BootstrapModule):
    """Configures a modern Python environment using uv or pip."""

    cli_flags: ClassVar[tuple[str, ...]] = ("-p", "--python")
    cli_help: ClassVar[str] = "Scaffold a Python environment"

    def __init__(self, package_manager: str | None = None) -> None:
        self._package_manager = package_manager

    @property
    def package_manager(self) -> str:
        """Lazily evaluates the requested package manager from global config."""
        if self._package_manager is None:
            from protostar.config import ProtostarConfig

            self._package_manager = ProtostarConfig.load().python_package_manager
        return self._package_manager

    @property
    def name(self) -> str:
        """Returns the human-readable module name, including the package manager."""
        return f"Python ({self.package_manager})"

    def pre_flight(self) -> None:
        """Ensures the selected package manager is available."""
        if self.package_manager == "uv" and not shutil.which("uv"):
            raise RuntimeError(
                "Missing dependency: 'uv' is required for Python scaffolding. "
                "Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`."
            )
        elif self.package_manager == "pip" and not (
            shutil.which("python3") or shutil.which("python")
        ):
            raise RuntimeError(
                "Missing dependency: 'python' is required for pip scaffolding."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues initialization and ignores virtual environment artifacts."""
        logger.debug(f"Building Python language layer using {self.package_manager}.")

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

        if self.package_manager == "uv":
            if not Path("pyproject.toml").exists():
                manifest.add_system_task(["uv", "init", "--no-workspace"])
        elif self.package_manager == "pip" and not Path(".venv").exists():
            manifest.add_system_task(["python3", "-m", "venv", ".venv"])


class RustModule(BootstrapModule):
    """Configures a Rust environment using Cargo."""

    cli_flags: ClassVar[tuple[str, ...]] = ("-r", "--rust")
    cli_help: ClassVar[str] = "Scaffold a Rust (cargo) environment"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
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

    cli_flags: ClassVar[tuple[str, ...]] = ("-n", "--node")
    cli_help: ClassVar[str] = "Scaffold a Node.js environment"

    def __init__(self, package_manager: str | None = None) -> None:
        self._package_manager = package_manager

    @property
    def package_manager(self) -> str:
        """Lazily evaluates the requested package manager from global config."""
        if self._package_manager is None:
            from protostar.config import ProtostarConfig

            self._package_manager = ProtostarConfig.load().node_package_manager
        return self._package_manager

    @property
    def name(self) -> str:
        """Returns the human-readable module name, including the package manager."""
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

    cli_flags: ClassVar[tuple[str, ...]] = ("-c", "--cpp")
    cli_help: ClassVar[str] = "Scaffold a C/C++ environment footprint"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
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

    cli_flags: ClassVar[tuple[str, ...]] = ("-l", "--latex")
    cli_help: ClassVar[str] = "Scaffold a LaTeX environment footprint"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
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
