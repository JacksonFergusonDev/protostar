import logging
import tomllib
import types
import typing
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

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
            instance = cls._parse_and_merge(LOCAL_CONFIG_FILE, instance, is_local=True)

        return instance

    # --- Dependency Note: Why Not Pydantic? ---
    # Pydantic v2 was considered for config validation. The decision was to
    # stay with manual isinstance checks for the following reasons:
    #
    #   1. Schema stability: ProtostarConfig is small and unlikely to grow
    #      significantly. Pydantic earns its keep with complex, nested, or
    #      frequently changing schemas — none of which apply here.
    #
    #   2. CLI import cost: Even at ~0.1s, Pydantic's import time is
    #      perceptible in a CLI context where there is no persistent process
    #      keeping it warm. Every subcommand pays this cost.
    #
    #   3. Binary dependency: pydantic-core is a compiled Rust extension
    #      (~2–4MB, platform-specific wheel). This complicates installs in
    #      minimal or unusual environments and feels disproportionate for
    #      validating a handful of config fields written by the tool's own user.
    #
    # If the config schema grows to include cross-field validation, deeply
    # nested preset models, or externally-sourced input, revisit this decision.
    @classmethod
    def _parse_and_merge(
        cls, path: Path, instance: "ProtostarConfig", is_local: bool = False
    ) -> "ProtostarConfig":
        """Helper to parse a TOML file and merge its values into a config instance.

        Dynamically evaluates dataclass fields to prevent brittle parsing logic,
        while maintaining specific handlers for complex nested dictionaries.
        Type annotations are resolved at runtime via typing.get_type_hints so
        that Union types (e.g. str | None) are validated correctly before
        assignment.

        Args:
            path: The filesystem path to the local or global configuration file.
            instance: The active ProtostarConfig object to mutate.
            is_local: A flag indicating whether the configuration file is local.

        Returns:
            A new ProtostarConfig instance containing the merged state.

        Raises:
            ValueError: If the TOML file contains syntax errors.
        """
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(
                f"Syntax error in configuration file {path}.\n"
                f"Details: {e}\n"
                "Please fix the syntax error or delete the file to regenerate the defaults."
            ) from e
        except Exception as e:
            logger.warning(
                f"Failed to load config from {path}: {e}. Falling back to defaults."
            )
            return instance

        # --- Schema Validation & Scope Enforcement ---
        from protostar.generators import GENERATOR_REGISTRY

        generate_keys = set(GENERATOR_REGISTRY.keys())
        init_keys = {"env", "presets", "dev"}

        if is_local:
            blocked_found = init_keys.intersection(data.keys())
            if blocked_found:
                logger.warning(
                    f"Scope Warning: Found global init blocks ({', '.join(blocked_found)}) "
                    f"in local {path}. Local configs are strictly for 'generate'. These blocks will be ignored."
                )
                for k in blocked_found:
                    data.pop(k)

            allowed_keys = generate_keys
        else:
            allowed_keys = init_keys | generate_keys

        unknown_keys = set(data.keys()) - allowed_keys
        if unknown_keys:
            logger.warning(
                f"Config Warning: Unrecognized root keys in {path}: {', '.join(unknown_keys)}."
            )

        updates: dict[str, Any] = {}

        if "env" in data:
            env_data = data["env"]

            # get_type_hints resolves stringified annotations (PEP 563 /
            # `from __future__ import annotations`) into real type objects.
            # f.type would return raw strings in that context and break
            # isinstance checks.
            resolved_hints = typing.get_type_hints(cls)

            for key, value in env_data.items():
                if key not in resolved_hints:
                    continue

                expected = resolved_hints[key]
                origin = typing.get_origin(expected)

                if origin not in (None, types.UnionType, typing.Union):
                    updates[key] = value
                    continue

                if origin in (types.UnionType, typing.Union):
                    allowed = tuple(
                        t for t in typing.get_args(expected) if t is not type(None)
                    )
                else:
                    allowed = (expected,)

                if value is not None and allowed and not isinstance(value, allowed):
                    logger.warning(
                        f"Config Warning: Invalid type for '[env].{key}'. Expected {expected}, "
                        f"got {type(value).__name__}. Falling back to default."
                    )
                    continue

                updates[key] = value

            if "no-ruff" in env_data:
                if not isinstance(env_data["no-ruff"], bool):
                    logger.warning(
                        "Config Warning: '[env].no-ruff' must be a boolean. Falling back to default."
                    )
                else:
                    updates["ruff"] = not env_data["no-ruff"]

        if "presets" in data:
            merged_presets = dict(instance.presets)
            merged_presets.update(data["presets"])
            updates["presets"] = merged_presets

        if "dev" in data:
            dev_data = data["dev"]
            if "extra_dependencies" in dev_data:
                updates["global_dev_dependencies"] = dev_data["extra_dependencies"]

            if "pyproject" in dev_data:
                updates["pyproject_injections"] = dev_data["pyproject"]

        return replace(instance, **updates)
