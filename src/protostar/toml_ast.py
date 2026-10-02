"""AST-preserving TOML aggregation and spec-driven reconciliation."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, cast

import tomlkit
import tomlkit.items
from tomlkit.container import Container, OutOfOrderTableProxy
from tomlkit.items import (
    AbstractTable,
    AoT,
    Comment,
    InlineTable,
    Item,
    Table,
    Whitespace,
)
from tomlkit.toml_document import TOMLDocument

from .errors import ConfigurationError
from .intent import StructuredContribution, validate_configuration
from .merge import (
    DEFAULT_POLICY,
    MISSING,
    NO_RESOLUTIONS,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Resolutions,
    StructuredReconciliation,
    Value,
    as_mapping,
    hold,
    lookup,
    overlay_declared,
    reconcile,
    semantic_equal,
    without_paths,
)


@dataclass(frozen=True)
class TomlLayout:
    """How a document is laid out beyond tomlkit's own round-trip output.

    Each callable receives a fallback sink for notes on layout it declined to apply.

    Attributes:
        create: Formats a document Protostar is creating from the merged AST.
        extend: Places new sections of the merged AST into the original text.
    """

    create: Callable[[TOMLDocument, Callable[[str], None]], str]
    extend: Callable[[str, TOMLDocument, Callable[[str], None]], str]


@dataclass(frozen=True)
class FlatNames:
    """A table whose keys are dotted names a tool also accepts nested.

    ``"a.b" = {}`` and ``a.b = {}`` are different TOML, but a tool that hoists the
    ``a`` table reads both as the name ``a.b``. Reconciliation compares such a
    table by name, so the two spellings never become two entries, and writes each
    name back in the spelling the document already uses.

    Attributes:
        path: The table holding the names.
        namespaces: Key paths, relative to the table, the tool hoists into dotted
            names. A nested spelling wins over a quoted one, as the tool reads it.
    """

    path: tuple[str, ...]
    namespaces: frozenset[tuple[str, ...]]


@dataclass(frozen=True)
class TomlDocumentSpec:
    """How one TOML document merges beyond plain tables and atomic arrays.

    Attributes:
        policy: Kernel policy, including set-like arrays.
        seed_paths: Paths written only while Protostar creates the document or
            explicit overwrite is selected, and never merged into an existing
            document. A written seed is owned, so deleting its table still reads as
            a deletion, but Protostar never updates it afterwards.
        root_table: Table that holds every setting Protostar declares, when the
            tool also accepts its settings at the top level. An existing document
            with settings but without this table is left alone, because adding the
            table would hide those settings from the tool.
        layout: Document layout; ``None`` keeps tomlkit's round-trip output.
        flat_names: Tables compared by dotted name, whichever way it is spelled.
    """

    policy: MergePolicy = DEFAULT_POLICY
    seed_paths: frozenset[tuple[str, ...]] = frozenset()
    root_table: str | None = None
    layout: TomlLayout | None = None
    flat_names: tuple[FlatNames, ...] = ()


DEFAULT_TOML_SPEC = TomlDocumentSpec()


@dataclass(frozen=True)
class AggregatedToml:
    """Semantic desired value paired with its comment-preserving TOML AST."""

    value: dict[str, Value]
    document: TOMLDocument


@dataclass(frozen=True)
class TomlReconciliation(StructuredReconciliation):
    """AST output, owned composite baseline, and concrete conflicts."""

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
                add_semantic(as_mapping(target[key]), value, producer, keys)

    def overlay_ast(
        target: AbstractTable | Container, incoming: AbstractTable | Container
    ) -> None:
        # None would read as False too.
        overlap_seen = False  # pragma: no mutate
        # None would read as False too.
        separator_added = False  # pragma: no mutate
        for key, value in incoming.items():
            existed = key in target
            current = target[key] if existed else None
            if isinstance(current, AbstractTable) and isinstance(value, AbstractTable):
                overlay_ast(current, value)
            else:
                if (
                    not existed
                    and overlap_seen
                    and not separator_added
                    and isinstance(target, AbstractTable)
                    and not isinstance(value, AbstractTable)
                ):
                    target.add(tomlkit.nl())
                    separator_added = True
                target[key] = deepcopy(value)
            overlap_seen = overlap_seen or existed

    for contribution in sorted(
        contributions, key=lambda item: item.producer.startswith("template:")
    ):
        data = as_mapping(validate_configuration(contribution.content))
        add_semantic(desired, data, contribution.producer)
        overlay_ast(desired_doc, tomlkit.parse(contribution.content))
    return AggregatedToml(desired, desired_doc)


def aggregate_toml(contributions: list[StructuredContribution]) -> dict[str, Value]:
    """Returns aggregated semantic intent for validation and pure callers."""
    return aggregate_toml_document(contributions).value


def _hold_seeds(
    desired: dict[str, Value], base: Value, paths: frozenset[tuple[str, ...]]
) -> dict[str, Value]:
    """Holds each written seed at its owned value and drops every other seed.

    A held seed reads as unchanged, so a seed the user edited or deleted never
    conflicts, and a changed seed default is never applied. A seed Protostar never
    wrote is dropped, so it is never merged into an existing document.

    Args:
        desired: Aggregated desired value.
        base: Owned baseline, or ``MISSING``.
        paths: The document's seed paths.

    Returns:
        A detached desired value.
    """
    owned = frozenset(path for path in paths if lookup(base, path) is not MISSING)
    held = without_paths(desired, paths - owned)
    for path in owned:
        hold(held, base, path)
    return held


def _spellings(
    table: dict[str, Value],
    namespaces: frozenset[tuple[str, ...]],
    prefix: tuple[str, ...] = (),
) -> dict[str, list[tuple[str, ...]]]:
    """Maps each name in a flat-names table to the key paths spelling it.

    A name spelled twice lists its quoted spelling first, so the last spelling
    is the nested one the tool reads.
    """
    spellings: dict[str, list[tuple[str, ...]]] = {}
    for key, member in table.items():
        path = (*prefix, key)
        if path in namespaces and isinstance(member, dict):
            for name, paths in _spellings(member, namespaces, path).items():
                spellings.setdefault(name, []).extend(paths)
        else:
            spellings.setdefault(".".join(path), []).insert(0, path)
    return spellings


def _member(table: dict[str, Value], path: tuple[str, ...]) -> Value:
    node: Value = table
    for key in path:
        node = as_mapping(node)[key]
    return node


def _flat(table: dict[str, Value], namespaces: frozenset[tuple[str, ...]]) -> Value:
    return {
        name: deepcopy(_member(table, paths[-1]))
        for name, paths in _spellings(table, namespaces).items()
    }


def _map_flat_names(
    value: Value,
    spec: TomlDocumentSpec,
    convert: Callable[[FlatNames, dict[str, Value]], Value],
) -> Value:
    # With nothing to map, the copy equals the value.
    if not spec.flat_names or not isinstance(value, dict):  # pragma: no mutate
        return value
    value = deepcopy(value)
    for names in spec.flat_names:
        *parents, leaf = names.path
        node: Value = value
        for key in parents:
            node = node.get(key) if isinstance(node, dict) else MISSING
        if isinstance(node, dict) and isinstance(node.get(leaf), dict):
            node[leaf] = convert(names, as_mapping(node[leaf]))
    return value


def flatten_names(value: Value, spec: TomlDocumentSpec) -> Value:
    """Rewrites each flat-names table to one key per dotted name.

    Args:
        value: A document value, or ``MISSING``.
        spec: The document spec naming its flat-names tables.

    Returns:
        A detached value whose flat-names tables are keyed by name.
    """
    return _map_flat_names(
        value, spec, lambda names, table: _flat(table, names.namespaces)
    )


def _nested_path(name: str, namespaces: frozenset[tuple[str, ...]]) -> tuple[str, ...]:
    """The nested spelling of a name, under its deepest namespace."""
    parts = tuple(name.split("."))
    depth = max(
        (
            len(ns)
            for ns in namespaces
            if parts[: len(ns)] == ns and len(parts) > len(ns)
        ),
        default=0,
    )
    if depth == 0:
        return (name,)
    return (*parts[:depth], ".".join(parts[depth:]))


def _inline(member: dict[str, Value]) -> Value:
    """An inline table spaced as TOML's own examples are, ``{ a = 1 }``."""
    table = tomlkit.inline_table()
    table.update(member)
    body = table.as_string()[1:-1]
    text = f"{{ {body} }}" if body else "{}"
    member = tomlkit.parse(f"member = {text}")["member"]
    # A cast is a no-op.
    return cast(Value, member)  # pragma: no mutate


