"""Workspace context and environment utilities for Protostar."""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError

__all__ = [
    "PackageName",
    "ProjectName",
    "PythonVersion",
    "check_python_version",
    "generate_python_version_range",
    "resolve_package_name",
    "resolve_project_name",
    "resolve_python_version",
    "sanitize_package_name",
    "validate_package_name",
    "validate_project_name",
]

_PYTHON_FLOAT_PATTERN = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
MIN_SUPPORTED_PYTHON_MINOR = 8
MAX_SUPPORTED_PYTHON_MINOR = 14


def check_python_version(version: object, *, label: str = "Python version") -> str:
    """Validates that a Python version is a float-like string within the supported range."""
    if not isinstance(version, str) or not _PYTHON_FLOAT_PATTERN.fullmatch(version):
        raise ConfigurationError(
            f"Invalid {label}: {version!r}.",
            hint=f"{label} must be a float value (e.g., '3.13').",
        )
    parts = version.split(".")
    major, minor = int(parts[0]), int(parts[1])
    if major != 3 or not (
        MIN_SUPPORTED_PYTHON_MINOR <= minor <= MAX_SUPPORTED_PYTHON_MINOR
    ):
        raise ConfigurationError(
            f"Invalid {label}: {version!r}.",
            hint=f"{label} is outside the accepted range (3.{MIN_SUPPORTED_PYTHON_MINOR} - 3.{MAX_SUPPORTED_PYTHON_MINOR}).",
        )
    return version


def validate_package_name(name: object) -> str:
    """Validates that a package name is a valid Python identifier."""
    if not isinstance(name, str) or not name.isidentifier():
        raise ConfigurationError(
            f"Invalid package name: {name!r}.",
            hint="Package name must be a valid Python identifier (e.g., 'my_package').",
        )
    return name


def validate_project_name(name: object) -> str:
    """Validates that a project name contains no illegal path characters."""
    if (
        not isinstance(name, str)
        or not name.strip()
        or any(c in name for c in ("/", "\\", "\x00"))
        or name in {".", ".."}
    ):
        raise ConfigurationError(
            f"Invalid project name: {name!r}.",
            hint="Project name cannot contain slashes or null bytes, and cannot be empty, '.', or '..'.",
        )
    return name


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
    if metadata:
        raw = metadata.get("minimum_python") or metadata.get("python_version")
        if raw:
            try:
                return str(PythonVersion.from_string(str(raw)))
            except ValueError:
                return str(raw)

    target_pyproject = pyproject_path or Path("pyproject.toml")
    if target_pyproject.exists():
        try:
            with target_pyproject.open("rb") as f:
                data = tomllib.load(f)
                project = data.get("project", {})
                req_python = (
                    project.get("requires-python", "")
                    if isinstance(project, dict)
                    else ""
                )
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
                project = data.get("project", {})
                name = project.get("name") if isinstance(project, dict) else None
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


def validate_resolver_workspace(root: Path) -> None:
    """Rejects resolver ownership outside the declared transaction workspace.

    An ancestor uv workspace is unsupported when it includes this project. Its
    resolver lock belongs to the ancestor and cannot be journaled locally.
    """
    import fnmatch
    import tomllib

    from .errors import ConfigurationError, FileSystemError

    root = root.resolve()
    for ancestor in root.parents:
        pyproject = ancestor / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except OSError as e:
            raise FileSystemError(
                "inspect resolver workspace", str(pyproject), e
            ) from e
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                "Malformed ancestor project configuration.",
                hint="Correct the ancestor pyproject.toml before resolving this project.",
            ) from e
        tool = data.get("tool", {})
        uv = tool.get("uv", {}) if isinstance(tool, dict) else {}
        workspace = uv.get("workspace") if isinstance(uv, dict) else None
        if workspace is None:
            continue
        if not isinstance(workspace, dict):
            raise ConfigurationError(
                "Malformed ancestor uv workspace.",
                hint="Correct the ancestor tool.uv.workspace table.",
            )
        relative = root.relative_to(ancestor).as_posix()
        members, excluded = workspace.get("members", []), workspace.get("exclude", [])
        if (
            not isinstance(members, list)
            or not isinstance(excluded, list)
            or not all(isinstance(p, str) for p in [*members, *excluded])
        ):
            raise ConfigurationError(
                "Invalid ancestor workspace membership.",
                hint="Use arrays of relative glob strings for workspace members and exclude.",
            )

        def matches(relative: str, pattern: str) -> bool:
            if "{" in pattern or "}" in pattern:
                raise ConfigurationError(
                    "Unsupported ancestor workspace glob.",
                    hint="Use explicit member paths or standard *, ?, [], and ** glob patterns.",
                )

            def match_parts(parts: list[str], patterns: list[str]) -> bool:
                if not patterns:
                    return not parts
                if patterns[0] == "**":
                    return match_parts(parts, patterns[1:]) or (
                        bool(parts) and match_parts(parts[1:], patterns)
                    )
                return (
                    bool(parts)
                    and fnmatch.fnmatchcase(parts[0], patterns[0])
                    and match_parts(parts[1:], patterns[1:])
                )

            return match_parts(
                relative.split("/"), pattern.removeprefix("./").rstrip("/").split("/")
            )

        if any(matches(relative, pattern) for pattern in members) and not any(
            matches(relative, pattern) for pattern in excluded
        ):
            raise ConfigurationError(
                "The uv resolver workspace lies outside the transaction boundary.",
                hint="Initialize from the owning workspace root or exclude this project from the ancestor uv workspace.",
            )
