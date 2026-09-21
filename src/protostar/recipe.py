"""Versioned project intent, independent of the applied ownership ledger."""

from __future__ import annotations

import datetime
import importlib.resources
import os
import re
import stat
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING, Any

import tomlkit

from .documents.pyproject_layout import (
    Section,
    compose_children,
    insert_section,
    join_sections,
    split_sections,
)
from .errors import ConfigurationError, UnsupportedFilesystemNodeError
from .ide import IDEType
from .intent import TemplateOrigin, TemplateReference
from .manifest import ProjectMetadata
from .workspace import resolve_package_name, resolve_project_name

if TYPE_CHECKING:
    from .config import TemplateBlueprint, UserConfig
    from .modules import BootstrapModule


class Tool(StrEnum):
    """Project-selectable tooling producers."""

    DIRENV = "direnv"
    MARKDOWNLINT = "markdownlint"
    RUMDL = "rumdl"
    RUFF = "ruff"
    MYPY = "mypy"
    TY = "ty"
    PYREFLY = "pyrefly"
    PYTEST = "pytest"
    PRE_COMMIT = "pre_commit"
    PREK = "prek"
    COMMITIZEN = "commitizen"
    RENOVATE = "renovate"
    CODECOV = "codecov"
    ZENSICAL = "zensical"
    READTHEDOCS = "readthedocs"
    CI = "ci"
    RELEASE = "release"
    JUST = "just"
    AGENTS = "agents"


class SelectionLayer(StrEnum):
    """Origin of an effective tooling selection."""

    PROJECT = "project"
    TEMPLATE = "template"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ToolSelection:
    """A resolved selection with its producer and precedence intact."""

    tool: Tool
    enabled: bool
    layer: SelectionLayer


@dataclass(frozen=True)
class RecipeSource:
    """Exact source identity; revisions remain in the ownership ledger."""

    origin: TemplateOrigin
    locator: str

    def load(self, root: Path, context: dict[str, str]) -> TemplateBlueprint:
        """Acquires the recorded source, without consulting aliases."""
        from .config import TemplateBlueprint

        target = self.locator
        if self.origin is TemplateOrigin.BUILT_IN:
            target = str(
                importlib.resources.files("protostar.templates").joinpath(
                    f"{target}.toml"
                )
            )
        elif self.origin is TemplateOrigin.LOCAL:
            target = str(root / target)
        return TemplateBlueprint.load(
            target,
            template_context=context,
            built_in=self.locator if self.origin is TemplateOrigin.BUILT_IN else None,
        )

    def inspect(self, root: Path, context: dict[str, str]) -> TemplateBlueprint:
        """Loads the exact recorded revision with no remote disk acquisition."""
        if self.origin is not TemplateOrigin.REMOTE:
            from .review_workspace import capture_node

            target = (
                Path(
                    str(
                        importlib.resources.files("protostar.templates").joinpath(
                            f"{self.locator}.toml"
                        )
                    )
                )
                if self.origin is TemplateOrigin.BUILT_IN
                else root / self.locator
            ).expanduser()
            capture_node(target)
            base = target if target.is_dir() else target.parent
            if target.is_dir():
                capture_node(target / "protostar.toml")
            template = base / "template"
            capture_node(template)
            if template.is_dir():
                for path in template.rglob("*"):
                    capture_node(path)
            return self.load(root, context)
        import hashlib

        from .config import TemplateBlueprint
        from .network import acquire_inspection_source, resolve_remote_source

        source = resolve_remote_source(self.locator)
        acquired = acquire_inspection_source(source.locator)
        reference = TemplateReference(
            self.origin,
            source.locator,
            hashlib.sha256(acquired.template_bytes).hexdigest(),
            source_revision=source.revision,
        )
        return TemplateBlueprint.from_sources(
            acquired.template_bytes, acquired.files, reference, context
        )