def _inline_only(ast: Table | Container, key: str) -> bool:
    """Whether a table's member can hold only inline tables.

    A member spelled with dotted keys, ``key.a = 1``, or as an inline table,
    ``key = { a = 1 }``, cannot hold a table with its own header. A table spread
    over out-of-order headers is neither; its members cannot be told apart.
    """
    if isinstance(ast[key], InlineTable):
        return True
    container = ast if isinstance(ast, Container) else ast.value
    return any(
        k is not None and k.key == key and k.is_dotted() for k, _ in container.body
    )


def _place(table: dict[str, Value], path: tuple[str, ...], member: Value) -> None:
    for key in path[:-1]:
        table = as_mapping(table.setdefault(key, {}))
    table[path[-1]] = member


def _respell(
    flat: dict[str, Value],
    local: dict[str, Value],
    desired: dict[str, Value],
    namespaces: frozenset[tuple[str, ...]],
    inline: set[tuple[str, ...]],
) -> dict[str, Value]:
    """Spells each name of a flat-names table the way the document does.

    A name the document has keeps its spellings: the one the tool reads takes the
    new value, a shadowed quoted one stays as it is. A new name follows its
    namespace's spelling in the document, else the desired spelling. A new
    quoted table is added to ``inline``, to be written on one line.
    """
    local_spellings = _spellings(local, namespaces)
    desired_spellings = _spellings(desired, namespaces)

    def nests(root: str) -> bool:
        # The document's spelling of the namespace, else the desired one.
        for spellings in (local_spellings, desired_spellings):
            for paths in spellings.values():
                for path in paths:
                    if len(path) > 1 and path[0] == root:
                        return True
                    if len(path) == 1 and path[0].startswith(f"{root}."):
                        return False
        return True

    result: dict[str, Value] = {}
    for name, member in flat.items():
        paths = local_spellings.get(name)
        if paths:
            for path in paths[:-1]:
                _place(result, path, deepcopy(_member(local, path)))
            _place(result, paths[-1], member)
            continue
        nested = _nested_path(name, namespaces)
        if nests(nested[0]):
            _place(result, nested, member)
        else:
            if isinstance(member, dict):
                inline.add((name,))
            _place(result, (name,), member)
    return result


