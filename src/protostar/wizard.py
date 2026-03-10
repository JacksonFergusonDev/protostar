"""Interactive Terminal User Interface (TUI) wizards for Protostar."""

import os
import sys
from typing import Any

from .config import ProtostarConfig
from .generators import GENERATOR_REGISTRY
from .modules import (
    LANG_MODULES,
    TOOLING_MODULES,
)
from .presets import PRESETS


def _should_run_wizard() -> bool:
    """Evaluates if the environment supports interactive TTY prompts."""
    if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_discovery_wizard() -> str | None:
    """Runs the primary discovery multiplexer wizard.

    Returns:
        The selected action string ('init', 'generate', 'config'), or None if
        the user cancels the prompt or the environment is non-interactive.
    """
    if not _should_run_wizard():
        return None

    import questionary

    action = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice("Initialize a new environment", value="init"),
            questionary.Choice("Generate boilerplate code", value="generate"),
            questionary.Choice("Manage global configuration", value="config"),
        ],
    ).ask()

    # Cast to str | None to satisfy strict typing, as .ask() returns Any
    return str(action) if action else None


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

    import questionary
    from questionary import Choice, Separator

    config = ProtostarConfig.load()
    choices: list[Choice | Separator] = []

    # 1. Languages
    choices.append(Separator("--- Languages (Select at least one) ---"))
    for lang_mod in LANG_MODULES:
        choices.append(Choice(title=lang_mod.name, value=lang_mod))

    # 2. Presets
    choices.append(Separator("--- Presets ---"))
    for preset in PRESETS:
        choices.append(Choice(title=preset.name, value=preset))

    # 3. Context & Tooling
    choices.append(Separator("--- Context & Tooling ---"))
    choices.append(Choice(title="Docker (.dockerignore)", value="docker"))

    for tool_mod in TOOLING_MODULES:
        # Dynamically evaluate the global configuration default
        is_checked = getattr(config, tool_mod.config_key, False)
        choices.append(Choice(title=tool_mod.name, value=tool_mod, checked=is_checked))

    def _validate_init(result: list[Any]) -> bool | str:
        """Ensures the user has selected at least one language footprint."""
        if not any(item in LANG_MODULES for item in result):
            return "Please select at least one language footprint."
        return True

    # For benchmarking: Intercept execution right before blocking the thread with the prompt
    if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
        sys.exit(0)

    selected = questionary.checkbox(
        "Select the components for your new environment:",
        choices=choices,
        validate=_validate_init,
    ).ask()

    if selected is None:
        return None

    modules = [
        item for item in selected if item in LANG_MODULES or item in TOOLING_MODULES
    ]
    presets = [item for item in selected if item in PRESETS]
    docker = "docker" in selected

    return {
        "modules": modules,
        "presets": presets,
        "docker": docker,
    }


def run_generate_wizard() -> dict[str, str | None] | None:
    """Runs the target generation selection wizard.

    Returns:
        A dictionary containing the 'target' (str) and 'name' (str | None).
        Returns None if cancelled or non-interactive.
    """
    if not _should_run_wizard():
        return None

    import questionary
    from questionary import Choice

    choices = []
    for key, generator in GENERATOR_REGISTRY.items():
        desc = generator.__doc__.strip().split("\n")[0] if generator.__doc__ else ""
        title = f"{key:<15} - {desc}"
        choices.append(Choice(title=title, value=key))

    target = questionary.select(
        "Select a boilerplate target to generate:",
        choices=choices,
    ).ask()

    if not target:
        return None

    name = questionary.text(
        "Enter the identifier or filename (optional, press Enter to skip):"
    ).ask()

    if name is None:  # User triggered a KeyboardInterrupt (Ctrl+C)
        return None

    # Treat empty strings from the prompt as None to align with argparse behavior
    return {"target": str(target), "name": str(name).strip() if name else None}
