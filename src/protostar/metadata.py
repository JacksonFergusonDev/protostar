"""Project metadata definitions and resolution mechanisms for Protostar."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import questionary

from .config import ProtostarConfig
from .system import get_git_config


@dataclass
class MetadataField:
    """Definition of a metadata field for project scaffolding."""

    key: str
    label: str
    prompt_type: str  # "text" or "checkbox"
    choices: list[str] | None
    auto_resolver: Callable[[ProtostarConfig], Any | None] | None
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
}


def resolve_metadata(
    required_keys: set[str], optional_keys: set[str], *, tui_mode: bool
) -> dict[str, Any]:
    """Resolves metadata either from config/git or by prompting the user.

    Args:
        required_keys: Keys that MUST be explicitly confirmed by the user.
        optional_keys: Keys that can be silently auto-resolved in flags mode.
        tui_mode: Whether running in the TUI (prompt for everything possible) vs flags.

    Returns:
        A dictionary of resolved metadata keys to their values.
    """
    config = ProtostarConfig.load()
    resolved: dict[str, Any] = {}

    all_keys = required_keys | optional_keys
    to_prompt = []

    for key in METADATA_FIELDS:
        if key not in all_keys:
            continue

        field = METADATA_FIELDS[key]
        candidate_val = None
        if field.auto_resolver:
            candidate_val = field.auto_resolver(config)

        if key in required_keys:
            # Required fields are always explicitly prompted.
            # If we have a candidate value, pre-fill it as default.
            to_prompt.append((key, field, candidate_val or field.default))
        else:
            # Optional fields
            if tui_mode:
                # Prompt with auto-resolved default
                to_prompt.append((key, field, candidate_val or field.default))
            else:
                # Silently use auto-resolved value
                if candidate_val is not None:
                    resolved[key] = candidate_val
                elif field.default is not None and field.default != "":
                    resolved[key] = field.default

    # Execute prompts
    for key, field, default_val in to_prompt:
        if field.prompt_type == "text":
            resolved[key] = questionary.text(
                field.label, default=str(default_val) if default_val is not None else ""
            ).ask()
            if resolved[key] is None:
                raise KeyboardInterrupt
        elif field.prompt_type == "checkbox":
            choices = []
            for choice_str in field.choices or []:
                checked = default_val is not None and choice_str in default_val
                choices.append(questionary.Choice(choice_str, checked=checked))

            resolved[key] = questionary.checkbox(field.label, choices=choices).ask()
            if resolved[key] is None:
                raise KeyboardInterrupt

    return resolved
