"""pyproject.toml policy: merge spec, layout, personal seeds, and group includes."""

from collections.abc import Callable

import tomlkit
import tomlkit.items

from ..errors import ConfigurationError
from ..intent import (
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
# Lint selections are sets in practice: a user's additions and Protostar's merge by
# membership instead of replacing one another.
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
        )
    ),
    super_tables=frozenset({("tool",)}),
    # Personal project metadata is filled in once; later edits are the user's.
    seed_paths=frozenset(
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
    ),
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


def apply_dependency_includes(original: str, edges: list[DependencyInclude]) -> str:
    """Returns an AST-preserving additive application of typed group includes."""
    try:
        doc = tomlkit.parse(original)
    except tomlkit.exceptions.ParseError as e:
        raise ConfigurationError(
            "Invalid dependency configuration.",
            hint="Correct pyproject.toml before applying dependency includes.",
        ) from e
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
