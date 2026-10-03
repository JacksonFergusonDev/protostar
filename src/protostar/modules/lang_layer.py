"""The Python baseline every project gets: uv, ``pyproject.toml``, license, and readme."""

from __future__ import annotations

import importlib.resources
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.ide import IDEType
from protostar.interpolation import quoted, render_template
from protostar.metadata import LicenseType
from protostar.workflows import TargetOS

if TYPE_CHECKING:
    from protostar.config import UserConfig
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


README = "README.md"
"""The readme ``[project]`` declares while the project has one."""


def declare_readme(manifest: EnvironmentManifest) -> None:
    """Declares the project's readme once one exists or is planned.

    Templates add their files after every module builds, so this runs last.
    Declaring a readme the project lacks breaks the build backend.

    Args:
        manifest: The planned project, with every file added.
    """
    if Path(README).is_file() or Path(README) in manifest.target_files():
        manifest.filesystem.add_structured(
            "pyproject.toml",
            f'[project]\nreadme = "{README}"\n',
            producer=f"module:{PythonCore.__name__}:readme",
        )


class PythonCore(BootstrapModule):
    """Configures a modern Python environment using uv as the fundamental baseline."""

    def __init__(
        self,
        python_version: str | None = None,
        user_config: UserConfig | None = None,
    ) -> None:
        self._python_version = python_version
        self._config = user_config

    @property
    def python_version(self) -> str | None:
        """Evaluates the requested python version."""
        if self._python_version is not None:
            return self._python_version
        if self._config is not None:
            return self._config.python_version
        return None

    @python_version.setter
    def python_version(self, value: str | None) -> None:
        self._python_version = value

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Python (uv)"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues initialization, ignores artifacts, and handles IDE configuration bindings.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Python baseline layer using uv.")

        artifacts = [
            ".venv/",
            "__pycache__/",
            ".cache/",
        ]
        for artifact in artifacts:
            manifest.filesystem.add_environment_artifact(artifact)

        if not Path("pyproject.toml").exists():
            cmd = ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
            version = (
                self._python_version
                or (manifest.recipe.python if manifest.recipe else None)
                or self.python_version
            )
            if version:
                cmd.extend(["--python", version])
            # --8<-- [start:owned_files]
            manifest.tasks.add_system_task(
                cmd,
                description="Initializing uv project",
                owned_files=["pyproject.toml", ".python-version"],
            )
            # --8<-- [end:owned_files]

        desc = manifest.metadata.get("description") or "Add your description here."
        name = manifest.metadata.get("author_name") or "your-name"
        email = manifest.metadata.get("author_email") or "your-email@example.com"
        github = manifest.metadata.get("github_username")
        min_python = manifest.metadata.get("minimum_python")
        supported_os: list[TargetOS | str] = manifest.metadata.get("supported_os", [])

        project_metadata_payload = f"""[project]
description = {quoted(str(desc))}
authors = [{{ name = {quoted(str(name))}, email = {quoted(str(email))} }}]
"""
        project_license = manifest.metadata.get("license")
        license_classifier = None
        if (
            project_license
            and project_license != "None"
            and project_license in LICENSE_MAP
        ):
            filename, license_classifier = LICENSE_MAP[project_license]
            license_content = render_template(
                importlib.resources.files("protostar.licenses")
                .joinpath(filename)
                .read_text(encoding="utf-8"),
                manifest.rendering_context(),
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
            if (target_os := TargetOS.from_string(os_name)) is not None:
                classifiers.append(f'"{target_os.trove_classifier}"')

        if license_classifier:
            classifiers.append(f'"{license_classifier}"')

        if classifiers:
            classifier_str = ",\n    ".join(classifiers)
            project_metadata_payload += f"""classifiers = [
    {classifier_str},
]
"""

        if github:
            repository = f"https://github.com/{github}/{Path.cwd().name}"
            project_metadata_payload += f"""
[project.urls]
Repository = {quoted(repository)}
Issues = {quoted(f"{repository}/issues")}
"""

        manifest.filesystem.add_structured(
            "pyproject.toml", project_metadata_payload, producer="module:PythonCore"
        )

        # --- IDE Injection ---
        if manifest.recipe:
            ide = manifest.recipe.ide
        elif self._config and self._config.ide:
            try:
                ide = (
                    self._config.ide
                    if isinstance(self._config.ide, IDEType)
                    else IDEType(self._config.ide)
                )
            except ValueError:
                ide = IDEType.NONE
        else:
            ide = IDEType.NONE
        if ide in (IDEType.VSCODE, IDEType.CURSOR):
            import sys

            if sys.platform == "win32":
                interpreter_path = Path.cwd() / ".venv" / "Scripts" / "python.exe"
            else:
                interpreter_path = Path.cwd() / ".venv" / "bin" / "python"
            manifest.add_ide_setting(
                "python.defaultInterpreterPath", str(interpreter_path)
            )
            manifest.add_ide_setting("python.terminal.activateEnvironment", True)
