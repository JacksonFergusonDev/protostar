import logging
import tomllib
import types
import typing
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar

from .errors import ConfigurationError
from .templating import extract_variables, render_template

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

DEFAULT_CONFIG_CONTENT = """[env]
# Preferred IDE: 'vscode', 'cursor', or 'none'
# ide = "vscode"

# Auto-scaffold direnv with python environments
direnv = false

# Default Python version
python_version = "3.13"

# Optional dev tool toggles for Python
# markdownlint = true
# ruff = false  # Disables the default Ruff scaffolding
# mypy = true
# pytest = true
# pre_commit = true

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
        ide (str | None): The preferred IDE (e.g., 'vscode', 'cursor', 'none').
        direnv (bool): Whether to auto-scaffold .envrc shell bindings.
        python_version (str | None): The specific Python version to scaffold.
        markdownlint (bool): Whether to auto-scaffold MarkdownLint configs.
        ruff (bool): Whether to auto-scaffold Ruff dependencies and configs.
        mypy (bool): Whether to auto-scaffold Mypy dependencies and configs.
        pytest (bool): Whether to auto-scaffold Pytest dependencies and configs.
        pre_commit (bool): Whether to auto-scaffold pre-commit hooks.
        presets (dict[str, Any]): Initialization presets, mapped to strings or nested dicts.
        global_dev_dependencies (list[str]): Packages to inject into every initialized environment.
        pyproject_injections (dict[str, str]): Raw, multi-line TOML strings to append to pyproject.toml.
        files (dict[str, str]): Exact file paths mapped to their raw contents for injection.
        variables (dict[str, Any]): Arbitrary key-value pairs for dynamic configuration.
    """

    ide: str | None = None
    direnv: bool = False
    python_version: str | None = "3.13"
    markdownlint: bool = False
    ruff: bool = True
    mypy: bool = False
    pytest: bool = False
    pre_commit: bool = False
    presets: dict[str, Any] = field(default_factory=dict)
    global_dev_dependencies: list[str] = field(default_factory=list)
    pyproject_injections: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    _parsing_warnings: list[str] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    # In-memory cache to prevent repeated disk I/O
    _instance: ClassVar["ProtostarConfig | None"] = None

    @classmethod
    def load(
        cls,
        force_reload: bool = False,
        override_target: str | None = None,
        template_context: dict[str, str] | None = None,
    ) -> "ProtostarConfig":
        """Loads and parses the global Protostar configuration file.

        Evaluates the global XDG configuration and implements a class-level cache
        to prevent repeated disk I/O across the lifecycle.

        Args:
            force_reload: If True, bypasses the cache and forces a disk read.
            override_target: An optional path or URL to a portable configuration to overlay.
            template_context: Variables passed via CLI to inject into the template.

        Returns:
            The loaded ProtostarConfig instance.
        """
        if cls._instance is not None and not force_reload and override_target is None:
            return cls._instance

        instance = cls()

        if CONFIG_FILE.exists():
            instance = cls._parse_and_merge(
                CONFIG_FILE.read_text(encoding="utf-8"), str(CONFIG_FILE), instance
            )

        if override_target is not None:
            if override_target.startswith("http://") or override_target.startswith(
                "https://"
            ):
                from .network import fetch_remote_config

                content = fetch_remote_config(override_target)
            else:
                target_path = Path(override_target)
                if not target_path.exists():
                    raise ConfigurationError(
                        f"Configuration file not found: {target_path}"
                    )
                content = target_path.read_text(encoding="utf-8")

            variables = extract_variables(content)
            context = template_context or {}
            missing = [v for v in variables if v not in context]

            if missing:
                from .wizard import resolve_missing_variables

                context.update(resolve_missing_variables(missing))

            content = render_template(content, context)
            instance = cls._parse_and_merge(content, override_target, instance)

        cls._instance = instance
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
    #      (~2-4MB, platform-specific wheel). This complicates installs in
    #      minimal or unusual environments and feels disproportionate for
    #      validating a handful of config fields written by the tool's own user.
    #
    # If the config schema grows to include cross-field validation, deeply
    # nested preset models, or externally-sourced input, revisit this decision.
    @classmethod
    def _parse_and_merge(
        cls, content: str, source: str, instance: "ProtostarConfig"
    ) -> "ProtostarConfig":
        """Helper to parse a TOML string and merge its values into a config instance.

        Dynamically evaluates dataclass fields to prevent brittle parsing logic,
        while maintaining specific handlers for complex nested dictionaries.
        Type annotations are resolved at runtime via typing.get_type_hints so
        that Union types (e.g. str | None) are validated correctly before
        assignment.

        Args:
            content: The raw TOML string to parse.
            source: The origin of the content (for error reporting).
            instance: The active ProtostarConfig object to mutate.

        Returns:
            A new ProtostarConfig instance containing the merged state.

        Raises:
            ConfigurationError: If the TOML string contains syntax errors.
        """
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                f"Syntax error in configuration source '{source}'.\n"
                f"Details: {e}\n"
                "Please fix the syntax error to proceed."
            ) from e
        except Exception as e:
            instance._parsing_warnings.append(
                f"Failed to load config from {source}: {e}. Falling back to defaults."
            )
            return instance

        # --- Schema Validation & Scope Enforcement ---
        allowed_keys = {"env", "presets", "dev", "files", "variables"}
        warnings: list[str] = []

        unknown_keys = set(data.keys()) - allowed_keys
        if unknown_keys:
            warnings.append(
                f"Unrecognized root keys in {source}: {', '.join(unknown_keys)}."
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
                    warnings.append(
                        f"Invalid type for '[env].{key}'. Expected {expected}, "
                        f"got {type(value).__name__}. Falling back to default."
                    )
                    continue

                updates[key] = value

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

        if "files" in data:
            merged_files = dict(instance.files)
            merged_files.update(data["files"])
            updates["files"] = merged_files

        if "variables" in data:
            merged_vars = dict(instance.variables)
            merged_vars.update(data["variables"])
            updates["variables"] = merged_vars

        new_instance = replace(instance, **updates)
        new_instance._parsing_warnings = instance._parsing_warnings + warnings
        return new_instance
