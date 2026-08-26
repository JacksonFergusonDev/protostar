"""Workspace context and environment utilities for Protostar."""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "PackageName",
    "ProjectName",
    "PythonVersion",
    "generate_python_version_range",
    "resolve_package_name",
    "resolve_project_name",
    "resolve_python_version",
    "sanitize_package_name",
]


@dataclass(frozen=True, order=True)
class PythonVersion:
    """Domain value object representing a Python semantic language version (e.g. 3.12)."""

    major: int
    minor: int

    def __post_init__(self) -> None:
        """Validates that major and minor version components are non-negative."""
        if self.major < 0 or self.minor < 0:
            raise ValueError(
                f"Invalid Python version numbers: {self.major}.{self.minor}"
            )

    @classmethod
    def from_string(cls, version_str: str) -> "PythonVersion":
        """Parses a version string (e.g. '3.13', '3.13.1', or '>=3.12') into a PythonVersion."""
        clean = re.sub(r"^[>=<^~=\s]+", "", version_str.strip())
        parts = clean.split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid Python version string: {version_str!r}")
        try:
            return cls(major=int(parts[0]), minor=int(parts[1]))
        except ValueError as e:
            raise ValueError(
                f"Invalid Python version components in {version_str!r}"
            ) from e

    @property
    def trove_classifier(self) -> str:
        """Returns the PEP 621 PyPI trove classifier for this Python version."""
        return f"Programming Language :: Python :: {self.major}.{self.minor}"

    def range_to(self, max_minor: int = 15) -> list["PythonVersion"]:
        """Generates a sequence of minor versions from this version up to max_minor."""
        if self.major == 3:
            return [
                PythonVersion(major=3, minor=m) for m in range(self.minor, max_minor)
            ]
        return [self]

    def __str__(self) -> str:
        """Returns the major.minor string representation."""
        return f"{self.major}.{self.minor}"


@dataclass(frozen=True)
class PackageName:
    """Domain value object representing a valid PEP 8 Python package identifier."""

    value: str

    def __post_init__(self) -> None:
        """Validates that the package name is a valid Python identifier."""
        if not self.value or not self.value.isidentifier():
            raise ValueError(f"Invalid Python package name identifier: {self.value!r}")

    @classmethod
    def from_raw(cls, raw: str) -> "PackageName":
        """Sanitizes raw text into a valid PEP 8 Python package identifier."""
        sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
        if not sanitized:
            sanitized = "app"
        elif sanitized[0].isdigit():
            sanitized = f"pkg_{sanitized}"
        return cls(value=sanitized)

    def __str__(self) -> str:
        """Returns the sanitized package name string."""
        return self.value


@dataclass(frozen=True)
class ProjectName:
    """Domain value object representing a repository or workspace project name."""

    value: str

    def __post_init__(self) -> None:
        """Validates that the project name is non-empty."""
        if not self.value.strip():
            raise ValueError("Project name cannot be empty.")

    def to_package_name(self) -> PackageName:
        """Derives a normalized Python package name from this project name."""
        return PackageName.from_raw(self.value)

    def __str__(self) -> str:
        """Returns the project name string."""
        return self.value


def resolve_python_version(
    metadata: Mapping[str, Any] | None = None,
    pyproject_path: Path | None = None,
    default: str | None = None,
) -> str:
    """Resolves the python version from metadata or pyproject.toml.

    Args:
        metadata: Optional dictionary containing resolved metadata.
        pyproject_path: Optional path to pyproject.toml. Defaults to Path("pyproject.toml").
        default: Optional fallback if all other sources are empty.

    Returns:
        The resolved python version string.
    """
    if metadata and metadata.get("python_version"):
        raw = str(metadata["python_version"])
        try:
            return str(PythonVersion.from_string(raw))
        except ValueError:
            return raw

    target_pyproject = pyproject_path or Path("pyproject.toml")
    if target_pyproject.exists():
        try:
            with target_pyproject.open("rb") as f:
                data = tomllib.load(f)
                req_python = data.get("project", {}).get("requires-python", "")
                match = re.search(r"(\d+\.\d+)", req_python)
                if match:
                    return str(PythonVersion.from_string(match.group(1)))
        except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError, KeyError):
            pass

    if default:
        return default

    return "3.13"


def generate_python_version_range(
    min_version: PythonVersion | str, max_minor: int = 15
) -> list[str]:
    """Generates a list of Python version strings from the minimum up to a maximum minor version.

    Args:
        min_version: The minimum Python version (e.g. "3.9" or PythonVersion(3, 9)).
        max_minor: The maximum minor version to generate up to. Defaults to 15.

    Returns:
        A list of version strings (e.g. ["3.9", "3.10", ...]).
    """
    try:
        pv = (
            min_version
            if isinstance(min_version, PythonVersion)
            else PythonVersion.from_string(str(min_version))
        )
        return [str(v) for v in pv.range_to(max_minor=max_minor)]
    except Exception:
        return []


def sanitize_package_name(name: str) -> str:
    """Sanitizes a project or directory name into a valid PEP 8 Python package identifier.

    Replaces hyphens, dots, spaces, and non-alphanumeric characters with underscores,
    collapses consecutive underscores, strips leading/trailing underscores, lowercases
    the result, and ensures the name does not start with a digit.

    Args:
        name: The raw project or package name string.

    Returns:
        A valid Python package identifier string.
    """
    return str(PackageName.from_raw(name))


def resolve_project_name(
    metadata: Mapping[str, Any] | None = None,
    pyproject_path: Path | None = None,
    default: str | None = None,
) -> str:
    """Resolves the human-facing project name from metadata, pyproject.toml, or directory.

    Args:
        metadata: Optional dictionary containing resolved metadata.
        pyproject_path: Optional path to pyproject.toml. Defaults to Path("pyproject.toml").
        default: Optional fallback if all other sources are empty.

    Returns:
        The resolved project name string.
    """
    if metadata and metadata.get("project_name"):
        return str(ProjectName(str(metadata["project_name"])))
    if metadata and metadata.get("name"):
        return str(ProjectName(str(metadata["name"])))

    target_pyproject = pyproject_path or Path("pyproject.toml")
    if target_pyproject.exists():
        try:
            with target_pyproject.open("rb") as f:
                data = tomllib.load(f)
                name = data.get("project", {}).get("name")
                if name:
                    return str(ProjectName(str(name)))
        except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError, KeyError):
            pass

    if default:
        return default

    return Path.cwd().name


def resolve_package_name(
    metadata: Mapping[str, Any] | None = None,
    pyproject_path: Path | None = None,
    default: str | None = None,
) -> str:
    """Resolves the normalized Python package name from metadata, pyproject.toml, or directory.

    Args:
        metadata: Optional dictionary containing resolved metadata.
        pyproject_path: Optional path to pyproject.toml. Defaults to Path("pyproject.toml").
        default: Optional fallback if all other sources are empty.

    Returns:
        A valid, sanitized Python package name string.
    """
    if metadata and metadata.get("package_name"):
        return sanitize_package_name(str(metadata["package_name"]))

    raw_name = resolve_project_name(
        metadata=metadata, pyproject_path=pyproject_path, default=default
    )
    return sanitize_package_name(raw_name)
