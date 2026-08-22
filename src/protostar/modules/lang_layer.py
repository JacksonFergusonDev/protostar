import importlib.resources
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.config import UserConfig
from protostar.errors import MissingDependencyError
from protostar.ide import IDEType
from protostar.metadata import LicenseType
from protostar.workflows import TargetOS

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from protostar.workspace import (
    PythonVersion,
    generate_python_version_range,
)

from .base import BootstrapModule

logger = logging.getLogger("protostar")


LICENSE_MAP: dict[str, tuple[str, str]] = {
    lic.value: (lic.resource_filename, lic.trove_classifier)
    for lic in LicenseType
    if lic.resource_filename is not None and lic.trove_classifier is not None
}


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
        supported_os: list[TargetOS | str] = manifest.metadata.get("supported_os", [])

        project_metadata_payload = f"""[project]
description = "{desc}"
readme = "README.md"
authors = [{{ name = "{name}", email = "{email}" }}]
"""
        project_license = manifest.metadata.get("license")
        license_classifier = None
        if (
            project_license
            and project_license != "None"
            and project_license in LICENSE_MAP
        ):
            filename, license_classifier = LICENSE_MAP[project_license]
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
            try:
                pv = (
                    min_python
                    if isinstance(min_python, PythonVersion)
                    else PythonVersion.from_string(str(min_python))
                )
                for ver in pv.range_to():
                    classifiers.append(f'"{ver.trove_classifier}"')
            except ValueError:
                for version in generate_python_version_range(min_python):
                    classifiers.append(f'"Programming Language :: Python :: {version}"')

        for os_name in supported_os:
            try:
                target_os = (
                    os_name if isinstance(os_name, TargetOS) else TargetOS(str(os_name))
                )
                classifiers.append(f'"{target_os.trove_classifier}"')
            except ValueError:
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
        if config.ide in (IDEType.VSCODE, IDEType.CURSOR):
            interpreter_path = Path.cwd() / ".venv" / "bin" / "python"
            manifest.add_ide_setting(
                "python.defaultInterpreterPath", str(interpreter_path)
            )
            manifest.add_ide_setting("python.terminal.activateEnvironment", True)
