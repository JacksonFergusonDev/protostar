"""Interactive Terminal User Interface (TUI) wizards for Protostar."""

import importlib.resources
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from protostar.cli.prompts import Choice, Separator, Style, checkbox, select, text
from protostar.config import TemplateBlueprint, TemplateSource, UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.metadata import METADATA_FIELDS, MetadataKey, PromptType
from protostar.modules import (
    TOOLING_MODULES,
    BootstrapModule,
)
from protostar.recipe import (
    EXCLUSIVE_TOOL_PAIRS,
    SelectionLayer,
    Tool,
    establish_recipe,
    read_recipe,
)
from protostar.system import is_interactive


@dataclass
class WizardSelections:
    """Selections captured from the interactive initialization wizard.

    Attributes:
        modules: Selected tooling modules.
        docker: If True, scaffolds container artifacts (.dockerignore).
        project_metadata: Resolved project metadata key-value mappings.
        blueprint: The loaded template blueprint, if any.
        is_external: If True, the template was loaded from an external source.
        is_user_aliased: If True, the template was resolved via a global alias.
        is_trusted: If True, the template is explicitly trusted to run system tasks.
        variables: Values entered for the template's custom variables.
    """

    modules: list[BootstrapModule] = field(default_factory=list)
    docker: bool = False
    project_metadata: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    blueprint: TemplateBlueprint | None = None
    source: TemplateSource | None = None
    is_external: bool = False
    is_user_aliased: bool = False
    is_trusted: bool = False


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

    from protostar.templates import TemplateType, discover_templates

    config = UserConfig.load()
    discovered = discover_templates(config=config)
    builtins = [t for t in discovered if t.type == TemplateType.BUILT_IN]
    aliases = [t for t in discovered if t.type == TemplateType.GLOBAL_ALIAS]
    templates_by_alias = {t.alias: t for t in discovered}

    template_choices: list[Any] = ["None"]
    max_name_len = max((len(t.name) for t in discovered), default=10)
    col_width = max(max_name_len, 10)

    if builtins:
        template_choices.append(
            Separator(
                "── Built-in Templates ─────────────────────────────────────────────"
            )
        )
        for t in builtins:
            title = (
                f"{t.name:<{col_width}}  ·  {t.description}"
                if t.description
                else t.name
            )
            template_choices.append(Choice(title=title, value=t.alias))

    if aliases:
        template_choices.append(
            Separator(
                "── External Aliases ───────────────────────────────────────────────"
            )
        )
        for t in aliases:
            title = (
                f"{t.name:<{col_width}}  ·  {t.description}"
                if t.description
                else t.name
            )
            template_choices.append(Choice(title=title, value=t.alias))

    answer: str | None = "None"
    if len(template_choices) > 1:
        if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
            answer = "None"
        else:
            answer = select(
                "Start from a template?",
                choices=template_choices,
            )

        if answer is None:
            raise ExecutionAbortedError("Template selection cancelled by user.")

    blueprint = None
    source = None
    variables: dict[str, str] = {}
    is_external = False
    is_user_aliased = False
    is_trusted = False

    if answer != "None":
        if answer in templates_by_alias:
            tmpl_info = templates_by_alias[answer]
            if tmpl_info.type == TemplateType.BUILT_IN:
                target = str(
                    importlib.resources.files("protostar.templates").joinpath(
                        f"{answer}.toml"
                    )
                )
                is_trusted = True
            else:
                target = tmpl_info.source
                is_external = True
                is_user_aliased = True
                is_trusted = tmpl_info.trusted
        else:
            raise ExecutionAbortedError(
                f"Template selection '{answer}' could not be resolved."
            )

        source = TemplateSource.load(
            target,
            built_in=answer if not is_external else None,
            display_name=answer,
        )
        if source.variables:
            variables = prompt_template_variables(sorted(source.variables))
        blueprint = source.render(variables)

    choices: list[Choice | Separator] = []
    existing_recipe = read_recipe(Path("pyproject.toml"))
    opinions = blueprint.tooling_overrides if blueprint else {}
    selection_recipe = existing_recipe or establish_recipe(config)
    selected_by_tool = {
        selection.tool: selection for selection in selection_recipe.selections(opinions)
    }

    # Context & Tooling
    choices.append(Separator("--- Context & Tooling ---"))
    docker_from_template = bool(blueprint and blueprint.tooling_overrides.get("docker"))
    docker_checked = existing_recipe.docker if existing_recipe else docker_from_template
    choices.append(
        Choice(
            title="Docker (Dockerfile & .dockerignore)"
            + (" (Enforced by template)" if docker_from_template else ""),
            value="docker",
            checked=docker_checked,
        )
    )

    for tool_mod in TOOLING_MODULES:
        selection = selected_by_tool[Tool(tool_mod.config_key)]
        is_checked = selection.enabled
        label_suffix = ""

        if blueprint and tool_mod.config_key in blueprint.tooling_overrides:
            blueprint_val = blueprint.tooling_overrides[tool_mod.config_key]
            if selection.layer is SelectionLayer.TEMPLATE and blueprint_val != getattr(
                config, tool_mod.config_key, False
            ):
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

    selected = checkbox(
        "Select the components for your new environment:",
        choices=choices,
    )

    if selected is None:
        raise ExecutionAbortedError("Component selection cancelled by user.")

    modules = [item for item in selected if item in TOOLING_MODULES]
    docker = "docker" in selected

    selected_tools = {Tool(m.config_key) for m in modules}
    for pair in EXCLUSIVE_TOOL_PAIRS:
        if not pair <= selected_tools:
            continue
        prek_mod = next(m for m in modules if m.config_key == Tool.PREK)
        pre_commit_mod = next(m for m in modules if m.config_key == Tool.PRE_COMMIT)
        chosen = select(
            "Both Pre-Commit and Prek were selected. Which Git hook manager would you like to use?",
            choices=[
                Choice(
                    "Prek (Recommended: Fast Rust-based git hook manager)",
                    value=prek_mod,
                ),
                Choice(
                    "Pre-Commit (Traditional Python-based git hook manager)",
                    value=pre_commit_mod,
                ),
            ],
        )
        if chosen is None:
            raise ExecutionAbortedError("Hook runner selection cancelled by user.")
        discard = pre_commit_mod if chosen is prek_mod else prek_mod
        modules.remove(discard)

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
        source=source,
        variables=variables,
        is_external=is_external,
        is_user_aliased=is_user_aliased,
        is_trusted=is_trusted,
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
