import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from protostar.config import ProtostarConfig
from protostar.errors import MissingDependencyError

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from .base import BootstrapModule

logger = logging.getLogger("protostar")


class PythonCore(BootstrapModule):
    """Configures a modern Python environment using uv as the fundamental baseline."""

    def __init__(
        self,
        python_version: str | None = None,
        project_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._python_version = python_version
        self.project_metadata = project_metadata or {}

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
            raise MissingDependencyError(
                dependency="uv",
                purpose="Python scaffolding",
                install_hint="Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`.",
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

        desc = self.project_metadata.get("description")
        name = self.project_metadata.get("author_name")
        email = self.project_metadata.get("author_email")
        github = self.project_metadata.get("github_username")
        min_python = self.project_metadata.get("minimum_python")
        supported_os: list[str] = self.project_metadata.get("supported_os", [])

        project_metadata_payload = "[project]\n"
        if desc:
            project_metadata_payload += f'description = "{desc}"\n'
        project_metadata_payload += 'readme = "README.md"\n'

        if name or email:
            author_str = ""
            if name:
                author_str += f'name = "{name}"'
            if email:
                if author_str:
                    author_str += ", "
                author_str += f'email = "{email}"'
            project_metadata_payload += f"authors = [\n    {{ {author_str} }}\n]\n"

        if min_python and supported_os:
            classifiers = []
            classifiers.append('"Programming Language :: Python :: 3"')

            try:
                major, minor = map(int, min_python.split("."))
                if major == 3:
                    for v in range(minor, 15):
                        classifiers.append(f'"Programming Language :: Python :: 3.{v}"')
            except Exception:
                pass

            for os_name in supported_os:
                if os_name == "MacOS":
                    classifiers.append('"Operating System :: MacOS"')
                elif os_name == "Linux":
                    classifiers.append('"Operating System :: POSIX :: Linux"')
                elif os_name == "Windows":
                    classifiers.append('"Operating System :: Microsoft :: Windows"')

            if classifiers:
                classifier_str = ",\n    ".join(classifiers)
                project_metadata_payload += f"""classifiers = [
    {classifier_str},
]
"""

        if github:
            repo_name = Path.cwd().name
            project_metadata_payload += f"""
[project.urls]
Repository = "https://github.com/{github}/{repo_name}"
Issues = "https://github.com/{github}/{repo_name}/issues"
"""

        manifest.add_file_append("pyproject.toml", project_metadata_payload)

        # --- IDE Injection ---
        config = ProtostarConfig.load()
        if config.ide in ("vscode", "cursor"):
            interpreter_path = Path.cwd() / ".venv" / "bin" / "python"
            manifest.add_ide_setting(
                "python.defaultInterpreterPath", str(interpreter_path)
            )
            manifest.add_ide_setting("python.terminal.activateEnvironment", True)
