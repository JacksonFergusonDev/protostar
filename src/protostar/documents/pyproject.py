"""pyproject.toml policy: merge spec, layout, personal seeds, and group includes."""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Collection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tomlkit

from ..errors import ConfigurationError
from ..intent import (
    DependencyGroup,
    DependencyInclude,
    ResolverFootprint,
    StructuredContribution,
    validate_configuration,
)
from ..interpolation import extract_variables, render_template
from ..merge import MergePolicy
from ..toml_ast import TomlDocumentSpec, TomlLayout
from .pyproject_layout import format_document, place_new_sections

TARGET = "pyproject.toml"
# Personal project metadata is filled in once; later edits are the user's.
SEED_PATHS = frozenset(
    ("project", key)
    for key in (
        "name",
        "version",
        "description",
        "authors",
        "maintainers",
        "license",
        "license-files",
        "readme",
        "urls",
        "classifiers",
        "keywords",
    )
)
# Lint selections are sets in practice: a user's additions and Protostar's merge by
# membership instead of replacing one another. The producers' contributions are
# their complete declaration, so configuration a tool or template stops declaring
# is retracted, one [tool] table at a time. Seeds are the user's once written, and
# dependency-group includes have their own writer, so neither is retracted.
SPEC = TomlDocumentSpec(
    policy=MergePolicy(
        frozenset(
            {
                ("tool", "ruff", "lint", "select"),
                ("tool", "ruff", "lint", "extend-select"),
                ("tool", "ruff", "lint", "ignore"),
                ("tool", "ruff", "lint", "extend-ignore"),
                ("tool", "rumdl", "disable"),
            }
        ),
        complete=True,
        retained_paths=SEED_PATHS | {("dependency-groups",)},
        namespace_paths=frozenset({("tool",)}),
    ),
    seed_paths=SEED_PATHS,
    layout=TomlLayout(create=format_document, extend=place_new_sections),
)


def finalize_new_pyproject(
    content: str, on_fallback: Callable[[str], None] | None = None
) -> str:
    """Settles the layout of a pyproject.toml that Protostar created.

    The managed merge formats the file, but `uv add` then appends
    `[dependency-groups]` and the recipe is inserted after it, so the finished file
    needs one more pass. Never call this on a project the user already had.
    """
    import tomlkit

    return format_document(tomlkit.parse(content), on_fallback)


def declare_contribution(
    path: str, content: str, producer: str
) -> StructuredContribution:
    """Validates a TOML contribution and marks one that moves the resolver.

    Placeholder substitution is temporary and reversible: declaration must retain
    late-bound values for execution, rather than persisting dummy interpolation.

    Args:
        path: Workspace-relative POSIX path of the TOML document.
        content: TOML payload, possibly holding late-bound placeholders.
        producer: Stable producer identity.

    Returns:
        The contribution, with a resolver footprint when it sets this file's
        ``requires-python``.
    """
    variables = {v: f"PROTOSTAR_LATE_{v}" for v in extract_variables(content)}
    data = validate_configuration(render_template(content, variables))
    project_data = data.get("project")
    footprint = (
        ResolverFootprint()
        if path == TARGET
        and isinstance(project_data, dict)
        and "requires-python" in project_data
        else None
    )
    return StructuredContribution(producer, content, resolver_footprint=footprint)


def _parse_toml_document(original: str, *, action: str) -> tomlkit.TOMLDocument:
    import tomlkit
    import tomlkit.exceptions

    try:
        return tomlkit.parse(original)
    except tomlkit.exceptions.ParseError as e:
        raise ConfigurationError(
            "Invalid dependency configuration.",
            hint=f"Correct pyproject.toml before {action}.",
        ) from e


def _parse_toml_data(original: str, *, action: str) -> dict[str, object]:
    try:
        return tomllib.loads(original)
    except tomllib.TOMLDecodeError as e:
        raise ConfigurationError(
            "Invalid dependency configuration.",
            hint=f"Correct pyproject.toml before {action}.",
        ) from e


