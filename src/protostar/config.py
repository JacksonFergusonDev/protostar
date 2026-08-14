"""Configuration management and schema definitions for Protostar."""

import logging
import tomllib
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar

from .errors import ConfigurationError
from .interpolation import extract_variables, render_template
from .network import fetch_remote_config

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

DEFAULT_CONFIG_CONTENT = """[env]
# Preferred IDE: 'vscode', 'cursor', or 'none'
# ide = "vscode"

# Default Author Information
# author_name = "your-name"
# author_email = "your-email"
# github_username = "your-github-username"

# Auto-scaffold direnv with python environments
direnv = false

# Default Python version
python_version = "3.13"
# supported_os = ["MacOS", "Linux", "Windows"]

# Optional dev tool toggles for Python
# markdownlint = true
# ruff = false  # Disables the default Ruff scaffolding
# mypy = true
# ty = true          # Scaffold Astral ty type checker
# pyrefly = true     # Scaffold Pyrefly type checker
# pytest = true
# pre_commit = true
# prek = true        # Scaffold prek git hooks (faster Rust alternative to pre-commit)
# commitizen = true  # Scaffold commitizen version bumping and changelog tooling
# renovate = true    # Scaffold Renovate dependency update configuration
# codecov = true     # Scaffold Codecov configuration
# zensical = true    # Scaffold Zensical documentation
# readthedocs = true # Scaffold Read the Docs configuration
# ci = true          # Scaffold standard GitHub Actions CI workflows
# release = true     # Scaffold GitHub Actions PyPI release workflows
# just = true        # Scaffold a justfile for command execution
# active_presets = []

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
class UserConfig:
    """Global configuration settings for the Protostar CLI.

    Attributes:
        ide (str | None): The preferred IDE (e.g., 'vscode', 'cursor', 'none').
        direnv (bool): Whether to auto-scaffold .envrc shell bindings.
        python_version (str | None): The specific Python version to scaffold.
        supported_os (list[str]): The supported operating systems to scaffold CI for.
        markdownlint (bool): Whether to auto-scaffold MarkdownLint configs.
        ruff (bool): Whether to auto-scaffold Ruff dependencies and configs.
        mypy (bool): Whether to auto-scaffold Mypy dependencies and configs.
        ty (bool): Whether to auto-scaffold Astral ty type checker.
        pyrefly (bool): Whether to auto-scaffold Pyrefly type checker.
        pytest (bool): Whether to auto-scaffold Pytest dependencies and configs.
        pre_commit (bool): Whether to auto-scaffold pre-commit hooks.
        prek (bool): Whether to auto-scaffold prek git hooks.
        commitizen (bool): Whether to auto-scaffold commitizen version bumping and changelog tooling.
        renovate (bool): Whether to auto-scaffold Renovate dependency update configuration.
        codecov (bool): Whether to auto-scaffold Codecov configuration.
        zensical (bool): Whether to auto-scaffold Zensical documentation.
        readthedocs (bool): Whether to auto-scaffold Read the Docs configuration.
        ci (bool): Whether to auto-scaffold standard GitHub Actions CI workflows.
        release (bool): Whether to auto-scaffold GitHub Actions PyPI release workflows.
        just (bool): Whether to auto-scaffold a justfile for command execution.
        presets (dict[str, Any]): Initialization presets, mapped to strings or nested dicts.
        global_dev_dependencies (list[str]): Packages to inject into every initialized environment.
        pyproject_injections (dict[str, str]): Raw, multi-line TOML strings to append to pyproject.toml.
        files (dict[str, str]): Exact file paths mapped to their raw contents for injection.
        variables (dict[str, Any]): Arbitrary key-value pairs for dynamic configuration.
    """

    ide: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    github_username: str | None = None
    direnv: bool = False
    python_version: str | None = "3.13"
    supported_os: list[str] = field(default_factory=list)
    markdownlint: bool = False
    ruff: bool = True
    mypy: bool = False
    ty: bool = False
    pyrefly: bool = False
    pytest: bool = False
    pre_commit: bool = False
    prek: bool = False
    commitizen: bool = False
    renovate: bool = False
    codecov: bool = False
    zensical: bool = False
    readthedocs: bool = False
    ci: bool = False
    release: bool = False
    just: bool = False

    # In-memory cache to prevent repeated disk I/O
    _instance: ClassVar["UserConfig | None"] = None

    @classmethod
    def load(cls, force_reload: bool = False) -> "UserConfig":
        """Loads and parses the global Protostar configuration file.

        Args:
            force_reload: If True, bypasses the cache and forces a disk read.

        Returns:
            The loaded UserConfig instance.
        """
        if cls._instance is not None and not force_reload:
            return cls._instance

        instance = cls()

        if CONFIG_FILE.exists():
            instance = cls._parse_and_merge(
                CONFIG_FILE.read_text(encoding="utf-8"), str(CONFIG_FILE), instance
            )

        cls._instance = instance
        return instance

    @classmethod
    def _parse_and_merge(
        cls, content: str, source: str, instance: "UserConfig"
    ) -> "UserConfig":
        """Helper to parse a TOML string and merge its values into a config instance.

        Args:
            content: The raw TOML string to parse.
            source: The origin of the content (for error reporting).
            instance: The active UserConfig object to mutate.

        Returns:
            A new UserConfig instance containing the merged state.

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
            raise ConfigurationError(
                f"Unexpected error while parsing configuration source '{source}'.\n"
                f"Details: {e}"
            ) from e

        allowed_keys = {"env"}
        unknown_keys = set(data.keys()) - allowed_keys
        if unknown_keys:
            raise ConfigurationError(
                f"Unrecognized root keys in {source}: {', '.join(unknown_keys)}.\n"
                f"Allowed keys are: {', '.join(allowed_keys)}."
            )

        updates: dict[str, Any] = {}

        if "env" in data:
            env_data = data["env"]

            if "active_presets" in env_data and source == str(CONFIG_FILE):
                raise ConfigurationError(
                    "The 'active_presets' key is not allowed in the global configuration file "
                    f"({CONFIG_FILE}), as it would permanently inject those dependencies into every "
                    "future project.\n\n"
                    "Please use 'active_presets' exclusively within portable templates or --from targets."
                )

            resolved_hints = typing.get_type_hints(cls)

            for key, value in env_data.items():
                if key not in resolved_hints:
                    continue

                expected = resolved_hints[key]
                origin = typing.get_origin(expected)

                if origin is list:
                    if not isinstance(value, list):
                        raise ConfigurationError(
                            f"Type mismatch in {source} for '[env].{key}'.\n"
                            f"Expected list, but got {type(value).__name__}."
                        )
                    inner_type = typing.get_args(expected)[0]
                    for item in value:
                        if not isinstance(item, inner_type):
                            raise ConfigurationError(
                                f"Type mismatch in {source} for '[env].{key}' elements.\n"
                                f"Expected {inner_type.__name__}, but got {type(item).__name__}."
                            )
                    updates[key] = value
                    continue

                if origin not in (None, types.UnionType, typing.Union, list):
                    updates[key] = value
                    continue

                if origin in (types.UnionType, typing.Union):
                    allowed = tuple(
                        t for t in typing.get_args(expected) if t is not type(None)
                    )
                else:
                    allowed = (expected,)

                if value is not None and allowed and not isinstance(value, allowed):
                    raise ConfigurationError(
                        f"Type mismatch in {source} for '[env].{key}'.\n"
                        f"Expected {expected}, but got {type(value).__name__}."
                    )

                updates[key] = value

        return replace(instance, **updates)


