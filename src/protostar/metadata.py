"""Project metadata definitions and resolution mechanisms for Protostar."""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .errors import ConfigurationError
from .system import get_git_config
from .workflows import TargetOS
from .workspace import check_python_version

if TYPE_CHECKING:
    from .config import UserConfig

__all__ = [
    "METADATA_FIELDS",
    "LicenseType",
    "MetadataField",
    "MetadataKey",
    "PromptType",
    "resolve_auto_metadata",
    "validate_docker_port",
    "validate_github_username",
    "validate_metadata",
    "validate_minimum_python",
]


class PromptType(enum.StrEnum):
    """The kind of field that collects a metadata value."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    SELECT = "select"


class MetadataKey(enum.StrEnum):
    """Enumeration of recognized project metadata keys."""

    DESCRIPTION = "description"
    LICENSE = "license"
    AUTHOR_NAME = "author_name"
    AUTHOR_EMAIL = "author_email"
    GITHUB_USERNAME = "github_username"
    MINIMUM_PYTHON = "minimum_python"
    SUPPORTED_OS = "supported_os"
    DOCKER_PORT = "docker_port"


class LicenseType(enum.StrEnum):
    """Enumeration of supported open source project licenses."""

    MIT = "MIT"
    APACHE_2_0 = "Apache-2.0"
    BSD_3_CLAUSE = "BSD-3-Clause"
    GPL_3_0 = "GPL-3.0"
    LGPL_3_0 = "LGPL-3.0"
    AGPL_3_0 = "AGPL-3.0"
    NONE = "None"

    @property
    def resource_filename(self) -> str | None:
        """Returns the bundled license template filename, or None if no license."""
        mapping = {
            LicenseType.MIT: "mit.txt",
            LicenseType.APACHE_2_0: "apache_2_0.txt",
            LicenseType.BSD_3_CLAUSE: "bsd_3.txt",
            LicenseType.GPL_3_0: "gpl_3.txt",
            LicenseType.LGPL_3_0: "lgpl_3.txt",
            LicenseType.AGPL_3_0: "agpl_3.txt",
            LicenseType.NONE: None,
        }
        return mapping[self]

    @property
    def trove_classifier(self) -> str | None:
        """Returns the PEP 621 PyPI trove classifier for this license, or None."""
        mapping = {
            LicenseType.MIT: "License :: OSI Approved :: MIT License",
            LicenseType.APACHE_2_0: "License :: OSI Approved :: Apache Software License",
            LicenseType.BSD_3_CLAUSE: "License :: OSI Approved :: BSD License",
            LicenseType.GPL_3_0: "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
            LicenseType.LGPL_3_0: "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
            LicenseType.AGPL_3_0: "License :: OSI Approved :: GNU Affero General Public License v3",
            LicenseType.NONE: None,
        }
        return mapping[self]


@dataclass
class MetadataField:
    """Definition of a metadata field for project scaffolding."""

    key: MetadataKey
    label: str
    prompt_type: PromptType
    choices: list[str] | None
    auto_resolver: Callable[[UserConfig], Any | None] | None
    default: Any | None
    validator: Callable[[Any], object] | None = None


_GITHUB_USERNAME_PATTERN = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$"
)


def validate_github_username(value: object) -> None:
    """Validates that a GitHub username matches GitHub naming rules if provided."""
    if value is None or value == "":
        return
    if not isinstance(value, str):
        raise ConfigurationError(
            f"Invalid GitHub username: {value!r}.",
            hint="GitHub username must be a string.",
        )
    if value.startswith("@"):
        raise ConfigurationError(
            f"Invalid GitHub username: {value!r}.",
            hint="Remove the leading '@' from GitHub username.",
        )
    if not _GITHUB_USERNAME_PATTERN.fullmatch(value):
        raise ConfigurationError(
            f"Invalid GitHub username: {value!r}.",
            hint="GitHub username may only contain alphanumeric characters and single hyphens, and cannot begin or end with a hyphen (maximum 39 characters).",
        )


def validate_docker_port(value: object) -> None:
    """Validates that a container port is an integer in the 1-65535 range."""
    port: int
    if isinstance(value, int) and not isinstance(value, bool):
        port = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        port = int(value.strip())
    else:
        raise ConfigurationError(
            f"Invalid container port: {value!r}.",
            hint="Container port must be an integer (e.g., '8000').",
        )
    if not (1 <= port <= 65535):
        raise ConfigurationError(
            f"Invalid container port: {value!r}.",
            hint="Container port is outside the accepted range (1 - 65535).",
        )


def validate_minimum_python(value: object) -> None:
    """Validates that a minimum Python version is a float within the supported range."""
    check_python_version(value, label="minimum Python version")


METADATA_FIELDS: dict[MetadataKey, MetadataField] = {
    MetadataKey.DESCRIPTION: MetadataField(
        key=MetadataKey.DESCRIPTION,
        label="Project description",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=None,
        default="",
    ),
    MetadataKey.LICENSE: MetadataField(
        key=MetadataKey.LICENSE,
        label="License",
        prompt_type=PromptType.SELECT,
        choices=[lic.value for lic in LicenseType],
        auto_resolver=lambda cfg: cfg.license,
        default=LicenseType.MIT.value,
    ),
    MetadataKey.AUTHOR_NAME: MetadataField(
        key=MetadataKey.AUTHOR_NAME,
        label="Author name",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.author_name or get_git_config("user.name"),
        default="",
    ),
    MetadataKey.AUTHOR_EMAIL: MetadataField(
        key=MetadataKey.AUTHOR_EMAIL,
        label="Author email",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.author_email or get_git_config("user.email"),
        default="",
    ),
    MetadataKey.GITHUB_USERNAME: MetadataField(
        key=MetadataKey.GITHUB_USERNAME,
        label="GitHub username",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.github_username,
        default="",
        validator=validate_github_username,
    ),
    MetadataKey.MINIMUM_PYTHON: MetadataField(
        key=MetadataKey.MINIMUM_PYTHON,
        label="Minimum Python version",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.python_version,
        default="3.13",
        validator=validate_minimum_python,
    ),
    MetadataKey.SUPPORTED_OS: MetadataField(
        key=MetadataKey.SUPPORTED_OS,
        label="Supported operating systems",
        prompt_type=PromptType.CHECKBOX,
        choices=[target_os.value for target_os in TargetOS],
        auto_resolver=lambda cfg: cfg.supported_os if cfg.supported_os else None,
        default=[target_os.value for target_os in TargetOS],
    ),
    MetadataKey.DOCKER_PORT: MetadataField(
        key=MetadataKey.DOCKER_PORT,
        label="Container port",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=None,
        default="8000",
        validator=validate_docker_port,
    ),
}


def validate_metadata(metadata: Mapping[str, Any]) -> None:
    """Validates all metadata fields present in the mapping against their defined validators."""
    for raw_key, field in METADATA_FIELDS.items():
        key_str = raw_key.value if isinstance(raw_key, MetadataKey) else str(raw_key)
        if key_str in metadata and field.validator is not None:
            field.validator(metadata[key_str])


def resolve_auto_metadata(
    keys: set[MetadataKey | str] | None = None,
    config: UserConfig | None = None,
) -> dict[str, Any]:
    """Deterministically resolves metadata values from configuration or defaults.

    Args:
        keys: Optional subset of metadata keys to resolve. If None, resolves all
            known fields.
        config: Optional UserConfig instance. If None, loads from global config.

    Returns:
        A dictionary mapping metadata keys to their resolved values.
    """
    if config is None:
        from .config import UserConfig

        config = UserConfig.load()

    resolved: dict[str, Any] = {}
    target_keys = set(METADATA_FIELDS.keys()) if keys is None else keys

    for raw_key in target_keys:
        if raw_key not in METADATA_FIELDS:
            continue

        field = METADATA_FIELDS[raw_key]  # type: ignore[index]
        candidate_val = None
        if field.auto_resolver:
            candidate_val = field.auto_resolver(config)

        key_str = str(raw_key.value if isinstance(raw_key, MetadataKey) else raw_key)
        if candidate_val is not None:
            resolved[key_str] = candidate_val
        elif field.default is not None:
            resolved[key_str] = field.default

    return resolved