@dataclass(frozen=True)
class ProjectRecipe:
    """Immutable schema-v1 project recipe containing no trust or variable answers."""

    source: RecipeSource | None
    python: str
    docker: bool
    ide: IDEType
    tools: tuple[tuple[Tool, bool], ...]
    fallback: tuple[tuple[Tool, bool], ...]
    context: tuple[tuple[str, str], ...]
    metadata: tuple[tuple[str, str | tuple[str, ...]], ...]
    bindings: tuple[tuple[str, str], ...] = ()

    def selections(self, opinions: dict[str, bool]) -> tuple[ToolSelection, ...]:
        """Resolves overrides, current template opinions, then captured defaults."""
        if any(
            key not in ({tool.value for tool in Tool} | {"docker"})
            or type(value) is not bool
            for key, value in opinions.items()
        ):
            raise ConfigurationError(
                "Invalid template tooling opinion.",
                hint="Use recognized tool names with boolean selections.",
            )
        overrides, fallback = dict(self.tools), dict(self.fallback)
        return tuple(
            ToolSelection(tool, overrides[tool], SelectionLayer.PROJECT)
            if tool in overrides
            else ToolSelection(tool, opinions[tool], SelectionLayer.TEMPLATE)
            if tool in opinions
            else ToolSelection(tool, fallback[tool], SelectionLayer.FALLBACK)
            for tool in Tool
        )

    def rendering_context(self) -> dict[str, str]:
        """Resolves environment bindings in memory, without exposing values."""
        context = dict(self.context)
        for variable, environment in self.bindings:
            if environment not in os.environ:
                raise ConfigurationError(
                    f"Missing environment binding for {variable}.",
                    hint=f"Set environment variable {environment} before initializing this project.",
                )
            context[variable] = os.environ[environment]
        return context

    def to_dict(self) -> dict[str, Any]:
        """Returns deterministic public recipe data without environment values."""
        return {
            "version": 1,
            "mode": "template" if self.source else "tooling-only",
            "python": self.python,
            "docker": self.docker,
            "ide": self.ide.value,
            **(
                {
                    "source": {
                        "origin": self.source.origin.value,
                        "locator": self.source.locator,
                    }
                }
                if self.source
                else {}
            ),
            "tools": dict(sorted(self.tools)),
            "fallback": dict(sorted(self.fallback)),
            "context": dict(sorted(self.context)),
            "metadata": {
                k: list(v) if isinstance(v, tuple) else v
                for k, v in sorted(self.metadata)
            },
            "bindings": dict(sorted(self.bindings)),
        }


# Tables that are omitted from pyproject.toml while empty; an absent one means empty.
_OPTIONAL_TABLES = frozenset({"tools", "metadata", "bindings"})

# The order recipe entries are written in, and where a late-added table belongs.
_RECIPE_ORDER = (
    "version",
    "mode",
    "python",
    "docker",
    "ide",
    "source",
    "tools",
    "fallback",
    "context",
    "metadata",
    "bindings",
)


def _invalid() -> ConfigurationError:
    return ConfigurationError(
        "Invalid [tool.protostar] project recipe.",
        hint="Correct the schema-v1 recipe fields; see docs/development/project-recipe.md.",
    )


