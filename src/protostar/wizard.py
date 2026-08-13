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

    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]--- Project Metadata ---[/bold cyan]")

    desc = questionary.text(
        "Project description (optional, press Enter to skip):"
    ).ask()
    if desc is None:
        return None

    def get_git_config(key: str) -> str | None:
        try:
            import subprocess

            result = subprocess.run(
                ["git", "config", "--global", key],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or None
        except Exception:
            return None

    default_author = config.author_name or get_git_config("user.name") or "your-name"
    author_name = questionary.text("Author name:", default=default_author).ask()
    if author_name is None:
        return None

    default_email = config.author_email or get_git_config("user.email") or "your-email"
    author_email = questionary.text("Author email:", default=default_email).ask()
    if author_email is None:
        return None

    default_github = config.github_username or ""
    github_username = questionary.text(
        "GitHub username (optional):", default=default_github
    ).ask()
    if github_username is None:
        return None

    if answer == "cli":
        min_python = questionary.text(
            "Minimum Python version supported:", default=config.python_version or "3.13"
        ).ask()
        if min_python is None:
            return None

        supported_os = questionary.checkbox(
            "Operating systems supported:",
            choices=[
                Choice(title="MacOS", value="MacOS", checked=True),
                Choice(title="Linux", value="Linux", checked=True),
                Choice(title="Windows", value="Windows", checked=True),
            ],
        ).ask()
        if supported_os is None:
            return None
    else:
        min_python = config.python_version or "3.13"
        supported_os = []

    modules = [item for item in selected if item in TOOLING_MODULES]
    presets = [item for item in selected if item in PRESETS]
    docker = "docker" in selected

    return {
        "modules": modules,
        "presets": presets,
        "docker": docker,
        "project_metadata": {
            "description": desc or "Add your description here.",
            "author_name": author_name,
            "author_email": author_email,
            "github_username": github_username,
            "minimum_python": min_python,
            "supported_os": supported_os,
        },
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
