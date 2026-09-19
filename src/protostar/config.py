"""Configuration management and schema definitions for Protostar."""

import functools
import hashlib
import logging
import os
import tempfile
import tomllib
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .errors import ConfigurationError, TemplateResolutionError
from .ide import IDEType
from .intent import (
    AppendContribution,
    DependencyGroup,
    DependencyInclude,
    PyprojectPayload,
    TemplateOrigin,
    TemplateReference,
    validate_configuration,
    validate_region_id,
    validate_target,
)
from .interpolation import extract_variables, render_template
from .network import resolve_remote_source, resolve_remote_template

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
_xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
if _xdg_config_home:
    CONFIG_FILE = Path(_xdg_config_home) / "protostar" / "config.toml"
else:
    CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

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

# [templates]
# my-org-api = "https://raw.githubusercontent.com/MyOrg/standards/main/api.toml"
# data-science-base = "~/Developer/templates/ds_base.toml"
#
# [templates.enterprise-api]
# name = "Enterprise API"
# source = "https://github.com/myorg/enterprise-template.git"
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
    templates: dict[str, TemplateAliasConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalizes template configuration dictionary and validates invariants."""
        if self.pre_commit and self.prek:
            raise ConfigurationError(
                "Cannot configure both 'pre_commit = true' and 'prek = true'.",
                hint="Choose either pre_commit or prek as your default git hook manager in your configuration.",
            )

        normalized: dict[str, TemplateAliasConfig] = {}
        for k, v in self.templates.items():
            if isinstance(v, str):
                normalized[k] = TemplateAliasConfig(source=v, name=k)
            else:
                normalized[k] = v
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
    """Loads and parses the global Protostar configuration file with caching."""
    logger.debug(
        "Loading global configuration from %s (exists=%s)",
        CONFIG_FILE,
        CONFIG_FILE.exists(),
    )
    instance = UserConfig()

    if CONFIG_FILE.exists():
        instance = UserConfig._parse_and_merge(
            CONFIG_FILE.read_text(encoding="utf-8"), str(CONFIG_FILE), instance
        )

    return instance


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
            hint='Use a TOML string, or a table with a string "content" and an optional "requires" tool name.',
        )

    requires = raw.get("requires")
    if requires is not None:
        _validated_tool(requires, location, source)
    return PyprojectPayload(raw["content"], requires)


def _validated_tool(name: object, location: str, source: str) -> str:
    """Returns a known tool key, or raises listing the valid ones."""
    # Local import: recipe sits above config in the import graph.
    from .recipe import Tool

    tools = sorted(tool.value for tool in Tool)
    if not isinstance(name, str) or name not in tools:
        raise ConfigurationError(
            f"Unknown tool {name!r} in configuration source '{source}' for '{location}'.",
            hint=f"Use one of: {', '.join(tools)}.",
        )
    return name


def _parse_tool_dependencies(raw: object, source: str) -> dict[str, list[str]]:
    """Parses [dev.tool_dependencies]: each tool maps to the packages it needs."""
    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"Type mismatch in configuration source '{source}' for '[dev].tool_dependencies'.\n"
            f"Expected table, but got {type(raw).__name__}.",
            hint='Map each tool to its packages: [dev.tool_dependencies]\npytest = ["pytest-cov"]',
        )
    parsed: dict[str, list[str]] = {}
    for tool, packages in raw.items():
        location = f"[dev.tool_dependencies].{tool}"
        _validated_tool(tool, location, source)
        if not isinstance(packages, list) or not all(
            isinstance(package, str) for package in packages
        ):
            raise ConfigurationError(
                f"Type mismatch in configuration source '{source}' for '{location}'.\n"
                "Expected an array of strings.",
                hint=f'Define the packages as an array: {tool} = ["package"]',
            )
        parsed[tool] = list(packages)
    return parsed


@dataclass
class TemplateBlueprint:
    """Represents the parsed template state for target environments."""

    custom_variables: frozenset[str] = field(default=frozenset(), repr=False)
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
    tool_dev_dependencies: dict[str, list[str]] = field(
        default_factory=dict,
        metadata={
            "description": "Development packages installed only while the named tool is enabled.",
            "example": {"pytest": ["pytest-cov"]},
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
            },
        },
    )
    pyproject_injections: dict[str, PyprojectPayload] = field(
        default_factory=dict,
        metadata={
            "description": "Managed TOML configuration; personal metadata is seed-only; dependency tables and tool.protostar are forbidden. A payload is a TOML string, or a table with `content` and an optional `requires` tool that injects it only while that tool is enabled.",
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
            "description": "Named non-TOML regions with stable IDs and content.",
            "example": {
                ".envrc": {"project_environment": {"content": "export PROJECT=example"}}
            },
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
    def load(
        cls,
        target: str,
        template_context: dict[str, str] | None = None,
        variable_resolver: Callable[[list[str]], dict[str, str]] | None = None,
        *,
        built_in: str | None = None,
        display_name: str | None = None,
    ) -> "TemplateBlueprint":
        """Loads and parses a template blueprint."""
        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        remote_source = None

        try:
            if target.startswith("http://") or target.startswith("https://"):
                remote_source = resolve_remote_source(target)
                temp_dir = tempfile.TemporaryDirectory()
                temp_workspace = Path(temp_dir.name)
                target_path = resolve_remote_template(
                    remote_source.locator, temp_workspace
                )
            else:
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

            raw_files: dict[str, str] = {}
            template_dir = base_dir / "template"
            if template_dir.exists() and template_dir.is_dir():
                for file_path in template_dir.rglob("*"):
                    if file_path.is_dir():
                        continue
                    if (
                        ".DS_Store" in file_path.parts
                        or "__pycache__" in file_path.parts
                    ):
                        continue
                    rel_path = str(file_path.relative_to(template_dir))
                    raw_files[rel_path] = file_path.read_text(encoding="utf-8")

            origin = (
                TemplateOrigin.BUILT_IN
                if built_in
                else TemplateOrigin.REMOTE
                if remote_source
                else TemplateOrigin.LOCAL
            )
            locator = built_in or (
                remote_source.locator
                if remote_source
                else toml_path.expanduser().resolve().as_posix()
            )
            reference = TemplateReference(
                origin,
                locator,
                hashlib.sha256(template_bytes).hexdigest(),
                display_name,
                source_revision=remote_source.revision if remote_source else None,
            )
            return cls.from_sources(
                template_bytes,
                raw_files,
                reference,
                template_context,
                variable_resolver,
            )
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

    @classmethod
    def from_sources(
        cls,
        template_bytes: bytes,
        raw_files: dict[str, str],
        reference: TemplateReference,
        template_context: dict[str, str] | None = None,
        variable_resolver: Callable[[list[str]], dict[str, str]] | None = None,
    ) -> "TemplateBlueprint":
        """Renders one acquired source revision entirely in memory."""
        target = reference.locator
        toml_content = template_bytes.decode("utf-8")
        all_text_sources = [toml_content, *raw_files.keys(), *raw_files.values()]
        combined_text = "\n".join(all_text_sources)
        variables = extract_variables(combined_text)

        context = dict(template_context) if template_context else {}

        late_binding_vars = {
            "PYTHON_VERSION",
            "PROJECT_NAME",
            "PACKAGE_NAME",
            "CURRENT_YEAR",
            "AUTHOR_NAME",
        }
        missing = [
            v for v in variables if v not in context and v not in late_binding_vars
        ]

        if missing:
            if variable_resolver is not None:
                context.update(variable_resolver(missing))
            else:
                raise TemplateResolutionError(
                    target,
                    f"Template requires variables: {', '.join(missing)}.",
                    hint="Please provide them via CLI flags (e.g. --variable_name=value) or run in an interactive terminal.",
                )

        rendered_toml = render_template(toml_content, context, escape_toml=True)
        blueprint = cls._parse(rendered_toml, target)
        blueprint.custom_variables = frozenset(variables) - late_binding_vars

        interpolated_files: dict[str, str] = {}
        for rel_path, content in raw_files.items():
            new_path = render_template(rel_path, context, escape_toml=False)
            new_content = render_template(content, context, escape_toml=False)
            interpolated_files[new_path] = new_content

        blueprint.files.update(interpolated_files)
        blueprint.reference = replace(reference, version=blueprint.version or None)
        blueprint._validate_declarations()
        return blueprint

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

            if "tool_dependencies" in dev_data:
                instance.tool_dev_dependencies = _parse_tool_dependencies(
                    dev_data["tool_dependencies"], source
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
                        or set(record) != {"content"}
                        or not isinstance(record["content"], str)
                    ):
                        raise ConfigurationError(
                            f"Invalid named append record for '[appends].{path}'.",
                            hint="Each stable ID must contain exactly one string content field.",
                        )
                    instance.appends.setdefault(path, {})[identity] = (
                        AppendContribution(identity, record["content"])
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

        # Extract tooling overrides dynamically (root-level boolean flags)
        structural_keys = {
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
        }
        for key, value in data.items():
            if key not in structural_keys and isinstance(value, bool):
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
