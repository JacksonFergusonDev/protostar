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
    """Configures a modern Python environment using uv as the fundamental baseline."""

    def __init__(self, python_version: str | None = None) -> None:
        self._python_version = python_version

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
        """Returns the human-readable module name."""
        return "Python (uv)"

    def pre_flight(self) -> None:
        """Ensures uv is available."""
        if not shutil.which("uv"):
            raise RuntimeError(
                "Missing dependency: 'uv' is required for Python scaffolding. "
                "Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`."
            )

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for a Python environment."""
        return [Path("pyproject.toml")]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues initialization, ignores artifacts, and handles IDE telemetry bindings.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Python baseline layer using uv.")

        artifacts = [
            ".venv/",
            "__pycache__/",
        ]
        for artifact in artifacts:
            manifest.add_environment_artifact(artifact)

        if not Path("pyproject.toml").exists():
            cmd = ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
            if self.python_version:
                cmd.extend(["--python", self.python_version])
            manifest.add_system_task(
                cmd, description="Scaffolding uv virtual environment"
            )

        # --- IDE Injection ---
        config = ProtostarConfig.load()
        if config.ide in ("vscode", "cursor"):
            interpreter_path = Path.cwd() / ".venv" / "bin" / "python"
            manifest.add_ide_setting(
                "python.defaultInterpreterPath", str(interpreter_path)
            )
            manifest.add_ide_setting("python.terminal.activateEnvironment", True)
