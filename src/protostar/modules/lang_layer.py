import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.config import ProtostarConfig

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from .base import BootstrapModule

logger = logging.getLogger("protostar")


class PythonCore(BootstrapModule):
    """Configures a modern Python environment using uv or pip as the fundamental baseline."""

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
        if self.package_manager == "pip" and not (
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
        """Queues initialization, ignores artifacts, and handles IDE telemetry bindings.

        Dynamically resolves the absolute path of the generated virtual environment
        and injects interpreter pointers into the workspace configuration if a
        supported IDE is active.

        Args:
            manifest: The centralized state object.
        """
        logger.debug(f"Building Python baseline layer using {self.package_manager}.")

        artifacts = [
            ".venv/",
            "__pycache__/",
        ]
        for artifact in artifacts:
            manifest.add_environment_artifact(artifact)

        if self.package_manager == "uv":
            if not Path("pyproject.toml").exists():
                cmd = ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
                if self.python_version:
                    cmd.extend(["--python", self.python_version])
                manifest.add_system_task(
                    cmd, description="Scaffolding uv virtual environment"
                )
        elif self.package_manager == "pip" and not Path(".venv").exists():
            python_cmd = (
                f"python{self.python_version}" if self.python_version else "python3"
            )
            manifest.add_system_task(
                [python_cmd, "-m", "venv", ".venv"],
                description="Scaffolding pip virtual environment",
            )

        # --- IDE Injection ---
        config = ProtostarConfig.load()
        if config.ide in ("vscode", "cursor"):
            interpreter_path = Path.cwd() / ".venv" / "bin" / "python"
            manifest.add_ide_setting(
                "python.defaultInterpreterPath", str(interpreter_path)
            )
            manifest.add_ide_setting("python.terminal.activateEnvironment", True)
