"""Interactive Terminal User Interface (TUI) wizards for Protostar."""

import importlib.resources
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from .config import TemplateBlueprint, UserConfig
from .errors import ConfigurationError, ExecutionAbortedError
from .metadata import METADATA_FIELDS, MetadataKey, PromptType
from .modules import TOOLING_MODULES, BootstrapModule
from .system import is_interactive


@dataclass
class WizardSelections:
    """Selections captured from the interactive initialization wizard.

    Attributes:
        modules: Selected tooling modules.
        docker: If True, scaffolds container artifacts (.dockerignore).
        project_metadata: Resolved project metadata key-value mappings.
        blueprint: The loaded template blueprint, if any.
        is_external: If True, the template was loaded from an external source.
        is_user_aliased: If True, the template was resolved via a trusted global alias.
    """

    modules: list[BootstrapModule] = field(default_factory=list)
    docker: bool = False
    project_metadata: dict[str, Any] = field(default_factory=dict)
    blueprint: TemplateBlueprint | None = None
    is_external: bool = False
    is_user_aliased: bool = False


def _should_run_wizard() -> bool:
    """Evaluates if the environment supports interactive TTY prompts."""
    return is_interactive()


def run_init_wizard() -> WizardSelections | None:
    """Runs the environment initialization checklist.

    Dynamically constructs a spacebar-toggleable checklist from the module
    registries. Tooling options are dynamically pre-selected based on the
    user's global Protostar configuration.

    Returns:
        A WizardSelections instance containing the user's interactive choices,
        or None if in a non-interactive environment.

    Raises:
        ExecutionAbortedError: If the user cancels the wizard during interactive prompts.
    """
    if not _should_run_wizard():
        return None

    import questionary
    from questionary import Choice, Separator

    config = UserConfig.load()

    template_choices: list[Any] = ["None"]
    builtins = []

    try:
        template_dir = importlib.resources.files("protostar.templates")
        for item in template_dir.iterdir():
            if item.is_file() and item.name.endswith(".toml"):
                builtins.append(item.name[:-5])
    except (OSError, TypeError, ValueError, AttributeError, ModuleNotFoundError):
        pass

    if builtins:
        template_choices.append(Separator("--- Built-in Templates ---"))
        template_choices.extend(builtins)

    if config.templates:
        template_choices.append(Separator("--- External Aliases ---"))
        template_choices.extend(config.templates.keys())

    answer = "None"
    if len(template_choices) > 1:
        if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
            answer = "None"
        else:
            answer = questionary.select(
                "Start from a template?",
                choices=template_choices,
            ).ask()

        if answer is None:
            raise ExecutionAbortedError("Template selection cancelled by user.")

    blueprint = None
    is_external = False
    is_user_aliased = False

    if answer != "None":
        config = UserConfig.load(force_reload=True)
        if answer in builtins:
            target = str(
                importlib.resources.files("protostar.templates").joinpath(
                    f"{answer}.toml"
                )
            )
        elif answer in config.templates:
            target = config.templates[answer]
            is_external = True
            is_user_aliased = True
        else:
            raise ExecutionAbortedError(
                f"Template selection '{answer}' could not be resolved."
            )

        blueprint = TemplateBlueprint.load(
            target, variable_resolver=resolve_missing_variables
        )

    choices: list[Choice | Separator] = []

    # Context & Tooling
    choices.append(Separator("--- Context & Tooling ---"))
    choices.append(Choice(title="Docker (Dockerfile & .dockerignore)", value="docker"))

    for tool_mod in TOOLING_MODULES:
        is_checked = getattr(config, tool_mod.config_key, False)
        label_suffix = ""

        if blueprint and tool_mod.config_key in blueprint.tooling_overrides:
            blueprint_val = blueprint.tooling_overrides[tool_mod.config_key]
            if blueprint_val != is_checked:
                is_checked = blueprint_val
                label_suffix = " (Enforced by template)"

        choices.append(
            Choice(
                title=f"{tool_mod.name}{label_suffix}",
                value=tool_mod,
                checked=is_checked,
            )
        )

    if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
        sys.exit(0)

    selected = questionary.checkbox(
        "Select the components for your new environment:",
        choices=choices,
    ).ask()

    if selected is None:
        raise ExecutionAbortedError("Component selection cancelled by user.")

    modules = [item for item in selected if item in TOOLING_MODULES]
    docker = "docker" in selected

    required_keys: set[MetadataKey | str] = set()
    optional_keys: set[MetadataKey | str] = set()
    for mod in modules:
        required_keys.update(mod.required_metadata)
        optional_keys.update(mod.optional_metadata)

    # Core project metadata always requested as optional
    optional_keys.update(
        (
            MetadataKey.DESCRIPTION,
            MetadataKey.AUTHOR_NAME,
            MetadataKey.AUTHOR_EMAIL,
            MetadataKey.GITHUB_USERNAME,
            MetadataKey.MINIMUM_PYTHON,
            MetadataKey.LICENSE,
        )
    )

    if docker:
        optional_keys.add(MetadataKey.DOCKER_PORT)

    console = Console()
    console.print("\n[bold cyan]--- Project Metadata ---[/bold cyan]")
    console.print(
        "\n[dim]Hint: You can skip these prompts in the future by adding your details to the global config (run `protostar config`).[/dim]"
    )

    resolved_metadata = prompt_metadata(required_keys, optional_keys)

    return WizardSelections(
        modules=modules,
        docker=docker,
        project_metadata=resolved_metadata,
        blueprint=blueprint,
        is_external=is_external,
        is_user_aliased=is_user_aliased,
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
    import questionary

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
            answer = questionary.text(
                field.label,
                default=str(default_val) if default_val is not None else "",
            ).ask()
            if answer is None:
                raise ExecutionAbortedError("Metadata configuration cancelled by user.")
            resolved[key_str] = answer
        elif field.prompt_type == PromptType.CHECKBOX:
            choices = []
            for choice_str in field.choices or []:
                checked = default_val is not None and choice_str in default_val
                choices.append(questionary.Choice(choice_str, checked=checked))

            answer = questionary.checkbox(field.label, choices=choices).ask()
            if answer is None:
                raise ExecutionAbortedError("Metadata configuration cancelled by user.")
            resolved[key_str] = answer
        elif field.prompt_type == PromptType.SELECT:
            select_choices = list(field.choices or [])
            if default_val is not None and str(default_val) in select_choices:
                select_choices.remove(str(default_val))
                select_choices.insert(0, str(default_val))

            answer = questionary.select(
                field.label,
                choices=select_choices,
                style=questionary.Style(
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
            ).ask()
            if answer is None:
                raise ExecutionAbortedError("Metadata configuration cancelled by user.")
            resolved[key_str] = answer

    return resolved


def resolve_missing_variables(variables: list[str]) -> dict[str, str]:
    """Prompts the user for values to fill template placeholders.

    Args:
        variables: A list of variable keys missing from the template context.

    Returns:
        A dictionary mapping the variables to the user's string inputs.

    Raises:
        ConfigurationError: If the environment is non-interactive.
        ExecutionAbortedError: If the user cancels variable input.
    """
    if not _should_run_wizard():
        raise ConfigurationError(
            "Non-interactive environment detected, but the configuration requires "
            f"the following variables: {', '.join(variables)}\n"
            'Please provide them via CLI flags (e.g. --variable_name="value").'
        )

    import questionary

    console = Console()
    console.print("\n[bold cyan]Configuration Variables Required[/bold cyan]")
    console.print("The requested environment specification contains placeholders.\n")

    context = {}
    for var in variables:
        answer = questionary.text(f"{var}:").ask()
        if answer is None:
            raise ExecutionAbortedError("Variable resolution cancelled by user.")
        context[var] = answer

    return context