def respell_names(
    value: Value,
    local: Value,
    desired: Value,
    spec: TomlDocumentSpec,
    inline: set[tuple[str, ...]] | None = None,
) -> Value:
    """Rewrites each flat-names table from names back to the document's keys.

    Args:
        value: A reconciled value whose flat-names tables are keyed by name.
        local: The document's own value, in its own spelling.
        desired: The desired value, in the producers' spelling.
        spec: The document spec naming its flat-names tables.
        inline: Collects the paths of new quoted tables, which read best on one
            line as the document's own quoted names do.

    Returns:
        A detached value spelled as the document spells it.
    """
    collected: set[tuple[str, ...]] = set()

    def respell(names: FlatNames, table: dict[str, Value]) -> Value:
        found: set[tuple[str, ...]] = set()
        spelled = _respell(
            table,
            table_at(local, names.path),
            table_at(desired, names.path),
            names.namespaces,
            found,
        )
        collected.update((*names.path, *path) for path in found)
        return spelled

    def table_at(source: Value, path: tuple[str, ...]) -> dict[str, Value]:
        node = lookup(source, path)
        return node if isinstance(node, dict) else {}

    spelled = _map_flat_names(value, spec, respell)
    if inline is not None:
        inline.update(collected)
    return spelled


def _trailing_comments(table: Table) -> int | None:
    """Returns where a table's closing comment block starts, if it has one.

    tomlkit keeps the comments and blank lines between a table's last value and
    the next header in the table's own body, so a header comment such as
    ``# ---- Mypy ---- #`` reads as the end of the table before it.
    """
    body = table.value.body
    start = len(body)
    while start and body[start - 1][0] is None:
        if not isinstance(body[start - 1][1], (Comment, Whitespace)):
            break
        start -= 1
    if any(isinstance(item, Comment) for _, item in body[start:]):
        return start
    return None


