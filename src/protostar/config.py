"""Configuration management and schema definitions for Protostar."""

import enum
import functools
import hashlib
import logging
import os
import tomllib
import types
import typing
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .errors import (
    ConfigurationError,
    MissingTemplateVariablesError,
    TemplateEncodingError,
    TemplateResolutionError,
)
from .ide import IDEType
from .intent import (
    AppendContribution,
    DependencyGroup,
    DependencyInclude,
    OptionalContent,
    PyprojectPayload,
    TemplateOrigin,
    TemplateReference,
    validate_configuration,
    validate_region_id,
    validate_target,
)
from .interpolation import BUILT_IN_VARIABLES, extract_variables, render_template
from .metadata import validate_github_username
from .migrations import Migration, parse_migrations
from .network import RemoteTemplate, fetch_remote_template
from .options import Condition, TemplateOption, parse_condition, parse_options
from .workspace import check_python_version

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
_xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
if _xdg_config_home:
    CONFIG_FILE = Path(_xdg_config_home) / "protostar" / "config.toml"
else:
    CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

CONFIG_ENV_VAR = "PROTOSTAR_CONFIG"


class ConfigOrigin(enum.StrEnum):
    """How the configuration file for this run was chosen."""

    DEFAULT = "default"
    EXPLICIT = "explicit"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ConfigSource:
    """The configuration file a run reads, and how it was selected.

    Attributes:
        origin: Whether the path is the default location, an explicit
            selection, or absent because configuration is disabled.
        path: The file to read, or None when configuration is disabled.
    """

    origin: ConfigOrigin
    path: Path | None

    @classmethod
    def disabled(cls) -> "ConfigSource":
        """Returns the source that reads no configuration at all."""
        return cls(ConfigOrigin.DISABLED, None)

    @classmethod
    def explicit(cls, path: Path) -> "ConfigSource":
        """Returns a deliberately selected configuration file."""
        return cls(ConfigOrigin.EXPLICIT, path)


_config_override: ConfigSource | None = None


def select_config_source(path: str | None, *, disabled: bool = False) -> None:
    """Overrides the configuration source for the remainder of the process.

    The CLI applies its ``--config`` / ``--no-config`` selection here after
    parsing, ahead of any command handler that reads configuration.

    Args:
        path: An explicit configuration file, or None to leave it unselected.
        disabled: True to read no configuration file at all.

    Raises:
        ConfigurationError: If both an explicit path and disabling are given.
    """
    global _config_override

    if disabled and path is not None:
        raise ConfigurationError(
            "Cannot combine an explicit configuration file with disabling configuration.",
            hint="Pass either '--config <path>' or '--no-config', not both.",
        )
    if disabled:
        _config_override = ConfigSource.disabled()
    elif path is not None:
        _config_override = ConfigSource.explicit(Path(path).expanduser())
    else:
        _config_override = None
    clear_user_config_cache()


def active_config_source() -> ConfigSource:
    """Resolves which configuration file this run reads.

    Precedence is the CLI selection, then the ``PROTOSTAR_CONFIG`` environment
    variable (empty disables configuration entirely), then the default path.

    Returns:
        The resolved configuration source.
    """
    if _config_override is not None:
        return _config_override

    raw = os.environ.get(CONFIG_ENV_VAR)
    if raw is None:
        return ConfigSource(ConfigOrigin.DEFAULT, CONFIG_FILE)
    if not raw.strip():
        return ConfigSource.disabled()
    return ConfigSource.explicit(Path(raw).expanduser())


DEFAULT_CONFIG_CONTENT = """[env]
# Preferred IDE: 'vscode', 'cursor', or 'none'
# ide = "vscode"

# Default Author Information
# author_name = "your-name"
# author_email = "your-email@example.com"
# github_username = "your-github-username"

# Default Python version
python_version = "3.13"
# supported_os = ["MacOS", "Linux", "Windows"]

# Optional dev tool toggles for Python
# direnv = true        # Scaffold .envrc and auto-activate virtual environments
# markdownlint = true  # Scaffold MarkdownLint configuration and hooks
# rumdl = true         # Scaffold rumdl fast markdown linter and formatter
# ruff = false         # Disable default Ruff linter and formatter scaffolding
# mypy = true          # Scaffold Mypy static type checker
# ty = true            # Scaffold Astral ty type checker
# pyrefly = true       # Scaffold Pyrefly static type checker
# pytest = true        # Scaffold Pytest testing framework
# pre_commit = true    # Scaffold pre-commit git hooks and configuration
# prek = true          # Scaffold prek git hooks (faster Rust alternative to pre-commit)
# commitizen = true    # Scaffold Commitizen version bumping and changelog tooling
# renovate = true      # Scaffold Renovate dependency update configuration
# codecov = true       # Scaffold Codecov configuration
# zensical = true      # Scaffold Zensical documentation
# readthedocs = true   # Scaffold Read the Docs configuration
# ci = true            # Scaffold standard GitHub Actions CI workflows
# release = true       # Scaffold GitHub Actions PyPI release workflows
# just = true          # Scaffold a justfile for command execution
# agents = true        # Scaffold a managed AGENTS.md guide for coding agents
# community = true     # Scaffold community health files and issue templates

# [templates]
# my-org-api = "https://raw.githubusercontent.com/MyOrg/standards/main/api.toml"
# data-science-base = "~/Developer/templates/ds_base.toml"
#
# [templates.enterprise-api]
# name = "Enterprise API"
# source = "https://github.com/myorg/enterprise-template"
# description = "Internal enterprise microservice scaffold with auth & tracing"
# trusted = true
"""