def remove_requirements(
    original: str, group: DependencyGroup, entries: Collection[str]
) -> str:
    """Returns the document without the given requirements in one group.

    Args:
        original: The pyproject.toml text.
        group: The group whose array lists the requirements.
        entries: The exact requirement strings to remove.

    Returns:
        The edited text, comments and layout otherwise intact.

    Raises:
        ConfigurationError: If the document or its dependency tables are invalid.
    """
    data = _parse_toml_data(original, action="removing requirements")
    table_key = "project" if group is DependencyGroup.MAIN else "dependency-groups"
    array_key = "dependencies" if group is DependencyGroup.MAIN else group.value
    raw_table = data.get(table_key)
    raw_array = raw_table.get(array_key) if isinstance(raw_table, dict) else None
    if not isinstance(raw_array, list) or not any(
        isinstance(item, str) and item in entries for item in raw_array
    ):
        return original

    import tomlkit
    import tomlkit.items

    doc = _parse_toml_document(original, action="removing requirements")
    table = doc.get(table_key, {})
    array = table.get(array_key)
    if not isinstance(array, tomlkit.items.Array):
        return original
    for index in reversed(range(len(array))):
        if isinstance(array[index], str) and str(array[index]) in entries:
            del array[index]
    return tomlkit.dumps(doc)


def apply_dependency_includes(original: str, edges: list[DependencyInclude]) -> str:
    """Returns an AST-preserving additive application of typed group includes."""
    data = _parse_toml_data(original, action="applying dependency includes")
    raw_groups = data.get("dependency-groups")
    if raw_groups is not None and not isinstance(raw_groups, dict):
        raise ConfigurationError(
            "dependency-groups must be a TOML table.",
            hint="Correct the dependency-groups table.",
        )
    needs_change = False
    if raw_groups is None:
        needs_change = True
    else:
        for edge in edges:
            if edge.group not in raw_groups or edge.include not in raw_groups:
                needs_change = True
            raw_entries = raw_groups.get(edge.group)
            raw_included = raw_groups.get(edge.include)
            if (raw_entries is not None and not isinstance(raw_entries, list)) or (
                raw_included is not None and not isinstance(raw_included, list)
            ):
                raise ConfigurationError(
                    "Dependency-group entries must be arrays.",
                    hint="Use requirement strings and include-group records inside each group array.",
                )
            if not isinstance(raw_entries, list) or not any(
                isinstance(e, dict) and e.get("include-group") == edge.include
                for e in raw_entries
            ):
                needs_change = True
    if not needs_change:
        return original

    import tomlkit
    import tomlkit.items

    doc = _parse_toml_document(original, action="applying dependency includes")
    groups = doc.get("dependency-groups")
    if groups is not None and not isinstance(groups, tomlkit.items.AbstractTable):
        raise ConfigurationError(
            "dependency-groups must be a TOML table.",
            hint="Correct the dependency-groups table.",
        )
    if groups is None:
        groups = tomlkit.table()
        if doc:
            doc.add(tomlkit.nl())
        doc["dependency-groups"] = groups
    changed = False
    for edge in edges:
        if edge.group not in groups:
            groups[edge.group] = tomlkit.array()
            changed = True
        if edge.include not in groups:
            groups[edge.include] = tomlkit.array()
            changed = True
        entries = groups[edge.group]
        if not isinstance(entries, tomlkit.items.Array) or not isinstance(
            groups[edge.include], tomlkit.items.Array
        ):
            raise ConfigurationError(
                "Dependency-group entries must be arrays.",
                hint="Use requirement strings and include-group records inside each group array.",
            )
        if not any(
            isinstance(e, dict) and e.get("include-group") == edge.include
            for e in entries
        ):
            item = tomlkit.parse(
                f'entry = {{ include-group = "{edge.include.value}" }}\n'
            )["entry"]
            entries.append(item)
            changed = True
    return tomlkit.dumps(doc) if changed else original
