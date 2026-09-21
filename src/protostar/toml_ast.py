"""AST-preserving TOML aggregation and spec-driven reconciliation."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

import tomlkit
import tomlkit.items
from tomlkit.items import AoT

from .errors import ConfigurationError
from .intent import StructuredContribution, validate_configuration
from .merge import (
    DEFAULT_POLICY,
    MISSING,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Value,
    overlay_declared,
    reconcile,
    semantic_equal,
)


@dataclass(frozen=True)
class TomlLayout:
    """How a document is laid out beyond tomlkit's own round-trip output.

    Each callable receives a fallback sink for notes on layout it declined to apply.

    Attributes:
        create: Formats a document Protostar is creating from the merged AST.
        extend: Places new sections of the merged AST into the original text.
    """

    create: Callable[[Any, Callable[[str], None]], str]
    extend: Callable[[str, Any, Callable[[str], None]], str]


@dataclass(frozen=True)
class TomlDocumentSpec:
    """How one TOML document merges beyond plain tables and atomic arrays.

    Attributes:
        policy: Kernel policy, including set-like arrays.
        super_tables: Paths of new tables emitted as super tables, so only their
            children get headers.
        layout: Document layout; ``None`` keeps tomlkit's round-trip output.
    """

    policy: MergePolicy = DEFAULT_POLICY
    super_tables: frozenset[tuple[str, ...]] = frozenset()
    layout: TomlLayout | None = None


DEFAULT_TOML_SPEC = TomlDocumentSpec()


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
    spec: TomlDocumentSpec,
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
    """Applies semantic decisions to the local AST, laid out by the document spec.

    Args:
        spec: Set-like arrays, super tables, and layout for this document.
        original: Current workspace text.
        desired: Aggregated desired value.
        base: Previously applied owned contributions, or ``MISSING``.
        location: File location carried into conflicts.
        overwrite: Whether explicit overwrite owns declared values.
        initializing: Whether Protostar is creating this document.
        missing_file: Whether the workspace file is absent.
        desired_ast: Desired AST whose styling is kept for accepted values.

    Returns:
        Emitted text, the composite owned baseline, conflicts, and layout notes.
    """
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
            spec.policy,
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
            elif (
                previous is MISSING
                and isinstance(value, dict)
                and path in spec.super_tables
            ):
                ast[key] = tomlkit.table(is_super_table=True)
                patch(ast[key], {}, value, path)
            elif (
                isinstance(previous, list)
                and isinstance(value, list)
                and path in spec.policy.set_like_paths
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
    elif spec.layout is not None and initializing:
        content = spec.layout.create(doc, layout_notes.append)
    elif spec.layout is not None:
        content = spec.layout.extend(original, doc, layout_notes.append)
    else:
        content = tomlkit.dumps(doc)
    return TomlReconciliation(content, baseline, conflicts, tuple(layout_notes))
