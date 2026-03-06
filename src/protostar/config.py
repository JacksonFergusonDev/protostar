import logging
import os
import subprocess
import tomllib
from dataclasses import dataclass, field, replace
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

        Args:
            path: The filesystem path to the local or global configuration file.
            instance: The active ProtostarConfig object to mutate.

        Returns:
            A new ProtostarConfig instance containing the merged state.
        """
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            updates: dict[str, Any] = {}

            if "env" in data:
                env_data = data["env"]
                if "ide" in env_data:
                    updates["ide"] = env_data["ide"]
                if "direnv" in env_data:
                    updates["direnv"] = env_data["direnv"]
                if "python_package_manager" in env_data:
                    updates["python_package_manager"] = env_data[
                        "python_package_manager"
                    ]
                if "python_version" in env_data:
                    updates["python_version"] = env_data["python_version"]
                if "node_package_manager" in env_data:
                    updates["node_package_manager"] = env_data["node_package_manager"]

                # Process dev tool flags, accommodating the inverted no-ruff flag
                if "markdownlint" in env_data:
                    updates["markdownlint"] = env_data["markdownlint"]
                if "ruff" in env_data:
                    updates["ruff"] = env_data["ruff"]
                if "no-ruff" in env_data:
                    updates["ruff"] = not env_data["no-ruff"]
                if "mypy" in env_data:
                    updates["mypy"] = env_data["mypy"]
                if "pytest" in env_data:
                    updates["pytest"] = env_data["pytest"]
                if "pre_commit" in env_data:
                    updates["pre_commit"] = env_data["pre_commit"]

            if "presets" in data:
                merged_presets = dict(instance.presets)
                merged_presets.update(data["presets"])
                updates["presets"] = merged_presets

            return replace(instance, **updates)

        except tomllib.TOMLDecodeError as e:
            console.print(
                f"[bold red]Config Error:[/bold red] Syntax error in {path}: {e}"
            )
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