@dataclass(frozen=True)
class TemplateAliasConfig:
    """Configuration metadata for an external or custom template alias.

    Attributes:
        source: Remote URL or local filesystem path to the template.
        name: Human-readable display name for the template.
        description: Brief description of the template stack and purpose.
        trusted: If True, bypasses interactive execution prompts for remote templates.
    """

    source: str
    name: str | None = None
    description: str = ""
    trusted: bool = False


def _validate_template_aliases(templates: dict[str, TemplateAliasConfig]) -> None:
    """Rejects template aliases that cannot resolve to exactly one template.

    Template lookup is case-insensitive and built-in templates are discovered
    ahead of user aliases, so a shadowing alias resolves differently depending
    on the call site (``--template`` finds the built-in, the wizard finds the
    alias). Neither answer is correct, so the ambiguity is refused at load time.

    Args:
        templates: The normalized user alias table.

    Raises:
        ConfigurationError: If an alias shadows a built-in template, or if two
            aliases differ only by letter case.
    """
    from protostar.templates import builtin_template_aliases

    config_path = active_config_source().path or CONFIG_FILE
    reserved = {alias.casefold(): alias for alias in builtin_template_aliases()}
    seen: dict[str, str] = {}
    for alias in sorted(templates):
        folded = alias.casefold()
        if folded in reserved:
            raise ConfigurationError(
                f"Template alias '{alias}' in '[templates]' is reserved by the "
                f"built-in template '{reserved[folded]}'.",
                hint=(
                    f"Rename the alias in {config_path}. Built-in template names "
                    "cannot be reused, because '--template' and the interactive "
                    "wizard would resolve them to different templates."
                ),
            )
        if folded in seen:
            raise ConfigurationError(
                f"Template aliases '{seen[folded]}' and '{alias}' in '[templates]' "
                "differ only by letter case.",
                hint=(
                    f"Rename one of them in {config_path}. Template lookup is "
                    "case-insensitive, so only one of the two is reachable."
                ),
            )
        seen[folded] = alias


