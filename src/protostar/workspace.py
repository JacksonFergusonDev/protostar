"""Workspace context and environment utilities for Protostar."""

import re
import tomllib
from pathlib import Path
from typing import Any


def resolve_python_version(
    metadata: dict[str, Any] | None = None,
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
        return str(metadata["python_version"])

    target_pyproject = pyproject_path or Path("pyproject.toml")
    if target_pyproject.exists():
        try:
            with target_pyproject.open("rb") as f:
                data = tomllib.load(f)
                req_python = data.get("project", {}).get("requires-python", "")
                match = re.search(r"(\d+\.\d+)", req_python)
                if match:
                    return match.group(1)
        except Exception:
            pass

    if default:
        return default

    return "3.13"


def generate_python_version_range(min_version: str, max_minor: int = 15) -> list[str]:
    """Generates a list of Python version strings from the minimum up to a maximum minor version.

    Args:
        min_version: The minimum Python version (e.g. "3.9").
        max_minor: The maximum minor version to generate up to. Defaults to 15.

    Returns:
        A list of version strings (e.g. ["3.9", "3.10", ...]).
    """
    versions = []
    try:
        major, minor = map(int, min_version.split("."))
        if major == 3:
            for v in range(minor, max_minor):
                versions.append(f"3.{v}")
    except Exception:
        pass
    return versions


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
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if not sanitized:
        return "app"
    if sanitized[0].isdigit():
        return f"pkg_{sanitized}"
    return sanitized


def resolve_project_name(
    metadata: dict[str, Any] | None = None,
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
        return str(metadata["project_name"])
    if metadata and metadata.get("name"):
        return str(metadata["name"])

    target_pyproject = pyproject_path or Path("pyproject.toml")
    if target_pyproject.exists():
        try:
            with target_pyproject.open("rb") as f:
                data = tomllib.load(f)
                name = data.get("project", {}).get("name")
                if name:
                    return str(name)
        except Exception:
            pass

    if default:
        return default

    return Path.cwd().name


def resolve_package_name(
    metadata: dict[str, Any] | None = None,
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
