"""AST-preserving TOML merging, manipulation, and formatting."""

import logging
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

import tomlkit
import tomlkit.items
from tomlkit.items import AoT

from .errors import ConfigurationError
from .intent import (
    ContributionPolicy,
    DependencyInclude,
    ResolverFootprint,
    StructuredContribution,
    validate_configuration,
)
from .interpolation import extract_variables, render_template
from .merge import (
    MISSING,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Value,
    overlay_declared,
    reconcile,
    semantic_equal,
)
from .toml_layout import format_document, place_new_sections

logger = logging.getLogger("protostar")

SET_LIKE_TOML_PATHS = frozenset(
    {
        ("tool", "ruff", "lint", "select"),
        ("tool", "ruff", "lint", "extend-select"),
        ("tool", "ruff", "lint", "ignore"),
        ("tool", "ruff", "lint", "extend-ignore"),
        ("tool", "rumdl", "disable"),
        ("project", "classifiers"),
    }
)


@dataclass(frozen=True)
class AggregatedToml:
    """Semantic desired value paired with its comment-preserving TOML AST."""

    value: dict[str, Value]
    document: Any


@dataclass(frozen=True)
class TomlReconciliation:
    """AST output, owned composite baseline, and concrete conflicts."""

    content: str
    baseline: Value
    conflicts: tuple[MergeConflict, ...]
    layout_notes: tuple[str, ...] = ()


def aggregate_toml_document(
    contributions: list[StructuredContribution],
) -> AggregatedToml:
    """Aggregates semantic precedence and the corresponding desired TOML AST."""
    desired: dict[str, Value] = {}
    desired_doc = tomlkit.document()
    owners: dict[tuple[str, ...], str] = {}

    def add_semantic(
        target: dict[str, Value],
        incoming: dict[str, Value],
        producer: str,
        path: tuple[str, ...] = (),
    ) -> None:
        for key, value in incoming.items():
            keys = (*path, key)
            current = target.get(key, MISSING)
            if isinstance(value, dict) and isinstance(current, dict):
                add_semantic(current, value, producer, keys)
                continue
            old = owners.get(keys)
            if (
                current is not MISSING
                and not semantic_equal(current, value)
                and old != producer
                and not (
                    producer.startswith("template:")
                    or (
                        producer.startswith("module:")
                        and old is not None
                        and old.startswith("module:")
                    )
                )
            ):
                raise ConfigurationError(
                    f"Ambiguous TOML producers at {'.'.join(keys)}.",
                    hint="Use documented module sequence/template precedence or remove conflicting declarations.",
                )
            target[key] = deepcopy(value)
            owners[keys] = producer
            if isinstance(value, dict):
                target[key] = {}
                add_semantic(cast(dict[str, Value], target[key]), value, producer, keys)

    def overlay_ast(target: Any, incoming: Any) -> None:
        overlap_seen = False
        separator_added = False
        for key, value in incoming.items():
            existed = key in target
            if (
                existed
                and isinstance(target[key], tomlkit.items.AbstractTable)
                and isinstance(value, tomlkit.items.AbstractTable)
                and not isinstance(target[key], AoT)
                and not isinstance(value, AoT)
            ):
                overlay_ast(target[key], value)
            else:
                if (
                    not existed
                    and overlap_seen
                    and not separator_added
                    and isinstance(target, tomlkit.items.AbstractTable)
                    and not isinstance(value, tomlkit.items.AbstractTable)
                ):
                    target.add(tomlkit.nl())
                    separator_added = True
                target[key] = deepcopy(value)
            overlap_seen = overlap_seen or existed

    for contribution in sorted(
        contributions, key=lambda item: item.producer.startswith("template:")
    ):
        data = cast(dict[str, Value], validate_configuration(contribution.content))
        add_semantic(desired, data, contribution.producer)
        overlay_ast(desired_doc, tomlkit.parse(contribution.content))
    return AggregatedToml(desired, desired_doc)


def aggregate_toml(contributions: list[StructuredContribution]) -> dict[str, Value]:
    """Returns aggregated semantic intent for validation and pure callers."""
    return aggregate_toml_document(contributions).value