@dataclass
class TemplateBlueprint:
    """Represents the parsed template state for target environments."""

    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    docs_dependencies: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    vcs_ignores: list[str] = field(default_factory=list)
    system_tasks: list[list[str]] = field(default_factory=list)
    post_install_tasks: list[list[str]] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    pyproject_injections: dict[str, str] = field(default_factory=dict)
    active_presets: list[str] = field(default_factory=list)
    tooling_overrides: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        target: str,
        template_context: dict[str, str] | None = None,
        variable_resolver: Callable[[list[str]], dict[str, str]] | None = None,
    ) -> "TemplateBlueprint":
        """Loads and parses a template blueprint."""
        if target.startswith("http://") or target.startswith("https://"):
            content = fetch_remote_config(target)
        else:
            target_path = Path(target)
            if not target_path.exists():
                raise ConfigurationError(f"Configuration file not found: {target_path}")
            content = target_path.read_text(encoding="utf-8")

        variables = extract_variables(content)
        context = dict(template_context) if template_context else {}

        late_binding_vars = {"PYTHON_VERSION", "PROJECT_NAME", "PACKAGE_NAME"}
        missing = [
            v for v in variables if v not in context and v not in late_binding_vars
        ]

        if missing:
            if variable_resolver is not None:
                context.update(variable_resolver(missing))
            else:
                raise ConfigurationError(
                    f"Configuration template requires variables: {', '.join(missing)}. "
                    "Please provide them via CLI flags (e.g. --variable_name=value) "
                    "or run in an interactive terminal."
                )

        content = render_template(content, context)
        return cls._parse(content, target)

    @classmethod
    def _parse(cls, content: str, source: str = "unknown") -> "TemplateBlueprint":
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                f"Syntax error in configuration source '{source}'.\n"
                f"Details: {e}\n"
                "Please fix the syntax error to proceed."
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Unexpected error while parsing configuration source '{source}'.\n"
                f"Details: {e}"
            ) from e

        instance = cls()

        if "env" in data:
            env_data = data["env"]
            if "active_presets" in env_data:
                instance.active_presets = env_data["active_presets"]

        if "dev" in data:
            dev_data = data["dev"]
            if "extra_dependencies" in dev_data:
                instance.dev_dependencies = dev_data["extra_dependencies"]
            elif "dev_dependencies" in dev_data:
                instance.dev_dependencies = dev_data["dev_dependencies"]

            if "pyproject" in dev_data:
                instance.pyproject_injections = dev_data["pyproject"]

        if "files" in data:
            instance.files = data["files"]

        return instance