def decode_recipe(data: object) -> ProjectRecipe:
    """Strictly validates recipe fields, source identity, and binding names."""
    if not isinstance(data, dict):
        raise _invalid()
    required = {"version", "mode", "python", "docker", "ide", "fallback", "context"}
    if (
        set(data) - (required | _OPTIONAL_TABLES | {"source"})
        or not required <= set(data)
        or type(data["version"]) is not int
        or data["version"] != 1
    ):
        raise _invalid()
    data = {**{table: {} for table in _OPTIONAL_TABLES}, **data}
    if (
        not isinstance(data["python"], str)
        or not re.fullmatch(r"3\.\d+(?:\.\d+)?", data["python"])
        or type(data["docker"]) is not bool
    ):
        raise _invalid()
    try:
        ide = IDEType(data["ide"])
    except (ValueError, TypeError) as e:
        raise _invalid() from e
    source = None
    if data["mode"] == "template":
        raw = data.get("source")
        if (
            not isinstance(raw, dict)
            or set(raw) != {"origin", "locator"}
            or not isinstance(raw["locator"], str)
            or not raw["locator"]
        ):
            raise _invalid()
        try:
            origin = TemplateOrigin(raw["origin"])
        except (ValueError, TypeError) as e:
            raise _invalid() from e
        locator = raw["locator"]
        if origin is TemplateOrigin.BUILT_IN:
            if locator not in {"api", "astro", "cli", "lib", "ml"}:
                raise _invalid()
        elif origin is TemplateOrigin.LOCAL:
            if (
                ".." in Path(locator).parts
                or "\\" in locator
                or "\x00" in locator
                or (
                    PureWindowsPath(locator).drive and not PureWindowsPath(locator).root
                )
            ):
                raise _invalid()
        else:
            from urllib.parse import urlsplit

            from .network import resolve_remote_source

            try:
                if (
                    not locator.startswith("https://")
                    or not urlsplit(locator).hostname
                    or resolve_remote_source(locator).locator != locator
                ):
                    raise _invalid()
            except ValueError as e:
                raise _invalid() from e
        source = RecipeSource(origin, locator)
    elif data["mode"] != "tooling-only" or "source" in data:
        raise _invalid()

    def tools(key: str) -> tuple[tuple[Tool, bool], ...]:
        raw = data[key]
        if (
            not isinstance(raw, dict)
            or any(
                k not in {tool.value for tool in Tool} or type(v) is not bool
                for k, v in raw.items()
            )
            or (key == "fallback" and set(raw) != set(Tool))
        ):
            raise _invalid()
        return tuple(sorted((Tool(k), v) for k, v in raw.items()))

    context, metadata, bindings = data["context"], data["metadata"], data["bindings"]
    names = {
        "PROJECT_NAME",
        "PACKAGE_NAME",
        "PYTHON_VERSION",
        "CURRENT_YEAR",
        "AUTHOR_NAME",
    }
    if (
        not isinstance(context, dict)
        or set(context) != names
        or any(not isinstance(v, str) for v in context.values())
    ):
        raise _invalid()
    if (
        not context["PACKAGE_NAME"].isidentifier()
        or any(c in context["PROJECT_NAME"] for c in ("/", "\\", "\x00"))
        or context["PROJECT_NAME"] in {"", ".", ".."}
        or not re.fullmatch(r"\d{4}", context["CURRENT_YEAR"])
        or context["PYTHON_VERSION"] != data["python"]
    ):
        raise _invalid()
    if not isinstance(bindings, dict) or any(
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
        or k in names
        or not isinstance(v, str)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v)
        for k, v in bindings.items()
    ):
        raise _invalid()
    allowed = {
        "description",
        "license",
        "author_name",
        "author_email",
        "github_username",
        "minimum_python",
        "supported_os",
        "docker_port",
    }
    if (
        not isinstance(metadata, dict)
        or set(metadata) - allowed
        or any(
            not (
                isinstance(v, str)
                or (
                    k == "supported_os"
                    and isinstance(v, list)
                    and all(isinstance(x, str) for x in v)
                )
            )
            for k, v in metadata.items()
        )
    ):
        raise _invalid()
    if "supported_os" in metadata and not isinstance(metadata["supported_os"], list):
        raise _invalid()
    return ProjectRecipe(
        source,
        data["python"],
        data["docker"],
        ide,
        tools("tools"),
        tools("fallback"),
        tuple(sorted(context.items())),
        tuple(
            sorted(
                (k, tuple(v) if isinstance(v, list) else v) for k, v in metadata.items()
            )
        ),
        tuple(sorted(bindings.items())),
    )


def read_recipe(path: Path) -> ProjectRecipe | None:
    """Reads and validates user intent without following unsupported nodes."""
    try:
        if path.is_symlink() or (
            path.exists() and not stat.S_ISREG(path.lstat().st_mode)
        ):
            raise UnsupportedFilesystemNodeError(path, "unsupported recipe target")
        if not path.exists():
            return None
        data = tomllib.loads(path.read_text())
        tool = data.get("tool", {})
        if not isinstance(tool, dict):
            raise _invalid()
        return decode_recipe(tool["protostar"]) if "protostar" in tool else None
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as e:
        raise _invalid() from e


def edit_recipe(content: str, recipe: ProjectRecipe) -> str:
    """Updates only recipe leaves through round-trip AST edits.

    The recipe is edited as its own section, so no other byte of the file changes.
    """
    decode_recipe(recipe.to_dict())
    try:
        raw = tomllib.loads(content)
        tool_data = raw.get("tool", {})
        if not isinstance(tool_data, dict):
            raise _invalid()
        if "protostar" in tool_data:
            decode_recipe(tool_data["protostar"])
        document = tomlkit.parse(content)
    except tomllib.TOMLDecodeError as e:
        raise _invalid() from e
    # Empty tables are noise in the file; the reader treats an absent table as empty.
    desired = {
        key: value
        for key, value in recipe.to_dict().items()
        if key not in _OPTIONAL_TABLES or value
    }

    sections = split_sections(document)
    recipe_sections = [
        i for i, section in enumerate(sections) if section.path == ("tool", "protostar")
    ]
    if len(recipe_sections) == 1:
        section = sections[recipe_sections[0]]
        section.body = _edit_recipe_text(section.body, desired)
        return join_sections(sections)
    if "protostar" not in tool_data and not any(s.path == ("tool",) for s in sections):
        tool_indexes = [i for i, s in enumerate(sections) if s.path[:1] == ("tool",)]
        index = tool_indexes[-1] + 1 if tool_indexes else len(sections)
        insert_section(
            sections,
            Section(("tool", "protostar"), _edit_recipe_text("", desired)),
            index,
        )
        return join_sections(sections)
    # Out-of-order recipe tables, or a [tool] that is not a table of tables: edit each
    # leaf where it stands.
    tool = document.setdefault("tool", tomlkit.table())
    _update_recipe(tool.setdefault("protostar", tomlkit.table()), desired)
    return tomlkit.dumps(document)


