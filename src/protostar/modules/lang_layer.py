import importlib.resources
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.config import UserConfig
from protostar.errors import MissingDependencyError

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from protostar.workspace import generate_python_version_range

from .base import BootstrapModule

logger = logging.getLogger("protostar")


class PythonCore(BootstrapModule):
    """Configures a modern Python environment using uv as the fundamental baseline."""

    def __init__(
        self,
        python_version: str | None = None,
    ) -> None:
        self._python_version = python_version

    @property
    def python_version(self) -> str | None:
        """Lazily evaluates the requested python version from global config."""
        if self._python_version is None:
            self._python_version = UserConfig.load().python_version
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
            manifest.filesystem.add_environment_artifact(artifact)

        if not Path("pyproject.toml").exists():
            cmd = ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
            if self.python_version:
                cmd.extend(["--python", self.python_version])
            manifest.tasks.add_system_task(
                cmd, description="Scaffolding uv virtual environment"
            )

        desc = manifest.metadata.get("description") or "Add your description here."
        name = manifest.metadata.get("author_name") or "your-name"
        email = manifest.metadata.get("author_email") or "your-email"
        github = manifest.metadata.get("github_username")
        min_python = manifest.metadata.get("minimum_python")
        supported_os: list[str] = manifest.metadata.get("supported_os", [])

        project_metadata_payload = f"""[project]
description = "{desc}"
readme = "README.md"
authors = [{{ name = "{name}", email = "{email}" }}]
"""
        project_license = manifest.metadata.get("license")
        license_classifier = None
        if project_license and project_license != "None":
            license_map = {
                "MIT": ("mit.txt", "License :: OSI Approved :: MIT License"),
                "Apache-2.0": (
                    "apache_2_0.txt",
                    "License :: OSI Approved :: Apache Software License",
                ),
                "BSD-3-Clause": ("bsd_3.txt", "License :: OSI Approved :: BSD License"),
                "GPL-3.0": (
                    "gpl_3.txt",
                    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
                ),
                "LGPL-3.0": (
                    "lgpl_3.txt",
                    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
                ),
                "AGPL-3.0": (
                    "agpl_3.txt",
                    "License :: OSI Approved :: GNU Affero General Public License v3",
                ),
            }
            if project_license in license_map:
                filename, license_classifier = license_map[project_license]
                license_content = (
                    importlib.resources.files("protostar.licenses")
                    .joinpath(filename)
                    .read_text(encoding="utf-8")
                )
                manifest.filesystem.add_file_injection("LICENSE", license_content)
                project_metadata_payload += 'license = { file = "LICENSE" }\n'

        classifiers = []
        if min_python:
            classifiers.append('"Programming Language :: Python :: 3"')
            for version in generate_python_version_range(min_python):
                classifiers.append(f'"Programming Language :: Python :: {version}"')

        for os_name in supported_os:
            if os_name == "MacOS":
                classifiers.append('"Operating System :: MacOS"')
            elif os_name == "Linux":
                classifiers.append('"Operating System :: POSIX :: Linux"')
            elif os_name == "Windows":
                classifiers.append('"Operating System :: Microsoft :: Windows"')

        if license_classifier:
            classifiers.append(f'"{license_classifier}"')

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

        manifest.filesystem.add_file_append("pyproject.toml", project_metadata_payload)

        # --- IDE Injection ---
        config = UserConfig.load()
        if config.ide in ("vscode", "cursor"):
            interpreter_path = Path.cwd() / ".venv" / "bin" / "python"
            manifest.add_ide_setting(
                "python.defaultInterpreterPath", str(interpreter_path)
            )
            manifest.add_ide_setting("python.terminal.activateEnvironment", True)
