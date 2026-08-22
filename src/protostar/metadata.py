"""Project metadata definitions and resolution mechanisms for Protostar."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import UserConfig
from .enums import LicenseType, MetadataKey, PromptType, TargetOS
from .system import get_git_config


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
