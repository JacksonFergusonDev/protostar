"""Project metadata definitions and resolution mechanisms for Protostar."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import UserConfig
from .system import get_git_config


@dataclass
class MetadataField:
    """Definition of a metadata field for project scaffolding."""

    key: str
    label: str
    prompt_type: str  # "text" or "checkbox"
    choices: list[str] | None
    auto_resolver: Callable[[UserConfig], Any | None] | None
    default: Any | None


METADATA_FIELDS: dict[str, MetadataField] = {
    "description": MetadataField(
        key="description",
        label="Project description (optional, press Enter to skip):",
        prompt_type="text",
        choices=None,
        auto_resolver=None,
        default="",
    ),
    "author_name": MetadataField(
        key="author_name",
        label="Author name (optional, press Enter to skip):",
        prompt_type="text",
        choices=None,
        auto_resolver=lambda cfg: cfg.author_name or get_git_config("user.name"),
        default="",
    ),
    "author_email": MetadataField(
        key="author_email",
        label="Author email (optional, press Enter to skip):",
        prompt_type="text",
        choices=None,
        auto_resolver=lambda cfg: cfg.author_email or get_git_config("user.email"),
        default="",
    ),
    "github_username": MetadataField(
        key="github_username",
        label="GitHub username (optional, press Enter to skip):",
        prompt_type="text",
        choices=None,
        auto_resolver=lambda cfg: cfg.github_username,
        default="",
    ),
    "minimum_python": MetadataField(
        key="minimum_python",
        label="Minimum supported Python version:",
        prompt_type="text",
        choices=None,
        auto_resolver=lambda cfg: cfg.python_version,
        default="3.13",
    ),
    "supported_os": MetadataField(
        key="supported_os",
        label="Supported Operating Systems:",
        prompt_type="checkbox",
        choices=["MacOS", "Linux", "Windows"],
        auto_resolver=lambda cfg: cfg.supported_os if cfg.supported_os else None,
        default=["MacOS", "Linux", "Windows"],
    ),
    "docker_port": MetadataField(
        key="docker_port",
        label="Container exposed port:",
        prompt_type="text",
        choices=None,
        auto_resolver=None,
        default="8000",
    ),
}


def resolve_auto_metadata(
    keys: set[str] | None = None,
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
        config = UserConfig.load()

    resolved: dict[str, Any] = {}
    target_keys = set(METADATA_FIELDS.keys()) if keys is None else keys

    for key in target_keys:
        if key not in METADATA_FIELDS:
            continue

        field = METADATA_FIELDS[key]
        candidate_val = None
        if field.auto_resolver:
            candidate_val = field.auto_resolver(config)

        if candidate_val is not None:
            resolved[key] = candidate_val
        elif field.default is not None:
            resolved[key] = field.default

    return resolved