@dataclass
class UserConfig:
    """Global configuration settings for the Protostar CLI.

    Attributes:
        ide (IDEType | str | None): The preferred IDE (e.g., 'vscode', 'cursor', 'none').
        author_name (str | None): Default author name for project metadata.
        author_email (str | None): Default author email for project metadata.
        github_username (str | None): Default GitHub username for repository URL formatting.
        direnv (bool): Whether to auto-scaffold .envrc shell bindings.
        python_version (str | None): The specific Python version to scaffold.
        license (str | None): Default project license identifier (e.g., 'MIT', 'Apache-2.0').
        supported_os (list[str]): The supported operating systems to scaffold CI for.
        markdownlint (bool): Whether to auto-scaffold MarkdownLint configs.
        rumdl (bool): Whether to auto-scaffold rumdl fast markdown linter and formatter.
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
        agents (bool): Whether to auto-scaffold a managed AGENTS.md guide for coding agents.
        community (bool): Whether to auto-scaffold community health files and issue templates.
    """

    ide: IDEType | str | None = None
    author_name: str | None = None
    author_email: str | None = None
    github_username: str | None = None
    direnv: bool = False
    python_version: str | None = "3.13"
    license: str | None = None
    supported_os: list[str] = field(default_factory=list)
    markdownlint: bool = False
    rumdl: bool = False
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
    agents: bool = False
    community: bool = False
    templates: dict[str, TemplateAliasConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalizes template configuration dictionary and validates invariants."""
        if self.pre_commit and self.prek:
            raise ConfigurationError(
                "Cannot configure both 'pre_commit = true' and 'prek = true'.",
                hint="Choose either pre_commit or prek as your default git hook manager in your configuration.",
            )
        if self.python_version is not None:
            check_python_version(self.python_version)
        if self.github_username:
            validate_github_username(self.github_username)

        normalized: dict[str, TemplateAliasConfig] = {}
        for k, v in self.templates.items():
            if isinstance(v, str):
                normalized[k] = TemplateAliasConfig(source=v, name=k)
            else:
                normalized[k] = v
        _validate_template_aliases(normalized)
        self.templates = normalized

    @classmethod
    def load(cls, force_reload: bool = False) -> "UserConfig":
        """Loads and parses the global Protostar configuration file.

        Args:
            force_reload: If True, bypasses the cache and forces a disk read.

        Returns:
            The loaded UserConfig instance.
        """
        if force_reload:
            clear_user_config_cache()
        hits_before = _load_cached_user_config.cache_info().hits
        instance = _load_cached_user_config()
        if _load_cached_user_config.cache_info().hits > hits_before:
            logger.debug("Using cached UserConfig instance")
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

        allowed_keys = {"env", "templates"}
        unknown_keys = set(data.keys()) - allowed_keys
        if unknown_keys:
            raise ConfigurationError(
                f"Unrecognized root keys in {source}: {', '.join(unknown_keys)}.\n"
                f"Allowed keys are: {', '.join(allowed_keys)}."
            )

        updates: dict[str, Any] = {}

        if "env" in data:
            env_data = data["env"]
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

        if "templates" in data:
            templates_data = data["templates"]
            if not isinstance(templates_data, dict):
                raise ConfigurationError(
                    f"Type mismatch in {source} for '[templates]'.\n"
                    f"Expected a table, but got {type(templates_data).__name__}."
                )
            parsed_templates: dict[str, TemplateAliasConfig] = {}
            for k, v in templates_data.items():
                if isinstance(v, str):
                    parsed_templates[k] = TemplateAliasConfig(source=v, name=k)
                elif isinstance(v, dict):
                    unknown_keys = set(v.keys()) - {
                        "source",
                        "name",
                        "description",
                        "trusted",
                    }
                    if unknown_keys:
                        raise ConfigurationError(
                            f"Unrecognized fields in '[templates.{k}]': {', '.join(sorted(unknown_keys))}.\n"
                            "Allowed fields are: source, name, description, trusted."
                        )
                    if "source" not in v or not isinstance(v["source"], str):
                        raise ConfigurationError(
                            f"Missing or invalid required field 'source' in '[templates.{k}'].\n"
                            "Expected a string path or URL."
                        )
                    name_val = v.get("name")
                    if name_val is not None and not isinstance(name_val, str):
                        raise ConfigurationError(
                            f"Type mismatch in '[templates.{k}].name'. Expected string, got {type(name_val).__name__}."
                        )
                    desc_val = v.get("description", "")
                    if not isinstance(desc_val, str):
                        raise ConfigurationError(
                            f"Type mismatch in '[templates.{k}].description'. Expected string, got {type(desc_val).__name__}."
                        )
                    trusted_val = v.get("trusted", False)
                    if not isinstance(trusted_val, bool):
                        raise ConfigurationError(
                            f"Type mismatch in '[templates.{k}].trusted'. Expected boolean, got {type(trusted_val).__name__}."
                        )
                    parsed_templates[k] = TemplateAliasConfig(
                        source=v["source"],
                        name=name_val or k,
                        description=desc_val,
                        trusted=trusted_val,
                    )
                else:
                    raise ConfigurationError(
                        f"Type mismatch in {source} for '[templates].{k}'.\n"
                        f"Expected string or table, but got {type(v).__name__}."
                    )
            updates["templates"] = parsed_templates

        return replace(instance, **updates)


@functools.cache
def _load_cached_user_config() -> UserConfig:
    """Loads and parses the selected Protostar configuration file with caching.

    Raises:
        ConfigurationError: If an explicitly selected configuration file is
            missing or unreadable. A missing file at the default location is
            not an error; it simply yields built-in defaults.
    """
    source = active_config_source()
    logger.debug(
        "Loading configuration from %s (origin=%s)", source.path, source.origin
    )
    instance = UserConfig()

    if source.path is None:
        return instance

    if not source.path.is_file():
        if source.origin is ConfigOrigin.EXPLICIT:
            raise ConfigurationError(
                f"Configuration file '{source.path}' does not exist.",
                hint=(
                    f"Point '--config' or ${CONFIG_ENV_VAR} at a readable file, "
                    "or pass '--no-config' to run without one."
                ),
            )
        return instance

    try:
        content = source.path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigurationError(
            f"Configuration file '{source.path}' could not be read.",
            hint="Verify the file's permissions and UTF-8 encoding.",
        ) from error

    return UserConfig._parse_and_merge(content, str(source.path), instance)


def clear_user_config_cache() -> None:
    """Clears the memoized global UserConfig instance cache."""
    _load_cached_user_config.cache_clear()


def _parse_pyproject_payload(
    identity: str, raw: object, source: str
) -> PyprojectPayload:
    """Parses one [dev.pyproject] entry: a TOML string, or a content/requires table."""
    if isinstance(raw, str):
        return PyprojectPayload(raw)

    location = f"[dev.pyproject].{identity}"
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("content"), str)
        or set(raw) - {"content", "requires"}
    ):
        raise ConfigurationError(
            f"Invalid structured payload in configuration source '{source}' for '{location}'.",
            hint='Use a TOML string, or a table with a string "content" and an optional "requires" condition.',
        )

    requires = raw.get("requires")
    return PyprojectPayload(
        raw["content"],
        parse_condition(requires, location, source) if requires is not None else None,
    )


def _string_list(raw: object, location: str, source: str) -> tuple[str, ...]:
    """Returns an array of strings, or raises naming where it belongs."""
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigurationError(
            f"Type mismatch in configuration source '{source}' for '{location}'.\n"
            "Expected an array of strings.",
            hint='Define it as an array of strings: ["..."]',
        )
    return tuple(raw)


def _parse_optional(raw: object, source: str) -> list[OptionalContent]:
    """Parses [[optional]]: blocks of content that apply while a condition holds."""
    hint = (
        'Use [[optional]] with requires = "..." and any of dependencies, '
        "dev_dependencies, docs_dependencies, and files."
    )
    if not isinstance(raw, list):
        raise ConfigurationError(
            f"Type mismatch in configuration source '{source}' for '[[optional]]'.\n"
            f"Expected an array of tables, but got {type(raw).__name__}.",
            hint=hint,
        )
    fields = ("dependencies", "dev_dependencies", "docs_dependencies", "files")
    blocks: list[OptionalContent] = []
    for index, entry in enumerate(raw):
        location = f"[[optional]] #{index + 1}"
        if (
            not isinstance(entry, dict)
            or "requires" not in entry
            or set(entry) - {"requires", *fields}
            or not set(entry) & set(fields)
        ):
            raise ConfigurationError(
                f"Invalid {location} in configuration source '{source}'.", hint=hint
            )
        values = {
            name: _string_list(entry[name], f"{location}.{name}", source)
            for name in fields
            if name in entry
        }
        if "files" in values:
            values["files"] = tuple(
                Path(path).as_posix() + ("/" if path.endswith("/") else "")
                for path in values["files"]
            )
        blocks.append(
            OptionalContent(
                parse_condition(entry["requires"], location, source), **values
            )
        )
    return blocks


# Root keys of a template that hold structure; every other root boolean is a
# tooling flag. `variables` is read from the raw template, not the blueprint.
TEMPLATE_STRUCTURAL_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "version",
        "dependency_includes",
        "description",
        "dependencies",
        "directories",
        "vcs_ignores",
        "system_tasks",
        "post_install_tasks",
        "docs_dependencies",
        "dev",
        "files",
        "appends",
        "variables",
        "migrations",
        "options",
        "optional",
    }
)


@dataclass
class TemplateBlueprint:
    """Represents the parsed template state for target environments."""

    reference: TemplateReference | None = field(default=None, repr=False)
    version: str = field(
        default="",
        metadata={"description": "Informational template version.", "example": "1.0.0"},
    )
    dependency_includes: list[DependencyInclude] = field(
        default_factory=list,
        metadata={
            "description": "Typed dependency-group include edges.",
            "example": [{"group": "dev", "include": "docs"}],
        },
    )

    name: str = field(
        default="",
        metadata={
            "description": "Human-readable display name of the template.",
            "example": "FastAPI",
        },
    )
    description: str = field(
        default="",
        metadata={
            "description": "Short explanation of the template stack and purpose.",
            "example": "FastAPI web application scaffold with Uvicorn and Pydantic",
        },
    )
    dependencies: list[str] = field(
        default_factory=list,
        metadata={
            "description": "Core runtime packages installed into the project environment.",
            "example": ["fastapi", "uvicorn", "pydantic"],
        },
    )
    dev_dependencies: list[str] = field(
        default_factory=list,
        metadata={
            "description": "Development packages not shipped to production.",
            "example": ["pytest", "mypy", "ruff"],
        },
    )
    docs_dependencies: list[str] = field(
        default_factory=list,
        metadata={
            "description": "Documentation toolchain dependencies.",
            "example": ["mkdocstrings[python]", "zensical"],
        },
    )
    directories: list[str] = field(
        default_factory=list,
        metadata={
            "description": "Relative directory paths scaffolded in the workspace.",
            "example": ["src/<% PACKAGE_NAME %>", "tests", "data/raw"],
        },
    )
    vcs_ignores: list[str] = field(
        default_factory=list,
        metadata={
            "description": "Patterns appended and deduplicated in .gitignore.",
            "example": ["*.log", ".env", "local_data/"],
        },
    )
    system_tasks: list[list[str]] = field(
        default_factory=list,
        metadata={
            "description": "Commands executed before dependency installation.",
            "example": [["git", "init"]],
        },
    )
    post_install_tasks: list[list[str]] = field(
        default_factory=list,
        metadata={
            "description": "Commands executed after dependencies are installed.",
            "example": [["uv", "run", "nbdime", "config-git", "--enable"]],
        },
    )
    files: dict[str, str] = field(
        default_factory=dict,
        metadata={
            "description": "Exact file paths mapped to their raw template contents.",
            "example": {
                "README.md": "# <% PROJECT_NAME %>\n\nAuto-scaffolded using custom template.",
                "src/<% PACKAGE_NAME %>/__init__.py": '"""<% PROJECT_NAME %> package."""\n__version__ = "0.1.0"',
                "compose.yaml": "services: {}\n",
            },
        },
    )
    pyproject_injections: dict[str, PyprojectPayload] = field(
        default_factory=dict,
        metadata={
            "description": "Managed TOML configuration; personal metadata is seed-only; dependency tables and tool.protostar are forbidden. A payload is a TOML string, or a table with `content` and an optional `requires` condition that injects it only while the condition holds.",
            "example": {
                "custom_linting": {
                    "requires": "ruff",
                    "content": '[tool.ruff.lint]\nextend-select = ["I", "UP", "B"]',
                },
                "build_backend": '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"',
            },
        },
    )
    appends: dict[str, dict[str, AppendContribution]] = field(
        default_factory=dict,
        metadata={
            "description": "Named non-TOML regions with stable IDs, content, and an optional requires condition.",
            "example": {
                ".envrc": {
                    "project_environment": {"content": "export REGION=<% REGION %>"}
                }
            },
        },
    )
    options: dict[str, TemplateOption] = field(
        default_factory=dict,
        metadata={
            "description": "Choices the template offers. A bool option declares a bool default; a choice option declares its choices and a default among them. Content opts in with requires; an option never renders into text.",
            "example": {
                "database": {
                    "description": "The database the service uses.",
                    "choices": ["none", "postgres", "sqlite"],
                    "default": "none",
                },
                "compose": {
                    "description": "Ship a compose.yaml.",
                    "default": False,
                },
            },
        },
    )
    optional: list[OptionalContent] = field(
        default_factory=list,
        metadata={
            "description": 'Content that applies only while its requires condition holds: a tool, a bool option, or option=value, or an array of them that must all hold. Files are template paths, or every file under a path ending in "/"; content listed by several blocks applies while any of them holds.',
            "example": [
                {"requires": "pytest", "dev_dependencies": ["pytest-cov"]},
                {"requires": "database=postgres", "dependencies": ["psycopg[binary]"]},
                {"requires": "compose", "files": ["compose.yaml"]},
            ],
        },
    )
    migrations: list[Migration] = field(
        default_factory=list,
        metadata={
            "description": "Changes a project makes as it moves past a template version: moved and removed seed files, and renamed variables. Requires a PEP 440 version.",
            "example": [
                {
                    "version": "1.0.0",
                    "rename": [
                        {
                            "from": "src/<% PACKAGE_NAME %>/settings.py",
                            "to": "src/<% PACKAGE_NAME %>/config.py",
                        }
                    ],
                    "remove": ["setup.cfg"],
                    "rename_variables": [{"from": "ORG", "to": "ORGANIZATION"}],
                }
            ],
        },
    )
    tooling_overrides: dict[str, bool] = field(
        default_factory=dict,
        metadata={
            "description": "Boolean toggles configuring baseline tooling opinions.",
            "example": None,
        },
    )

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

        # Validate name
        if "name" in data:
            if not isinstance(data["name"], str):
                raise ConfigurationError(
                    f"Type mismatch in configuration source '{source}' for 'name'.\n"
                    f"Expected string, but got {type(data['name']).__name__}.",
                    hint='Define name as a string: name = "my-template"',
                )
            instance.name = data["name"]

        # Validate description
        if "description" in data:
            if not isinstance(data["description"], str):
                raise ConfigurationError(
                    f"Type mismatch in configuration source '{source}' for 'description'.\n"
                    f"Expected string, but got {type(data['description']).__name__}.",
                    hint='Define description as a string: description = "Template description"',
                )
            instance.description = data["description"]

        # Validate string list fields
        string_list_fields = [
            "dependencies",
            "directories",
            "vcs_ignores",
            "docs_dependencies",
        ]
        for field_name in string_list_fields:
            if field_name in data:
                val = data[field_name]
                if not isinstance(val, list):
                    raise ConfigurationError(
                        f"Type mismatch in configuration source '{source}' for '{field_name}'.\n"
                        f"Expected array of strings, but got {type(val).__name__}.",
                        hint=f'Define {field_name} as a TOML array: {field_name} = ["..."]',
                    )
                for item in val:
                    if not isinstance(item, str):
                        raise ConfigurationError(
                            f"Type mismatch in configuration source '{source}' for '{field_name}' elements.\n"
                            f"Expected string, but got {type(item).__name__}.",
                            hint=f"Ensure all elements in '{field_name}' are strings: {field_name} = [\"...\"]",
                        )
                setattr(instance, field_name, val)

        # Validate task list fields (list of lists of strings)
        task_fields = ["system_tasks", "post_install_tasks"]
        for field_name in task_fields:
            if field_name in data:
                val = data[field_name]
                if not isinstance(val, list):
                    raise ConfigurationError(
                        f"Type mismatch in configuration source '{source}' for '{field_name}'.\n"
                        f"Expected array of commands, but got {type(val).__name__}.",
                        hint=f'Define {field_name} as an array of command arrays: {field_name} = [["command", "arg"]]',
                    )
                for task in val:
                    if not isinstance(task, list):
                        raise ConfigurationError(
                            f"Type mismatch in configuration source '{source}' for '{field_name}' command elements.\n"
                            f"Expected array of strings, but got {type(task).__name__}.",
                            hint=f'Define each command in \'{field_name}\' as an array of strings: {field_name} = [["command", "arg"]]',
                        )
                    for part in task:
                        if not isinstance(part, str):
                            raise ConfigurationError(
                                f"Type mismatch in configuration source '{source}' for '{field_name}' command arguments.\n"
                                f"Expected string, but got {type(part).__name__}.",
                                hint=f"Ensure all command arguments in '{field_name}' are strings.",
                            )
                setattr(instance, field_name, val)

        # Extract environment fields
        if "dev" in data:
            dev_data = data["dev"]
            if not isinstance(dev_data, dict):
                raise ConfigurationError(
                    f"Type mismatch in configuration source '{source}' for '[dev]'.\n"
                    f"Expected table, but got {type(dev_data).__name__}.",
                    hint="Define dev as a TOML table: [dev]",
                )
            if "dev_dependencies" in dev_data:
                dev_deps = dev_data["dev_dependencies"]
                if not isinstance(dev_deps, list):
                    raise ConfigurationError(
                        f"Type mismatch in configuration source '{source}' for '[dev].dev_dependencies'.\n"
                        f"Expected array of strings, but got {type(dev_deps).__name__}.",
                        hint='Define dev_dependencies as a TOML array: dev_dependencies = ["..."]',
                    )
                for item in dev_deps:
                    if not isinstance(item, str):
                        raise ConfigurationError(
                            f"Type mismatch in configuration source '{source}' for '[dev].dev_dependencies' elements.\n"
                            f"Expected string, but got {type(item).__name__}.",
                            hint="Ensure all elements in 'dev_dependencies' are strings: dev_dependencies = [\"...\"]",
                        )
                instance.dev_dependencies = dev_deps

            unknown = sorted(set(dev_data) - {"dev_dependencies", "pyproject"})
            if unknown:
                raise ConfigurationError(
                    f"Unknown keys in configuration source '{source}' for '[dev]': "
                    f"{', '.join(unknown)}.",
                    hint='Packages a tool or option needs go in [[optional]] with requires = "...".',
                )

            if "pyproject" in dev_data:
                if not isinstance(dev_data["pyproject"], dict):
                    raise ConfigurationError(
                        f"Type mismatch in configuration source '{source}' for '[dev].pyproject'.\n"
                        f"Expected table, but got {type(dev_data['pyproject']).__name__}.",
                        hint="Define pyproject as a table: [dev.pyproject]",
                    )
                for identity, raw in dev_data["pyproject"].items():
                    instance.pyproject_injections[identity] = _parse_pyproject_payload(
                        identity, raw, source
                    )

        if "files" in data:
            if not isinstance(data["files"], dict):
                raise ConfigurationError(
                    f"Type mismatch in configuration source '{source}' for '[files]'.\n"
                    f"Expected table, but got {type(data['files']).__name__}.",
                    hint="Define files as a table: [files]",
                )
            for file_path, file_content in data["files"].items():
                if not isinstance(file_content, str):
                    raise ConfigurationError(
                        f"Type mismatch in configuration source '{source}' for '[files].\"{file_path}\"'.\n"
                        f"Expected string content, but got {type(file_content).__name__}.",
                        hint=f'Define file content as a string: [files]\n"{file_path}" = "..."',
                    )
            instance.files = data["files"]

        if "appends" in data:
            appends_data = data["appends"]
            if not isinstance(appends_data, dict):
                raise ConfigurationError(
                    "Expected a table for '[appends]'.",
                    hint='Use [appends.".envrc".stable_id] with a content field.',
                )
            for path, records in appends_data.items():
                if not isinstance(records, dict):
                    raise ConfigurationError(
                        f"Anonymous append schema is unsupported for '[appends].{path}'.",
                        hint='Use [appends.".envrc".stable_id] with content = "...".',
                    )
                for identity, record in records.items():
                    validate_region_id(identity)
                    if (
                        not isinstance(record, dict)
                        or "content" not in record
                        or set(record) - {"content", "requires"}
                        or not isinstance(record["content"], str)
                    ):
                        raise ConfigurationError(
                            f"Invalid named append record for '[appends].{path}'.",
                            hint="Each stable ID must contain a string content field "
                            "and an optional requires condition.",
                        )
                    requires = record.get("requires")
                    instance.appends.setdefault(path, {})[identity] = (
                        AppendContribution(
                            identity,
                            record["content"],
                            parse_condition(
                                requires, f"[appends].{path}.{identity}", source
                            )
                            if requires is not None
                            else None,
                        )
                    )

        if "version" in data:
            if not isinstance(data["version"], str):
                raise ConfigurationError(
                    "Template version must be a string.", hint='Use version = "1.0.0".'
                )
            instance.version = data["version"]
        if "dependency_includes" in data:
            edges = data["dependency_includes"]
            if not isinstance(edges, list):
                raise ConfigurationError(
                    "dependency_includes must be an array of records.",
                    hint='Use dependency_includes = [{group = "dev", include = "docs"}].',
                )
            for edge in edges:
                if (
                    not isinstance(edge, dict)
                    or set(edge) != {"group", "include"}
                    or not all(isinstance(v, str) for v in edge.values())
                ):
                    raise ConfigurationError(
                        "Invalid dependency include record.",
                        hint="Declare string group and include fields.",
                    )
                try:
                    group, include = (
                        DependencyGroup(edge["group"]),
                        DependencyGroup(edge["include"]),
                    )
                except ValueError as e:
                    raise ConfigurationError(
                        "Unsupported dependency include group.",
                        hint="Use dev or docs groups.",
                    ) from e
                instance.dependency_includes.append(DependencyInclude(group, include))

        instance.migrations = list(parse_migrations(data, source))
        if "options" in data:
            instance.options = parse_options(data["options"], source)
        if "optional" in data:
            instance.optional = _parse_optional(data["optional"], source)

        # Extract tooling overrides dynamically (root-level boolean flags)
        for key, value in data.items():
            if key not in TEMPLATE_STRUCTURAL_KEYS and isinstance(value, bool):
                instance.tooling_overrides[key] = value

        instance._validate_declarations()
        return instance

    def _validate_declarations(self) -> None:
        """Validates schema boundaries even before the manifest is assembled."""
        from .manifest import DependencyManifest

        deps = DependencyManifest()
        for edge in self.dependency_includes:
            deps.add_include(edge.group, edge.include)
        for path in self.files.keys() | self.appends.keys():
            validate_target(path)

        def normalize_keys(mapping: dict[str, Any]) -> dict[str, Any]:
            normalized: dict[str, Any] = {}
            for path, value in mapping.items():
                key = Path(path).as_posix()
                if key in normalized:
                    raise ConfigurationError(
                        f"Duplicate normalized target '{key}'.",
                        hint="Use one relative spelling for each target.",
                    )
                normalized[key] = value
            return normalized

        if "pyproject.toml" in self.files:
            raise ConfigurationError(
                "Free-form pyproject.toml replacement is unsupported.",
                hint="Use dev.pyproject structured contributions; tool.protostar is reserved.",
            )
        self.files = normalize_keys(self.files)
        self.appends = normalize_keys(self.appends)
        if self.files.keys() & self.appends.keys() or (
            "pyproject.toml" in self.files and self.pyproject_injections
        ):
            raise ConfigurationError(
                "Ambiguous free-form and managed targets.",
                hint="Do not combine files with structured or region contributions at the same path.",
            )
        for path in self.appends:
            if path.endswith(".toml"):
                raise ConfigurationError(
                    "TOML append regions are unsupported.",
                    hint="Use dev.pyproject for TOML configuration.",
                )
        for payload in self.pyproject_injections.values():
            rendered = render_template(
                payload.content,
                dict.fromkeys(extract_variables(payload.content), "placeholder"),
            )
            validate_configuration(rendered)
        self._validate_conditions()

    def _validate_conditions(self) -> None:
        """Checks that every condition names a tool or a declared option, rightly.

        Raises:
            ConfigurationError: If an option shares a tool's name, a term names
                neither, a term's value doesn't fit its option, or no condition
                names a declared option.
        """
        # Local import: recipe sits above config in the import graph.
        from .recipe import Tool

        tools = {tool.value for tool in Tool}
        clashing = sorted(self.options.keys() & (tools | {"docker"}))
        if clashing:
            raise ConfigurationError(
                f"Options share a name with a tool: {', '.join(clashing)}.",
                hint="Rename each option; a requires term names a tool or an option.",
            )
        conditions: list[tuple[str, Condition]] = [
            (f"[dev.pyproject].{identity}", payload.requires)
            for identity, payload in self.pyproject_injections.items()
            if payload.requires is not None
        ]
        conditions += [
            (f"[appends].{path}.{identity}", record.requires)
            for path, records in self.appends.items()
            for identity, record in records.items()
            if record.requires is not None
        ]
        conditions += [
            (f"[[optional]] #{index + 1}", block.requires)
            for index, block in enumerate(self.optional)
        ]
        used: set[str] = set()
        for location, condition in conditions:
            for term in condition.terms:
                option = self.options.get(term.name)
                if option is None:
                    if term.name in tools and term.value is None:
                        continue
                    raise ConfigurationError(
                        f"{location} requires {str(term)!r}, which is neither a "
                        "tool nor a declared option.",
                        hint=f"Declare [options.{term.name}], or name a tool: "
                        f"{', '.join(sorted(tools))}.",
                    )
                used.add(term.name)
                if option.choices and term.value not in option.choices:
                    raise ConfigurationError(
                        f"{location} requires {str(term)!r}, but option "
                        f"{term.name!r} is a choice among: {', '.join(option.choices)}.",
                        hint=f'Write requires = "{term.name}=VALUE" with one of its choices.',
                    )
                if not option.choices and term.value is not None:
                    raise ConfigurationError(
                        f"{location} requires {str(term)!r}, but option "
                        f"{term.name!r} is on or off.",
                        hint=f'Write requires = "{term.name}" to require it on.',
                    )
        unused = sorted(self.options.keys() - used)
        if unused:
            raise ConfigurationError(
                f"[options] declares options no requires names: {', '.join(unused)}.",
                hint="Gate content on each option with requires, or remove it.",
            )

    def _validate_optional_files(self) -> None:
        """Checks that every file an [[optional]] block lists is one the template ships.

        Raises:
            ConfigurationError: If an entry matches no template file.
        """
        for index, block in enumerate(self.optional):
            for entry in block.files:
                probe = OptionalContent(block.requires, files=(entry,))
                if not any(probe.covers(path) for path in self.files):
                    raise ConfigurationError(
                        f"[[optional]] #{index + 1} lists {entry!r}, which the "
                        "template doesn't ship.",
                        hint="List a path under template/ or in [files], or a "
                        'directory ending in "/".',
                    )

    def gated(self, path: str) -> list[OptionalContent]:
        """Returns the [[optional]] blocks that list a template file."""
        return [block for block in self.optional if block.covers(path)]


@dataclass(frozen=True)
class TemplateSource:
    """One acquired template revision, held in memory until it is rendered.

    Loading and rendering are separate steps so a caller can ask which
    variables a template needs before supplying values: the engine never
    prompts, and a remote template is fetched once.

    Attributes:
        template_bytes: The raw ``protostar.toml`` bytes.
        files: Text files under ``template/``, keyed by relative path.
        reference: The source identity recorded in the lock file.
    """

    template_bytes: bytes
    files: dict[str, str]
    reference: TemplateReference

    @classmethod
    def load(
        cls,
        target: str,
        *,
        built_in: str | None = None,
        display_name: str | None = None,
    ) -> "TemplateSource":
        """Acquires a template from a local path, directory, or remote URL.

        Args:
            target: A ``protostar.toml`` path, a template directory, or a URL.
            built_in: The built-in template alias, when ``target`` is one.
            display_name: The name the user selected the template by.

        Returns:
            The acquired template, not yet rendered.

        Raises:
            TemplateResolutionError: If the target cannot be found or read.
        """
        if target.startswith("http://") or target.startswith("https://"):
            return cls.from_remote(fetch_remote_template(target), display_name)
        target_path = Path(target).expanduser()
        if not target_path.exists():
            raise TemplateResolutionError(
                target, f"Configuration file not found: {target_path}"
            )

        if target_path.is_file():
            toml_path = target_path
            base_dir = target_path.parent
        else:
            toml_path = target_path / "protostar.toml"
            if not toml_path.exists():
                raise TemplateResolutionError(
                    target, f"Configuration file not found: {toml_path}"
                )
            base_dir = target_path

        template_bytes = toml_path.read_bytes()
        try:
            template_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise TemplateEncodingError(target, toml_path.name) from e

        raw_files: dict[str, str] = {}
        template_dir = base_dir / "template"
        if template_dir.exists() and template_dir.is_dir():
            for file_path in template_dir.rglob("*"):
                if file_path.is_dir():
                    continue
                if ".DS_Store" in file_path.parts or "__pycache__" in file_path.parts:
                    continue
                rel_path = str(file_path.relative_to(template_dir))
                try:
                    raw_files[rel_path] = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError as e:
                    raise TemplateEncodingError(
                        target, f"template/{Path(rel_path).as_posix()}"
                    ) from e

        reference = TemplateReference(
            TemplateOrigin.BUILT_IN if built_in else TemplateOrigin.LOCAL,
            built_in or toml_path.expanduser().resolve().as_posix(),
            hashlib.sha256(template_bytes).hexdigest(),
            display_name,
        )
        return cls(template_bytes, raw_files, reference)

    @classmethod
    def from_remote(
        cls, remote: RemoteTemplate, display_name: str | None = None
    ) -> "TemplateSource":
        """Wraps a remote template acquired at one revision.

        Args:
            remote: The acquired template, its source, and its ref.
            display_name: The name the user selected the template by.
        """
        acquired = remote.acquired
        reference = TemplateReference(
            TemplateOrigin.REMOTE,
            remote.source.locator,
            hashlib.sha256(acquired.template_bytes).hexdigest(),
            display_name,
            path=remote.source.path,
            ref=remote.ref,
            revision=remote.revision,
        )
        return cls(acquired.template_bytes, dict(acquired.files), reference)

    @functools.cached_property
    def variables(self) -> frozenset[str]:
        """The template's custom variables, excluding built-in ones."""
        text = "\n".join(
            [self.template_bytes.decode("utf-8"), *self.files, *self.files.values()]
        )
        return frozenset(extract_variables(text)) - BUILT_IN_VARIABLES

    @functools.cached_property
    def _data(self) -> dict[str, Any]:
        """The raw template's root table, before any variable renders.

        Raises:
            ConfigurationError: If the template is not valid TOML.
        """
        try:
            return tomllib.loads(self.template_bytes.decode("utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                f"Syntax error in configuration source '{self.reference.locator}'.\n"
                f"Details: {e}\n"
                "Please fix the syntax error to proceed."
            ) from e

    @property
    def version(self) -> str | None:
        """The version the raw template declares, if any."""
        version = self._data.get("version")
        return version if isinstance(version, str) else None

    @functools.cached_property
    def migrations(self) -> tuple[Migration, ...]:
        """The template's migrations, read before any variable renders.

        A variable rename has to be known before rendering, which needs the
        variable under its new name.

        Raises:
            ConfigurationError: If the template is not valid TOML.
            TemplateResolutionError: If a migration is malformed.
        """
        return parse_migrations(self._data, self.reference.locator)

    @functools.cached_property
    def descriptions(self) -> dict[str, str]:
        """Descriptions the template's ``[variables]`` table declares, by name.

        Declarations are read from the raw template, before any value renders,
        so a caller can explain each variable while asking for its value.

        Raises:
            ConfigurationError: If the template is not valid TOML.
            TemplateResolutionError: If the table is malformed or declares a
                variable the template never uses.
        """
        target = self.reference.locator
        declared = self._data.get("variables", {})
        hint = 'Declare each variable as [variables.NAME] with description = "...".'
        if not isinstance(declared, dict) or any(
            not isinstance(entry, dict)
            or set(entry) != {"description"}
            or not isinstance(entry["description"], str)
            for entry in declared.values()
        ):
            raise TemplateResolutionError(
                target, "The [variables] table is malformed.", hint=hint
            )
        unused = sorted(declared.keys() - self.variables)
        if unused:
            raise TemplateResolutionError(
                target,
                f"[variables] declares variables the template never uses: "
                f"{', '.join(unused)}.",
                hint="Remove the declarations, or use each as <% NAME %>. "
                "Built-in variables need no declaration.",
            )
        return {name: entry["description"] for name, entry in sorted(declared.items())}

    @functools.cached_property
    def options(self) -> dict[str, TemplateOption]:
        """Options the template's ``[options]`` table offers, by name.

        Declarations are read from the raw template, before any value renders,
        so a caller can offer each option before choosing values.

        Raises:
            ConfigurationError: If the template is not valid TOML, or the table
                is malformed.
            TemplateResolutionError: If an option shares a variable's name.
        """
        target = self.reference.locator
        options = parse_options(self._data.get("options", {}), target)
        clashing = sorted(options.keys() & (self.variables | BUILT_IN_VARIABLES))
        if clashing:
            raise TemplateResolutionError(
                target,
                f"Options share a name with variables: {', '.join(clashing)}.",
                hint="An option chooses content and a variable fills in text; "
                "give each its own name.",
            )
        return options

    def render(self, context: Mapping[str, str]) -> TemplateBlueprint:
        """Renders the template entirely in memory.

        Built-in variables absent from ``context`` stay as placeholders and are
        filled in later, when the project's own values are known.

        Args:
            context: Values for the template's custom variables, and optionally
                for built-in ones.

        Returns:
            The parsed, rendered blueprint.

        Raises:
            MissingTemplateVariablesError: If a custom variable has no value.
            TemplateResolutionError: If the ``[variables]`` table is invalid.
        """
        target = self.reference.locator
        _ = self.descriptions
        _ = self.options
        missing = tuple(sorted(self.variables - context.keys()))
        if missing:
            raise MissingTemplateVariablesError(target, missing)

        values = dict(context)
        rendered_toml = render_template(
            self.template_bytes.decode("utf-8"), values, escape_toml=True
        )
        blueprint = TemplateBlueprint._parse(rendered_toml, target)
        blueprint.files.update(
            {
                render_template(path, values, escape_toml=False): render_template(
                    content, values, escape_toml=False
                )
                for path, content in self.files.items()
            }
        )
        blueprint.reference = replace(self.reference, version=blueprint.version or None)
        blueprint._validate_declarations()
        blueprint._validate_optional_files()
        return blueprint