def _update_recipe(current: Any, values: dict[str, Any]) -> None:
    for key in list(current):
        if key not in values:
            del current[key]
    for key, value in values.items():
        if isinstance(value, dict):
            _update_recipe(current.setdefault(key, tomlkit.table()), value)
        elif key not in current or current[key] != value:
            current[key] = value


def _edit_recipe_text(text: str, desired: dict[str, Any]) -> str:
    """Edits the text of a lone ``[tool.protostar]`` section, or writes a new one.

    Editing leaves in place changes nothing else. Adding a table recomposes the
    section, so tables sit in schema order with one blank line between them.
    """
    document = tomlkit.parse(text)
    tool = document.setdefault("tool", tomlkit.table(is_super_table=True))
    table = tool.setdefault("protostar", tomlkit.table())
    before = {str(key) for key in table}
    _update_recipe(table, desired)
    if {str(key) for key in table} == before:
        return tomlkit.dumps(document)
    return compose_children(document, ("tool", "protostar"), _RECIPE_ORDER)


@dataclass(frozen=True)
class RecipeIntent:
    """Explicit init inputs used to establish reproducible project intent."""

    reference: TemplateReference | None = None
    metadata: ProjectMetadata | None = None
    docker: bool = False
    python: str | None = None


def establish_recipe(
    config: UserConfig, intent: RecipeIntent | None = None
) -> ProjectRecipe:
    """Captures stable built-in context and effective defaults for explicit init."""
    intent = intent or RecipeIntent()
    metadata = intent.metadata or {}
    reference = intent.reference
    python = intent.python
    docker = intent.docker
    version = python or config.python_version or "3.13"
    project_name = resolve_project_name(metadata)
    if not Path("pyproject.toml").exists() and not any(
        metadata.get(k) for k in ("project_name", "name")
    ):
        project_name = re.sub(r"[-_.]+", "-", project_name).lower()
    context = {
        "PROJECT_NAME": project_name,
        "PACKAGE_NAME": resolve_package_name(metadata),
        "PYTHON_VERSION": version,
        "CURRENT_YEAR": str(datetime.date.today().year),
        "AUTHOR_NAME": str(metadata.get("author_name") or "your-name"),
    }
    recipe = ProjectRecipe(
        RecipeSource(reference.origin, reference.locator) if reference else None,
        version,
        docker,
        IDEType(config.ide or IDEType.NONE),
        (),
        tuple(sorted((tool, bool(getattr(config, tool))) for tool in Tool)),
        tuple(sorted(context.items())),
        tuple(
            sorted(
                (k, tuple(str(x) for x in v) if isinstance(v, list) else str(v))
                for k, v in metadata.items()
                if k
                in {
                    "description",
                    "license",
                    "author_name",
                    "author_email",
                    "github_username",
                    "minimum_python",
                    "supported_os",
                    "docker_port",
                }
            )
        ),
    )
    return decode_recipe(recipe.to_dict())


def select_tooling(
    recipe: ProjectRecipe, opinions: dict[str, bool]
) -> list[BootstrapModule]:
    """Builds the tooling stack from the resolved producer selections."""
    from .modules import TOOLING_MODULES

    enabled = {s.tool for s in recipe.selections(opinions) if s.enabled}
    return [module for module in TOOLING_MODULES if Tool(module.config_key) in enabled]


@dataclass(frozen=True)
class ProducerContribution:
    """A declaration attributed to its module, including shared target fields."""

    producer: str
    tool: Tool | None
    path: tuple[str, ...]
