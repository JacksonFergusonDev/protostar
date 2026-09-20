"""Centralized template discovery engine for Protostar.

Built-in templates share one contract, described in
``docs/developer/built-in-templates.md`` and enforced by
``tests/test_builtin_template_contract.py``.
"""

import functools
import importlib.resources
import os
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from protostar.config import UserConfig


class TemplateType(StrEnum):
    """The origin type of a template."""

    BUILT_IN = "built-in"
    GLOBAL_ALIAS = "global-alias"


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata describing an available template.

    Attributes:
        alias: CLI identifier and lookup key (e.g., 'api', 'enterprise-api').
        name: Human-readable display name (e.g., 'FastAPI', 'Enterprise API').
        description: Brief summary of the template stack and purpose.
        type: Whether the template is built-in or a global user alias.
        source: Package resource, local file path, or remote URL.
        trusted: Whether the template is trusted to execute system tasks.
    """

    alias: str
    name: str
    description: str
    type: TemplateType
    source: str
    trusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Converts TemplateInfo to a serializable dictionary."""
        return {
            "alias": self.alias,
            "name": self.name,
            "description": self.description,
            "type": str(self.type),
            "source": self.source,
            "trusted": self.trusted,
        }


_TEMPLATE_SUFFIX = ".toml"


def _builtin_alias(path: Traversable) -> str:
    """Returns the alias a packaged template resource is addressed by."""
    return path.name[: -len(_TEMPLATE_SUFFIX)]


def _builtin_template_files() -> tuple[Traversable, ...]:
    """Enumerates the template resources packaged with Protostar.

    Returns:
        Every template resource in the ``protostar.templates`` package ordered
        by file name, or an empty tuple when package resources are unreadable.
    """
    try:
        template_dir = importlib.resources.files("protostar.templates")
        items = [
            path
            for path in template_dir.iterdir()
            if path.is_file() and path.name.endswith(_TEMPLATE_SUFFIX)
        ]
    except (OSError, TypeError, ValueError, AttributeError, ModuleNotFoundError):
        return ()
    return tuple(sorted(items, key=lambda path: path.name))


@functools.cache
def builtin_template_aliases() -> frozenset[str]:
    """Returns the reserved alias of every template packaged with Protostar.

    Built-in aliases are reserved because template lookup is case-insensitive
    and built-ins are discovered ahead of user aliases. A user alias that
    shadows one would resolve to a different template per call site, so
    ``UserConfig`` rejects the collision at load time.

    Returns:
        The frozen set of built-in template aliases.
    """
    return frozenset(_builtin_alias(path) for path in _builtin_template_files())


def discover_templates(config: "UserConfig | None" = None) -> list[TemplateInfo]:
    """Discovers all available built-in templates and configured global aliases.

    Executes in under 2ms with zero network I/O. Built-in templates are read
    directly from package resources, and user aliases are resolved from
    UserConfig (reading local files when present, with synthetic non-blocking
    fallbacks for remote URLs).

    Args:
        config: Optional UserConfig instance. If None, loads from global config.

    Returns:
        List of TemplateInfo objects representing all discoverable templates.
    """
    discovered: list[TemplateInfo] = []

    # 1. Discover built-in templates from package resources
    for path in _builtin_template_files():
        alias = _builtin_alias(path)
        try:
            content = path.read_text(encoding="utf-8")
            data = tomllib.loads(content)
            name = data.get("name") or alias
            description = data.get("description", "")
        except (OSError, tomllib.TOMLDecodeError, AttributeError, TypeError):
            name = alias
            description = ""

        discovered.append(
            TemplateInfo(
                alias=alias,
                name=name,
                description=description,
                type=TemplateType.BUILT_IN,
                source="protostar.templates",
                trusted=True,
            )
        )

    # 2. Discover user aliases from UserConfig
    if config is None:
        try:
            from protostar.config import UserConfig

            config = UserConfig.load()
        except Exception:
            config = None

    if config is not None and config.templates:
        for alias, alias_cfg in sorted(config.templates.items(), key=lambda x: x[0]):
            source = alias_cfg.source
            name = alias_cfg.name or alias
            description = alias_cfg.description
            trusted = alias_cfg.trusted

            # If no explicit description was provided in config, try reading local file
            if not description and not (
                source.startswith(("http://", "https://", "git@", "ssh://"))
                or "://" in source
            ):
                try:
                    local_path = Path(os.path.expanduser(source)).resolve()
                    if local_path.is_file():
                        file_data = tomllib.loads(
                            local_path.read_text(encoding="utf-8")
                        )
                        if not alias_cfg.name and file_data.get("name"):
                            name = str(file_data["name"])
                        if file_data.get("description"):
                            description = str(file_data["description"])
                except (OSError, tomllib.TOMLDecodeError):
                    pass

            if not description:
                description = f"Global alias ({source})"

            discovered.append(
                TemplateInfo(
                    alias=alias,
                    name=name,
                    description=description,
                    type=TemplateType.GLOBAL_ALIAS,
                    source=source,
                    trusted=trusted,
                )
            )

    return discovered