def reconcile_toml(
    original: str,
    desired: dict[str, Value],
    base: Value,
    location: MergeLocation,
    *,
    overwrite: bool = False,
    initializing: bool = False,
    missing_file: bool = False,
    desired_ast: Any | None = None,
) -> TomlReconciliation:
    """Applies semantic decisions to the local AST without global formatting."""
    try:
        doc = tomlkit.parse(original)
    except tomlkit.exceptions.TOMLKitError as e:
        raise ConfigurationError(
            "Invalid structured TOML file.",
            hint="Correct the target TOML syntax before retrying.",
        ) from e
    local = cast(dict[str, Value], doc.unwrap())
    if overwrite or initializing:
        # Explicit target authorization owns declared leaves, never foreign siblings.
        baseline: Value = deepcopy(base) if isinstance(base, dict) else {}

        value = deepcopy(local)
        overlay_declared(value, desired)
        overlay_declared(cast(dict[str, Value], baseline), desired)
        conflicts: tuple[MergeConflict, ...] = ()
    else:
        result = reconcile(
            base,
            MISSING if missing_file else local,
            desired,
            location,
            MergePolicy(SET_LIKE_TOML_PATHS),
        )
        if result.value is MISSING:
            return TomlReconciliation(original, result.baseline, result.conflicts)
        value = cast(dict[str, Value], result.value)
        baseline = result.baseline
        conflicts = result.conflicts

    def desired_node(keys: tuple[str, ...]) -> Any | None:
        node = desired_ast
        if node is None:
            return None
        try:
            for key in keys:
                node = node[key]
        except (KeyError, TypeError):
            return None
        return node

    def patch(
        ast: Any,
        before: dict[str, Value],
        after: dict[str, Value],
        keys: tuple[str, ...] = (),
    ) -> None:
        for key, value in after.items():
            previous = before.get(key, MISSING)
            if semantic_equal(previous, value):
                continue
            path = (*keys, key)
            styled = desired_node(path)
            styled_value: Value = MISSING
            if styled is not None and hasattr(styled, "unwrap"):
                styled_value = cast(Value, styled.unwrap())
            if isinstance(previous, dict) and isinstance(value, dict):
                patch(ast[key], previous, value, path)
            elif previous is MISSING and isinstance(value, dict) and path == ("tool",):
                ast[key] = tomlkit.table(is_super_table=True)
                patch(ast[key], {}, value, path)
            elif (
                isinstance(previous, list)
                and isinstance(value, list)
                and path in SET_LIKE_TOML_PATHS
                and value[: len(previous)] == previous
            ):
                # Preserve local member trivia before considering desired AST replacement.
                for member in value[len(previous) :]:
                    ast[key].append(tomlkit.item(member))
            elif styled is not None and semantic_equal(styled_value, value):
                ast[key] = deepcopy(styled)
            else:
                ast[key] = tomlkit.item(value)

    patch(doc, local, value)
    layout_notes: list[str] = []
    if semantic_equal(local, value):
        content = original
    elif location.file == "pyproject.toml" and initializing:
        content = format_pyproject_toml(doc, layout_notes.append)
    elif location.file == "pyproject.toml":
        content = place_new_sections(original, doc, layout_notes.append)
    else:
        content = tomlkit.dumps(doc)
    return TomlReconciliation(content, baseline, conflicts, tuple(layout_notes))


def format_pyproject_toml(
    doc: Any, on_fallback: Callable[[str], None] | None = None
) -> str:
    """Formats a pyproject.toml document into the canonical Protostar layout."""
    return format_document(doc, on_fallback)


def finalize_new_pyproject(
    content: str, on_fallback: Callable[[str], None] | None = None
) -> str:
    """Settles the layout of a pyproject.toml that Protostar created.

    The managed merge formats the file, but `uv add` then appends
    `[dependency-groups]` and the recipe is inserted after it, so the finished file
    needs one more pass. Never call this on a project the user already had.
    """
    return format_pyproject_toml(tomlkit.parse(content), on_fallback)


def declare_structured_contributions(
    path: str, content: str, producer: str, policy: ContributionPolicy
) -> tuple[StructuredContribution, ...]:
    """Separates personal pyproject seeds from managed tooling/build intent.

    Placeholder substitution is temporary and reversible: declaration must retain
    late-bound values for execution, rather than persisting dummy interpolation.
    """
    variables = {v: f"PROTOSTAR_LATE_{v}" for v in extract_variables(content)}
    data = validate_configuration(render_template(content, variables))
    project_data = data.get("project")
    footprint = (
        ResolverFootprint()
        if path == "pyproject.toml"
        and isinstance(project_data, dict)
        and "requires-python" in project_data
        else None
    )
    personal = {
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
    }
    if (
        path != "pyproject.toml"
        or policy != ContributionPolicy.MANAGED
        or not isinstance(project_data, dict)
        or not personal.intersection(project_data)
    ):
        return (StructuredContribution(producer, content, policy, footprint),)
    doc = tomlkit.parse(render_template(content, variables))
    project = doc["project"]
    seed = tomlkit.document()
    seed_project = tomlkit.table()
    for key in list(project):
        if key in personal:
            seed_project[key] = project.pop(key)
    seed["project"] = seed_project
    if not project:
        del doc["project"]

    def restore(text: str) -> str:
        for variable, token in variables.items():
            text = text.replace(token, f"<% {variable} %>")
        return text

    result = [
        StructuredContribution(
            producer, restore(tomlkit.dumps(seed)), ContributionPolicy.SEED_ONLY
        )
    ]
    if doc:
        result.append(
            StructuredContribution(
                producer, restore(tomlkit.dumps(doc)), policy, footprint
            )
        )
    return tuple(result)


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
