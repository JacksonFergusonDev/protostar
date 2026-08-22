"""Project metadata definitions and resolution mechanisms for Protostar."""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .system import get_git_config
from .workflows import TargetOS

if TYPE_CHECKING:
    from .config import UserConfig

__all__ = [
    "METADATA_FIELDS",
    "LicenseType",
    "MetadataField",
    "MetadataKey",
    "PromptType",
    "resolve_auto_metadata",
]


class PromptType(enum.StrEnum):
    """Enumeration of interactive prompt widget types."""

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


METADATA_FIELDS: dict[MetadataKey, MetadataField] = {
    MetadataKey.DESCRIPTION: MetadataField(
        key=MetadataKey.DESCRIPTION,
        label="Project description (optional, press Enter to skip):",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=None,
        default="",
    ),
    MetadataKey.LICENSE: MetadataField(
        key=MetadataKey.LICENSE,
        label="Project license:",
        prompt_type=PromptType.SELECT,
        choices=[lic.value for lic in LicenseType],
        auto_resolver=lambda cfg: cfg.license,
        default=LicenseType.MIT.value,
    ),
    MetadataKey.AUTHOR_NAME: MetadataField(
        key=MetadataKey.AUTHOR_NAME,
        label="Author name (optional, press Enter to skip):",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.author_name or get_git_config("user.name"),
        default="",
    ),
    MetadataKey.AUTHOR_EMAIL: MetadataField(
        key=MetadataKey.AUTHOR_EMAIL,
        label="Author email (optional, press Enter to skip):",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.author_email or get_git_config("user.email"),
        default="",
    ),
    MetadataKey.GITHUB_USERNAME: MetadataField(
        key=MetadataKey.GITHUB_USERNAME,
        label="GitHub username (optional, press Enter to skip):",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.github_username,
        default="",
    ),
    MetadataKey.MINIMUM_PYTHON: MetadataField(
        key=MetadataKey.MINIMUM_PYTHON,
        label="Minimum supported Python version:",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=lambda cfg: cfg.python_version,
        default="3.13",
    ),
    MetadataKey.SUPPORTED_OS: MetadataField(
        key=MetadataKey.SUPPORTED_OS,
        label="Supported Operating Systems:",
        prompt_type=PromptType.CHECKBOX,
        choices=[target_os.value for target_os in TargetOS],
        auto_resolver=lambda cfg: cfg.supported_os if cfg.supported_os else None,
        default=[target_os.value for target_os in TargetOS],
    ),
    MetadataKey.DOCKER_PORT: MetadataField(
        key=MetadataKey.DOCKER_PORT,
        label="Container exposed port:",
        prompt_type=PromptType.TEXT,
        choices=None,
        auto_resolver=None,
        default="8000",
    ),
}


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
