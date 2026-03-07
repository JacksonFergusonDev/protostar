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

    def __init__(
        self, package_manager: str | None = None, python_version: str | None = None
    ) -> None:
        self._package_manager = package_manager
        self._python_version = python_version

    @property
    def package_manager(self) -> str:
        """Lazily evaluates the requested package manager from global config."""
        if self._package_manager is None:
            from protostar.config import ProtostarConfig

            self._package_manager = ProtostarConfig.load().python_package_manager
        return self._package_manager

    @property
    def python_version(self) -> str | None:
        """Lazily evaluates the requested python version from global config."""
        if self._python_version is None:
            from protostar.config import ProtostarConfig

            self._python_version = ProtostarConfig.load().python_version
        return self._python_version

    @python_version.setter
    def python_version(self, value: str | None) -> None:
        self._python_version = value

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

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for a Python environment."""
        if self.package_manager == "uv":
            return [Path("pyproject.toml")]
        return [Path("requirements.txt")]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues initialization and ignores virtual environment artifacts."""
        logger.debug(f"Building Python language layer using {self.package_manager}.")

        artifacts = [
            ".venv/",
            "__pycache__/",
            "*.ipynb_checkpoints",
        ]
        for artifact in artifacts:
            manifest.add_environment_artifact(artifact)

        if self.package_manager == "uv":
            if not Path("pyproject.toml").exists():
                cmd = ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
                if self.python_version:
                    cmd.extend(["--python", self.python_version])
                manifest.add_system_task(cmd)
        elif self.package_manager == "pip" and not Path(".venv").exists():
            python_cmd = (
                f"python{self.python_version}" if self.python_version else "python3"
            )
            manifest.add_system_task([python_cmd, "-m", "venv", ".venv"])


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

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for a Rust environment."""
        return [Path("Cargo.toml")]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues cargo initialization, ignores, and pre-commit hooks."""
        logger.debug("Building Rust language layer.")
        manifest.add_environment_artifact("target/")

        hook_payload = """  - repo: https://github.com/doublify/pre-commit-rust
    rev: v1.0
    hooks:
      - id: fmt
      - id: clippy"""
        manifest.add_pre_commit_hook(hook_payload)

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

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for a Node environment."""
        return [Path("package.json")]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues package initialization, ignores, and pre-commit hooks."""
        logger.debug(f"Building Node language layer using {self.package_manager}.")

        artifacts = ["node_modules/", "dist/", ".next/"]
        for artifact in artifacts:
            manifest.add_environment_artifact(artifact)

        hook_payload = """  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.56.0
    hooks:
      - id: eslint"""
        manifest.add_pre_commit_hook(hook_payload)

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
        """Ignores standard C/C++ build outputs and injects formatter hooks."""
        logger.debug("Building C/C++ language layer.")

        artifacts = ["build/", "*.o", "*.out", ".cache/", "compile_commands.json"]
        for artifact in artifacts:
            manifest.add_environment_artifact(artifact)

        hook_payload = """  - repo: https://github.com/pre-commit/mirrors-clang-format
    rev: v18.1.5
    hooks:
      - id: clang-format"""
        manifest.add_pre_commit_hook(hook_payload)


class LatexModule(BootstrapModule):
    """Configures a LaTeX environment footprint."""

    cli_flags: ClassVar[tuple[str, ...]] = ("-l", "--latex")
    cli_help: ClassVar[str] = "Scaffold a LaTeX environment footprint"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "LaTeX"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Ignores LaTeX compiler auxiliary files and injects formatter hooks."""
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
            manifest.add_environment_artifact(artifact)

        hook_payload = """  - repo: https://github.com/aarnphm/tex-fmt
    rev: v0.4.5
    hooks:
      - id: tex-fmt"""
        manifest.add_pre_commit_hook(hook_payload)
