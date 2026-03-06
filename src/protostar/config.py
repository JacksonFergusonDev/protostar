import logging
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

# Local workspace configuration resolution
LOCAL_CONFIG_FILE = Path(".protostar.toml")

DEFAULT_CONFIG_CONTENT = """[env]
# Preferred IDE: 'vscode', 'cursor', 'jetbrains', or 'none'
ide = "vscode"

# Auto-scaffold direnv with python environments
direnv = false

# Preferred Python package manager: 'uv' or 'pip'
python_package_manager = "uv"

# Optional default Python version (e.g., '3.12')
# python_version = "3.12"

# Preferred Node.js package manager: 'npm', 'pnpm', or 'yarn'
node_package_manager = "npm"

# Optional dev tool toggles for Python
# markdownlint = true
# no-ruff = true  # Disables the default Ruff scaffolding
# mypy = true
# pytest = true
# pre_commit = true

[presets]
# Generator presets for scaffolding boilerplate
latex = "minimal"

# --- Advanced Configuration Overrides ---
# Protostar allows you to customize the dependencies and directory structures
# for specific pipelines, or inject tooling across all initialized environments.

# [presets.astro]
# dependencies = ["astropy", "astroquery", "photutils", "specutils"]
# dev_dependencies = ["pytest-benchmark"]
# directories = ["data/catalogs", "data/fits", "data/raw"]

# [dev]
# extra_dependencies = ["bump-my-version"]

# [dev.pyproject]
# custom_ruff = '''
# [tool.ruff.lint]
# select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
# ignore = ["E501", "D100", "D104", "D107"]
# '''
"""


@dataclass
class ProtostarConfig:
    """Global configuration settings for the Protostar CLI.

    Attributes:
        ide (str): The preferred IDE (e.g., 'vscode', 'jetbrains', 'cursor', 'none').
        direnv (bool): Whether to auto-scaffold .envrc shell bindings.
        python_package_manager (str): The preferred Python manager ('uv', 'pip').
        python_version (str | None): The specific Python version to scaffold.
        node_package_manager (str): The preferred JS manager ('npm', 'pnpm', 'yarn').
        markdownlint (bool): Whether to auto-scaffold MarkdownLint configs.
        ruff (bool): Whether to auto-scaffold Ruff dependencies and configs.
        mypy (bool): Whether to auto-scaffold Mypy dependencies and configs.
        pytest (bool): Whether to auto-scaffold Pytest dependencies and configs.
        pre_commit (bool): Whether to auto-scaffold pre-commit hooks.
        presets (dict[str, Any]): Generation presets, mapped to either strings or nested configuration dictionaries.
        global_dev_dependencies (list[str]): Packages to inject into every initialized environment.
        pyproject_injections (dict[str, str]): Raw, multi-line TOML strings to append to pyproject.toml.
    """

    ide: str = "vscode"
    direnv: bool = False
    python_package_manager: str = "uv"
    python_version: str | None = None
    node_package_manager: str = "npm"
    markdownlint: bool = False
    ruff: bool = True
    mypy: bool = False
    pytest: bool = False
    pre_commit: bool = False
    presets: dict[str, Any] = field(default_factory=dict)
    global_dev_dependencies: list[str] = field(default_factory=list)
    pyproject_injections: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "ProtostarConfig":
        """Loads and parses global and local Protostar configuration files.

        Evaluates the global XDG configuration first, then merges any overrides
        from a local '.protostar.toml' file in the current working directory.
        """
        instance = cls()

        if CONFIG_FILE.exists():
            instance = cls._parse_and_merge(CONFIG_FILE, instance)

        if LOCAL_CONFIG_FILE.exists():
            logger.debug(
                f"Discovered local configuration override at {LOCAL_CONFIG_FILE}"
            )
            instance = cls._parse_and_merge(LOCAL_CONFIG_FILE, instance)

        return instance

    @classmethod
    def _parse_and_merge(
        cls, path: Path, instance: "ProtostarConfig"
    ) -> "ProtostarConfig":
        """Helper to parse a TOML file and merge its values into a config instance.

        Dynamically evaluates dataclass fields to prevent brittle parsing logic,
        while maintaining specific handlers for complex nested dictionaries.

        Args:
            path: The filesystem path to the local or global configuration file.
            instance: The active ProtostarConfig object to mutate.

        Returns:
            A new ProtostarConfig instance containing the merged state.

        Raises:
            SystemExit: If the TOML file contains syntax errors.
        """
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            updates: dict[str, Any] = {}

            # 1. Parse standard environment toggles dynamically
            if "env" in data:
                env_data = data["env"]

                # Dynamically map matching TOML keys directly to the dataclass fields
                valid_fields = {f.name for f in fields(cls)}
                for key, value in env_data.items():
                    if key in valid_fields:
                        updates[key] = value

                # Handle the specific inverted 'no-ruff' edge case
                if "no-ruff" in env_data:
                    updates["ruff"] = not env_data["no-ruff"]

            # 2. Parse and merge preset overrides
            if "presets" in data:
                merged_presets = dict(instance.presets)
                # Shallow update maps user-defined dictionaries over the default strings
                merged_presets.update(data["presets"])
                updates["presets"] = merged_presets

            # 3. Parse global development dependencies
            if "dev" in data:
                dev_data = data["dev"]
                if "extra_dependencies" in dev_data:
                    updates["global_dev_dependencies"] = dev_data["extra_dependencies"]

                # 4. Parse raw pyproject.toml injections
                if "pyproject" in dev_data:
                    updates["pyproject_injections"] = dev_data["pyproject"]

            return replace(instance, **updates)

        except tomllib.TOMLDecodeError as e:
            console.print(
                f"\n[bold red]Fatal Configuration Error:[/bold red] Syntax error in {path}"
            )
            console.print(f"Details: {e}")
            console.print(
                "Please fix the syntax error or delete the file to regenerate the defaults."
            )
            sys.exit(1)
        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to load config from {path}: {e}. "
                "Falling back to defaults."
            )

        return instance

    @staticmethod
    def open_in_editor() -> None:
        """Opens the global configuration file in the system's default editor.

        Ensures the parent directory exists and seeds a default configuration
        template if the file is missing.
        """
        if not CONFIG_FILE.parent.exists():
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(DEFAULT_CONFIG_CONTENT)
            logger.info(f"Initialized default configuration at {CONFIG_FILE}")

        # Fallback to nano if $EDITOR isn't exported in the user's shell profile
        editor = os.environ.get("EDITOR", "nano")

        try:
            subprocess.run([editor, str(CONFIG_FILE)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Editor '{editor}' exited with non-zero status: {e}")
        except FileNotFoundError:
            logger.error(
                f"Could not resolve editor '{editor}'. "
                "Ensure your $EDITOR environment variable is set to a valid executable."
            )
