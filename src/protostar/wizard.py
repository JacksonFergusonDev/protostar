"""Interactive Terminal User Interface (TUI) wizards for Protostar."""

import os
import sys
from typing import Any

from rich.console import Console

from .config import ProtostarConfig
from .errors import ConfigurationError
from .modules import TOOLING_MODULES
from .presets import PRESETS


def _should_run_wizard() -> bool:
    """Evaluates if the environment supports interactive TTY prompts."""
    if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_init_wizard() -> dict[str, Any] | None:
    """Runs the environment initialization checklist.

    Dynamically constructs a spacebar-toggleable checklist from the module
    registries. Tooling options are dynamically pre-selected based on the
    user's global Protostar configuration.

    Returns:
        A dictionary containing the selected 'modules' (list), 'presets' (list),
        and 'docker' (bool) flag. Returns None if cancelled or non-interactive.
    """
    if not _should_run_wizard():
        return None

    import importlib.resources

    import questionary
    from questionary import Choice, Separator

    templates = ["None"]
    try:
        template_dir = importlib.resources.files("protostar.templates")
        for item in template_dir.iterdir():
            if item.is_file() and item.name.endswith(".toml"):
                templates.append(item.name[:-5])
    except Exception:
        pass

    answer = "None"
    if len(templates) > 1:
        if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
            answer = "None"
        else:
            answer = questionary.select(
                "Start from a built-in template?",
                choices=templates,
            ).ask()

        if answer is None:
            return None

        if answer != "None":
            target = importlib.resources.files("protostar.templates").joinpath(
                f"{answer}.toml"
            )
            config = ProtostarConfig.load(
                override_target=str(target), force_reload=True
            )
        else:
            config = ProtostarConfig.load()
    else:
        config = ProtostarConfig.load()

    choices: list[Choice | Separator] = []

    # 1. Presets
    choices.append(Separator("--- Presets ---"))
    for preset in PRESETS:
        is_checked = preset.config_key in config.active_presets
        choices.append(Choice(title=preset.name, value=preset, checked=is_checked))

    # 2. Context & Tooling
    choices.append(Separator("--- Context & Tooling ---"))
    choices.append(Choice(title="Docker (.dockerignore)", value="docker"))

    for tool_mod in TOOLING_MODULES:
        is_checked = getattr(config, tool_mod.config_key, False)
        choices.append(Choice(title=tool_mod.name, value=tool_mod, checked=is_checked))

    if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
        sys.exit(0)

    selected = questionary.checkbox(
        "Select the components for your new environment:",
        choices=choices,
    ).ask()

    if selected is None:
        return None

    modules = [item for item in selected if item in TOOLING_MODULES]
    presets = [item for item in selected if item in PRESETS]
    docker = "docker" in selected

    from .metadata import resolve_metadata

    required_keys = set()
    optional_keys = set()
    for mod in modules:
        required_keys.update(mod.required_metadata)
        optional_keys.update(mod.optional_metadata)
    for preset in presets:
        required_keys.update(preset.required_metadata)
        optional_keys.update(preset.optional_metadata)

    # Core project metadata always requested as optional
    optional_keys.update(
        (
            "description",
            "author_name",
            "author_email",
            "github_username",
            "minimum_python",
        )
    )

    console = Console()
    console.print("\n[bold cyan]--- Project Metadata ---[/bold cyan]")
    console.print(
        "\n[dim]Hint: You can skip these prompts in the future by adding your details to the global config (run `protostar config`).[/dim]"
    )

    try:
        resolved_metadata = resolve_metadata(
            required_keys, optional_keys, tui_mode=True
        )
    except KeyboardInterrupt:
        return None

    return {
        "modules": modules,
        "presets": presets,
        "docker": docker,
        "project_metadata": resolved_metadata,
    }


def resolve_missing_variables(variables: list[str]) -> dict[str, str]:
    """Prompts the user for values to fill template placeholders.

    Args:
        variables: A list of variable keys missing from the template context.

    Returns:
        A dictionary mapping the variables to the user's string inputs.

    Raises:
        ConfigurationError: If the environment is non-interactive.
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
            console.print(
                "\n[bold red]ABORTED:[/bold red] Variable resolution cancelled."
            )
            sys.exit(130)
        context[var] = answer

    return context
