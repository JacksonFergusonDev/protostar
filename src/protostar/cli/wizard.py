"""Remaining metadata and variable prompts after the recipe editor exits."""

from dataclasses import replace
from typing import Any

from rich.console import Console

from protostar.cli.prompts import Choice, Style, checkbox, select, text
from protostar.config import UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.init_draft import InitDraft
from protostar.metadata import METADATA_FIELDS, MetadataKey, PromptType
from protostar.modules import TOOLING_MODULES


def complete_init_draft(draft: InitDraft) -> InitDraft:
    """Collect the prompts that remain outside Textual until the next PR."""
    source = draft.template.source if draft.template else None
    values = dict(draft.existing_recipe.variables) if draft.existing_recipe else {}
    values.update(draft.variables)
    if source:
        values = {
            key: value for key, value in values.items() if key in source.variables
        }
        missing = sorted(source.variables - values.keys())
        if missing:
            values.update(prompt_template_variables(missing))
    else:
        values = {}
    selected = {tool for tool, enabled in draft.tool_choices or () if enabled}
    modules = [module for module in TOOLING_MODULES if module.config_key in selected]
    required = {key for module in modules for key in module.required_metadata}
    optional = {key for module in modules for key in module.optional_metadata}
    optional.update(
        (
            MetadataKey.DESCRIPTION,
            MetadataKey.AUTHOR_NAME,
            MetadataKey.AUTHOR_EMAIL,
            MetadataKey.GITHUB_USERNAME,
            MetadataKey.MINIMUM_PYTHON,
            MetadataKey.LICENSE,
        )
    )
    if draft.docker:
        optional.add(MetadataKey.DOCKER_PORT)
    metadata = prompt_metadata(required, optional)
    minimum = metadata.get("minimum_python")
    return replace(
        draft,
        variables=tuple(sorted(values.items())),
        python_version=str(minimum) if minimum else None,
        metadata=tuple(
            sorted(
                (key, tuple(value) if isinstance(value, list) else str(value))
                for key, value in metadata.items()
            )
        ),
    )


def prompt_metadata(
    required_keys: set[MetadataKey | str],
    optional_keys: set[MetadataKey | str] | None = None,
) -> dict[str, Any]:
    """Interactively prompts the user for project metadata.

    Args:
        required_keys: Keys that must be explicitly confirmed by the user.
        optional_keys: Optional metadata keys to prompt for with auto-resolved
            defaults.

    Returns:
        A dictionary of resolved metadata keys to user-confirmed values.

    Raises:
        ExecutionAbortedError: If the user cancels any prompt.
    """
    config = UserConfig.load()
    resolved: dict[str, Any] = {}
    all_keys = required_keys | (optional_keys or set())
    to_prompt = []

    for key in METADATA_FIELDS:
        if key not in all_keys and key.value not in all_keys:
            continue

        field = METADATA_FIELDS[key]
        candidate_val = None
        if field.auto_resolver:
            candidate_val = field.auto_resolver(config)

        default_val = candidate_val if candidate_val is not None else field.default
        to_prompt.append((key, field, default_val))

    for key, field, default_val in to_prompt:
        key_str = key.value if isinstance(key, MetadataKey) else str(key)
        if field.prompt_type == PromptType.TEXT:
            text_answer = text(
                field.label,
                default=str(default_val) if default_val is not None else "",
            )
            if text_answer is None:
                raise ExecutionAbortedError("Metadata configuration cancelled by user.")
            resolved[key_str] = text_answer
        elif field.prompt_type == PromptType.CHECKBOX:
            choices = []
            for choice_str in field.choices or []:
                checked = default_val is not None and choice_str in default_val
                choices.append(Choice(choice_str, checked=checked))

            checkbox_answer = checkbox(field.label, choices=choices)
            if checkbox_answer is None:
                raise ExecutionAbortedError("Metadata configuration cancelled by user.")
            resolved[key_str] = checkbox_answer
        elif field.prompt_type == PromptType.SELECT:
            select_choices = list(field.choices or [])
            if default_val is not None and str(default_val) in select_choices:
                select_choices.remove(str(default_val))
                select_choices.insert(0, str(default_val))

            select_answer = select(
                field.label,
                choices=select_choices,
                style=Style(
                    [
                        ("answer", "fg:cyan bold"),
                        ("pointer", "fg:cyan bold"),
                        (
                            "highlighted",
                            "nobold noitalic nounderline fg:default bg:default",
                        ),
                        (
                            "selected",
                            "nobold noitalic nounderline fg:default bg:default",
                        ),
                    ]
                ),
            )
            if select_answer is None:
                raise ExecutionAbortedError("Metadata configuration cancelled by user.")
            resolved[key_str] = select_answer

    return resolved


def prompt_template_variables(variables: list[str]) -> dict[str, str]:
    """Prompts for values for a template's custom variables.

    Args:
        variables: The variable names to ask for, in order.

    Returns:
        Each variable mapped to the value entered.

    Raises:
        ExecutionAbortedError: If the user cancels a prompt.
    """
    console = Console()
    console.print("\n[bold cyan]Template Variables[/bold cyan]")
    console.print(
        "Values are saved to pyproject.toml and rendered into project files, "
        "so don't enter secrets.\n"
    )

    values = {}
    for variable in variables:
        answer = text(f"{variable}:")
        if answer is None:
            raise ExecutionAbortedError("Variable entry cancelled by user.")
        values[variable] = answer

    return values