def _above_trailing_comments(table: Table, key: str, start: int) -> None:
    """Moves a value just added to a table above its closing comment block.

    Otherwise the value lands below a comment that introduces the next
    section, and the document's layout reads it as that section's.
    """
    # The value was just appended below the block, so it is always found there;
    # a table, or a dotted key's table, keeps its own place.
    item = next(item for k, item in table.value.body if k is not None and k.key == key)
    if isinstance(item, (Table, AoT)):
        return
    table.value.remove(key)
    # tomlkit has no public way to add a key at a position.
    table.value._insert_at(start, key, item)


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
    desired_ast: TOMLDocument | None = None,
    resolutions: Resolutions = NO_RESOLUTIONS,
    proposing: bool = False,
) -> TomlReconciliation:
    """Applies semantic decisions to the local AST, laid out by the document spec.

    Args:
        spec: Set-like arrays, seed paths, and layout for this document.
        original: Current workspace text.
        desired: Aggregated desired value.
        base: Previously applied owned contributions, or ``MISSING``.
        location: File location carried into conflicts.
        overwrite: Whether explicit overwrite owns declared values.
        initializing: Whether Protostar is creating this document.
        missing_file: Whether the workspace file is absent.
        desired_ast: Desired AST whose styling is kept for accepted values.
        resolutions: Choices settling conflicts, keyed by conflict identity.
        proposing: Whether the document existed before Protostar owned any of
            it, so each change into it is a proposal.

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
    raw_local = as_mapping(doc.unwrap())
    raw_desired = desired
    local = as_mapping(flatten_names(raw_local, spec))
    desired = as_mapping(flatten_names(desired, spec))
    base = flatten_names(base, spec)
    if overwrite or initializing:
        # Explicit target authorization owns declared leaves, never foreign siblings.
        baseline: Value = deepcopy(base) if isinstance(base, dict) else {}

        value = deepcopy(local)
        overlay_declared(value, desired)
        overlay_declared(as_mapping(baseline), desired)
        conflicts: tuple[MergeConflict, ...] = ()
        resolved: tuple[MergeConflict, ...] = ()
        proposals: tuple[MergeConflict, ...] = ()
        preserved: tuple[MergeConflict, ...] = ()
    else:
        result = reconcile(
            base,
            MISSING if missing_file else local,
            _hold_seeds(desired, base, spec.seed_paths),
            location,
            replace(spec.policy, proposing=proposing),
            resolutions,
        )
        if result.value is MISSING:
            return TomlReconciliation(
                original,
                respell_names(result.baseline, MISSING, raw_desired, spec),
                result.conflicts,
                resolved=result.resolved,
                proposals=result.proposals,
                preserved=result.preserved,
            )
        value = as_mapping(result.value)
        baseline = result.baseline
        conflicts = result.conflicts
        resolved = result.resolved
        proposals = result.proposals
        preserved = result.preserved

    def desired_node(keys: tuple[str, ...]) -> Item | Container | None:
        node: Any = desired_ast
        if node is None:
            return None
        try:
            for key in keys:
                node = node[key]
        except (KeyError, TypeError):
            return None
        found: Item | Container | None = node
        return found

    def place_styled(
        ast: Table | Container,
        keys: tuple[str, ...],
        key: str,
        styled: Item | Container | OutOfOrderTableProxy,
        value: Value,
    ) -> None:
        if not isinstance(styled, OutOfOrderTableProxy):
            ast[key] = deepcopy(styled)
            return
        # Dotted keys (`a.b = 1` beside `a.c = 2`) spread one table over
        # several entries of its parent, which tomlkit reads back as a proxy
        # that cannot be copied. Carry the entries over one by one instead.
        parent = desired_node(keys)
        if isinstance(parent, Table):
            parent = parent.value
        # A proxy's parent is always a container.
        body = parent.body if isinstance(parent, Container) else []  # pragma: no mutate
        entries = [(k, item) for k, item in body if k is not None and k.key == key]
        if all(k.is_dotted() for k, _ in entries):
            if key in ast:
                del ast[key]
            for k, item in entries:
                ast.append(deepcopy(k), deepcopy(item))
        else:
            ast[key] = tomlkit.item(value)

    def patch(
        ast: Table | Container,
        before: dict[str, Value],
        after: dict[str, Value],
        keys: tuple[str, ...] = (),
        inline_only: bool = False,
    ) -> None:
        # A complete policy retracts owned keys the producers stop declaring.
        for key in [key for key in before if key not in after]:
            del ast[key]
        closing = _trailing_comments(ast) if isinstance(ast, Table) else None
        for key, value in after.items():
            previous = before.get(key)
            if semantic_equal(previous, value):
                continue
            added = closing is not None and key not in ast
            path = (*keys, key)
            styled = desired_node(path)
            # TOML has no null, so None never equals a value either.
            styled_value: Value = MISSING  # pragma: no mutate
            if styled is not None and hasattr(styled, "unwrap"):
                styled_value = styled.unwrap()
            if isinstance(previous, dict) and isinstance(value, dict):
                held_inline = inline_only or _inline_only(ast, key)
                patch(ast[key], previous, value, path, held_inline)
            elif (
                (inline_only or path in inline)
                and isinstance(value, dict)
                and not (
                    isinstance(styled, InlineTable)
                    and semantic_equal(styled_value, value)
                )
            ):
                # tomlkit writes a table set inside a dotted-key table under a
                # wrong top-level header, and an inline table cannot hold one;
                # either holds an inline table.
                # A new quoted name sits on one line, as the document's do.
                ast[key] = _inline(value)
            elif (
                isinstance(previous, list)
                and isinstance(value, list)
                and path in spec.policy.set_like_paths
                and value[: len(previous)] == previous
            ):
                # Preserve local member trivia before considering desired AST replacement.
                for member in value[len(previous) :]:
                    ast[key].append(tomlkit.item(member))
            # A value written here is the desired one.
            elif styled is not None and semantic_equal(
                styled_value, value
            ):  # pragma: no mutate
                place_styled(ast, keys, key, styled, value)
            else:
                ast[key] = tomlkit.item(value)
            if added and closing is not None and isinstance(ast, Table):
                _above_trailing_comments(ast, key, closing)
                closing += 1

    # The baseline is compared by name too, but kept in the document's spelling
    # so a lockfile never changes for a spelling alone.
    inline: set[tuple[str, ...]] = set()
    value = as_mapping(
        respell_names(value, raw_local, raw_desired, spec, inline),
    )
    baseline = respell_names(baseline, raw_local, raw_desired, spec)
    patch(doc, raw_local, value)
    layout_notes: list[str] = []
    # tomlkit round-trips an unchanged document.
    if semantic_equal(raw_local, value):  # pragma: no mutate
        content = original
    elif spec.layout is not None and initializing:
        content = spec.layout.create(doc, layout_notes.append)
    elif spec.layout is not None:
        content = spec.layout.extend(original, doc, layout_notes.append)
    else:
        # A copied desired table keeps the blank line that separated it from its
        # next sibling; the document keeps its own ending instead.
        ending = original[len(original.rstrip("\r\n")) :] if original else "\n"
        content = tomlkit.dumps(doc).rstrip("\r\n") + ending
    return TomlReconciliation(
        content,
        baseline,
        conflicts,
        resolved=resolved,
        proposals=proposals,
        preserved=preserved,
        layout_notes=tuple(layout_notes),
    )
