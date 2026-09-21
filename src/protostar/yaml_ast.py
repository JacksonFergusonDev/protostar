"""Bounded YAML 1.2 round-trip codec and spec-driven reconciliation adapter."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from itertools import pairwise
from types import MappingProxyType
from typing import Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from ruamel.yaml.scalarstring import ScalarString

from .errors import ConfigurationError
from .merge import (
    DEFAULT_POLICY,
    MISSING,
    ConflictReason,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Value,
    overlay_declared,
    prune_unapplied,
    reconcile,
    semantic_equal,
    validate_value,
)

_MAX_NODES = 10000
_MAX_BYTES = 1_000_000
_TAGS = {"map", "seq", "str", "null", "bool", "int", "float", "merge"}
# The emitter folds plain scalars past its width, so a merge would rewrap every
# long line in the file (leaving trailing spaces) rather than only the edited ones.
_UNBOUNDED_WIDTH = 1 << 31
_BLOCK_KEY = re.compile(r"^(?P<indent> *)(?P<dash>(?:- +)*)[^\s#-][^#]*:\s*(?:#.*)?$")
_SEQUENCE_ITEM = re.compile(r"^(?P<indent> *)-(?P<gap> +)\S")


@dataclass(frozen=True)
class YamlStyle:
    """Block indentation, in ruamel terms, that an emitted document follows.

    Attributes:
        mapping: Indent of a nested mapping relative to its parent key.
        sequence: Indent of sequence item content relative to its parent key.
        offset: Indent of the ``-`` indicator relative to its parent key.
    """

    mapping: int = 2
    sequence: int = 4
    offset: int = 2


DEFAULT_STYLE = YamlStyle()


def detect_style(content: str) -> YamlStyle:
    """Infers block indentation from the first nested mapping and sequence.

    The emitter applies one style to the whole document, so a merged file keeps
    its own indentation (including indentless sequences) instead of being
    re-indented wholesale. Mixed styles within one file follow the first match.

    Args:
        content: YAML document text.

    Returns:
        The detected style, with defaults for anything the document never shows.
    """
    mapping: int | None = None
    sequence: tuple[int, int] | None = None
    lines = [
        line
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for parent, child in pairwise(lines):
        key = _BLOCK_KEY.match(parent)
        if key is None:
            continue
        column = len(key["indent"]) + len(key["dash"])
        item = _SEQUENCE_ITEM.match(child)
        if item is not None:
            offset = len(item["indent"]) - column
            content_indent = offset + 1 + len(item["gap"])
            if sequence is None and offset >= 0:
                sequence = (content_indent, offset)
        elif mapping is None:
            indent = len(child) - len(child.lstrip(" ")) - column
            if indent > 0:
                mapping = indent
        if mapping is not None and sequence is not None:
            break
    mapping = mapping or DEFAULT_STYLE.mapping
    if sequence is None:
        # Keep the default dash placement relative to whatever mapping indent was found.
        sequence = (mapping + 2, mapping)
    if sequence[0] - sequence[1] < 2:
        return YamlStyle(mapping, DEFAULT_STYLE.sequence, DEFAULT_STYLE.offset)
    return YamlStyle(mapping, *sequence)


def _invalid() -> ConfigurationError:
    return ConfigurationError(
        "Invalid or unsupported YAML configuration.",
        hint="Use one YAML 1.2 mapping with unique string keys, standard JSON-like values, no cyclic aliases, and at most 100 levels/10000 nodes/1 MB.",
    )


def _codec(style: YamlStyle = DEFAULT_STYLE) -> YAML:
    codec = YAML(typ="rt", pure=True)
    codec.preserve_quotes = True
    codec.allow_duplicate_keys = False
    codec.width = _UNBOUNDED_WIDTH
    codec.indent(mapping=style.mapping, sequence=style.sequence, offset=style.offset)
    return codec


def _load(content: str) -> Any:
    if len(content.encode("utf-8")) > _MAX_BYTES:
        raise _invalid()
    try:
        codec = _codec()
        root = codec.compose(content)
        if codec.doc_infos and codec.doc_infos[-1].doc_version is not None:
            version = codec.doc_infos[-1].doc_version
            if (version.major, version.minor) != (1, 2):
                raise _invalid()
        if not isinstance(root, MappingNode):
            raise _invalid()
        active: set[int] = set()
        count = 0

        def visit(node: Node, depth: int) -> None:
            nonlocal count
            count += 1
            if count > _MAX_NODES or depth > 100 or id(node) in active:
                raise _invalid()
            if node.tag not in {f"tag:yaml.org,2002:{tag}" for tag in _TAGS}:
                raise _invalid()
            active.add(id(node))
            if isinstance(node, MappingNode):
                for key, value in node.value:
                    if not isinstance(key, ScalarNode) or key.tag not in (
                        "tag:yaml.org,2002:str",
                        "tag:yaml.org,2002:merge",
                    ):
                        raise _invalid()
                    visit(key, depth + 1)
                    visit(value, depth + 1)
            elif isinstance(node, SequenceNode):
                for child in node.value:
                    visit(child, depth + 1)
            active.remove(id(node))

        visit(root, 0)
        return _codec().load(content)
    except (YAMLError, ValueError, TypeError, RecursionError) as error:
        raise _invalid() from error


def _plain(node: Any) -> Value:
    if isinstance(node, dict):
        return {str(key): _plain(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_plain(value) for value in node]
    if node is None:
        return None
    if isinstance(node, bool):
        return bool(node)
    if isinstance(node, str):
        return str(node)
    if isinstance(node, int):
        # Anchored booleans are ScalarBoolean (an int subclass).
        from ruamel.yaml.scalarbool import ScalarBoolean

        return bool(node) if isinstance(node, ScalarBoolean) else int(node)
    if isinstance(node, float):
        return float(node)
    raise _invalid()


def decode_yaml_baseline(content: str) -> dict[str, Value]:
    """Decodes a bounded YAML mapping into detached, type-aware semantic values."""
    value = cast(dict[str, Value], _plain(_load(content)))
    validate_value(value)
    return value


def encode_yaml_baseline(value: dict[str, Value]) -> str:
    """Encodes owned values deterministically without local comments or aliases."""
    validate_value(value)

    def ordered(node: Value) -> Value:
        if isinstance(node, dict):
            return {key: ordered(node[key]) for key in sorted(node)}
        if isinstance(node, list):
            return [ordered(child) for child in node]
        return node

    stream = StringIO()
    try:
        _codec().dump(ordered(value), stream)
    except (YAMLError, ValueError, TypeError, RecursionError) as error:
        raise _invalid() from error
    content = stream.getvalue()
    decode_yaml_baseline(content)
    return content


@dataclass(frozen=True)
class YamlReconciliation:
    """Round-trip output, owned composite baseline, and structured conflicts."""

    content: str
    baseline: Value
    conflicts: tuple[MergeConflict, ...]


class Wildcard(Enum):
    """Sentinel for a keyed-sequence path segment that matches any key."""

    ANY = "*"


WILDCARD = Wildcard.ANY
type PathPattern = tuple[str | Wildcard, ...]


@dataclass(frozen=True)
class KeyedSequence:
    """A sequence of mapping records merged by identity instead of by position.

    Attributes:
        path: Keyed-view path of the sequence. Enclosing keyed records appear as
            their identity, so ``WILDCARD`` matches a record identity or any key.
        identity: Field whose non-empty string value identifies a record.
        string_fields: Fields that must be non-empty strings when present.
    """

    path: PathPattern
    identity: str
    string_fields: tuple[str, ...] = ()

    def matches(self, path: tuple[str, ...]) -> bool:
        """Reports whether a concrete keyed-view path names this sequence."""
        return len(path) == len(self.path) and all(
            pattern is WILDCARD or pattern == key
            for pattern, key in zip(self.path, path, strict=True)
        )


@dataclass(frozen=True)
class YamlDocumentSpec:
    """How one YAML document merges beyond plain mappings and atomic sequences.

    Attributes:
        name: Human-readable document name used in domain errors.
        keyed: Sequences whose records merge by identity.
        policy: Kernel policy, including set-like scalar sequences.
    """

    name: str
    keyed: tuple[KeyedSequence, ...] = ()
    policy: MergePolicy = DEFAULT_POLICY

    def sequence_at(self, path: tuple[str, ...]) -> KeyedSequence | None:
        """Returns the keyed sequence declared at a concrete keyed-view path."""
        return next((s for s in self.keyed if s.matches(path)), None)


CODECOV_TARGET = ".github/codecov.yml"
PRE_COMMIT_TARGET = ".pre-commit-config.yaml"
CODECOV_SPEC = YamlDocumentSpec("Codecov", policy=MergePolicy(frozenset({("ignore",)})))
PRE_COMMIT_SPEC = YamlDocumentSpec(
    "pre-commit",
    keyed=(
        KeyedSequence(("repos",), "repo", string_fields=("rev",)),
        KeyedSequence(("repos", WILDCARD, "hooks"), "id"),
    ),
)
YAML_DOCUMENTS: Mapping[str, YamlDocumentSpec] = MappingProxyType(
    {CODECOV_TARGET: CODECOV_SPEC, PRE_COMMIT_TARGET: PRE_COMMIT_SPEC}
)


def reconcile_yaml(
    spec: YamlDocumentSpec,
    original: str,
    desired: str,
    base: Value,
    location: MergeLocation,
    *,
    holds: tuple[tuple[str, ...], ...] = (),
    missing_file: bool = False,
    overwrite: bool = False,
) -> YamlReconciliation:
    """Reconciles a YAML document under its spec without owning foreign content.

    Args:
        spec: Keyed sequences and kernel policy for this document.
        original: Current workspace text; ignored when ``missing_file`` is set.
        desired: Desired contribution text.
        base: Previously applied owned contributions, or ``MISSING``.
        location: File location carried into conflicts.
        holds: Keyed-view paths whose desired value is replaced by the owned
            baseline (or dropped when unowned), so local content and previous
            ownership are kept there without a conflict of their own.
        missing_file: Whether the workspace file is absent.
        overwrite: Whether explicit overwrite owns declared values.

    Returns:
        Emitted text, the composite owned baseline, and structured conflicts.
    """
    return _reconcile_yaml(
        spec,
        original,
        desired,
        base,
        location,
        holds=holds,
        missing_file=missing_file,
        overwrite=overwrite,
    )


def validate_yaml_baseline(spec: YamlDocumentSpec, value: Value) -> None:
    """Validates identities and fields of desired or owned snapshots strictly."""
    _keyed(spec, value, strict=True)


def _identified(record: Any, sequence: KeyedSequence) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(record.get(sequence.identity), str)
        and bool(record[sequence.identity])
    )


def _keyed(
    spec: YamlDocumentSpec,
    value: Value,
    path: tuple[str, ...] = (),
    *,
    strict: bool = False,
) -> Value:
    """Presents keyed sequences as mappings from identity to record.

    Duplicate local identities map to the list of their records, which marks them
    ambiguous. Local records without an identity are foreign: they are left out of
    the keyed view and stay in place in the round-trip AST. Desired and owned
    snapshots (``strict``) must identify every record exactly once.
    """
    sequence = spec.sequence_at(path)
    if sequence is not None:
        if not isinstance(value, list):
            raise ConfigurationError(
                f"Invalid {spec.name} record sequence.",
                hint=f"Use a list of mappings with non-empty '{sequence.identity}' strings.",
            )
        grouped: dict[str, list[Value]] = {}
        for record in value:
            if not _identified(record, sequence):
                if strict:
                    raise ConfigurationError(
                        f"Invalid {spec.name} identity.",
                        hint=f"Give every record a non-empty '{sequence.identity}' string.",
                    )
                continue
            record = cast(dict[str, Value], record)
            for field in sequence.string_fields:
                if field in record and (
                    not isinstance(record[field], str) or not record[field]
                ):
                    raise ConfigurationError(
                        f"Invalid {spec.name} field '{field}'.",
                        hint=f"Quote '{field}' values as non-empty strings.",
                    )
            grouped.setdefault(cast(str, record[sequence.identity]), []).append(record)
        records: dict[str, Value] = {}
        for name, members in grouped.items():
            if len(members) > 1:
                if strict:
                    raise ConfigurationError(
                        f"Duplicate desired or owned {spec.name} identity.",
                        hint=f"Declare each '{sequence.identity}' once.",
                    )
                records[name] = deepcopy(members)
            else:
                record = cast(dict[str, Value], members[0])
                records[name] = _keyed(
                    spec,
                    {k: v for k, v in record.items() if k != sequence.identity},
                    (*path, name),
                    strict=strict,
                )
        return records
    if isinstance(value, dict):
        return {k: _keyed(spec, v, (*path, k), strict=strict) for k, v in value.items()}
    return deepcopy(value)


def _unkeyed(spec: YamlDocumentSpec, value: Value, path: tuple[str, ...] = ()) -> Value:
    if isinstance(value, dict):
        sequence = spec.sequence_at(path)
        if sequence is not None:
            records: list[Value] = []
            for name, record in value.items():
                if isinstance(record, list):
                    records.extend(deepcopy(record))
                else:
                    records.append(
                        {
                            sequence.identity: name,
                            **cast(
                                dict[str, Value],
                                _unkeyed(spec, record, (*path, name)),
                            ),
                        }
                    )
            return records
        return {k: _unkeyed(spec, v, (*path, k)) for k, v in value.items()}
    return deepcopy(value)


def _ambiguous(
    spec: YamlDocumentSpec, value: Value, path: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    """Finds the entries to hold because a keyed sequence repeats an identity.

    A duplicate inside a nested sequence holds the entry that contains the
    sequence (for example the repository owning duplicate hooks); a duplicate in
    a top-level sequence holds only the repeated identity.
    """
    found: list[tuple[str, ...]] = []
    if not isinstance(value, dict):
        return found
    keyed = spec.sequence_at(path) is not None
    for key, child in value.items():
        if keyed and isinstance(child, list):
            held = path[:-1] if len(path) > 1 else (*path, key)
            if held not in found:
                found.append(held)
        else:
            found.extend(
                held
                for held in _ambiguous(spec, child, (*path, key))
                if held not in found
            )
    return found


def _lookup(value: Value, path: tuple[str, ...]) -> Value:
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def _hold(remote: dict[str, Value], base: Value, path: tuple[str, ...]) -> None:
    """Replaces the desired value at ``path`` by its baseline, or drops it."""
    parent = _lookup(remote, path[:-1])
    if not isinstance(parent, dict):
        return
    prior = _lookup(base, path)
    if prior is MISSING:
        parent.pop(path[-1], None)
    else:
        parent[path[-1]] = deepcopy(prior)


def _omit(remote: dict[str, Value], path: tuple[str, ...]) -> None:
    parent = _lookup(remote, path[:-1])
    if isinstance(parent, dict):
        parent.pop(path[-1], None)


def _insertion_index(
    node: list[Any], sequence: KeyedSequence, order: list[str], name: str
) -> int:
    """Places a new record after its nearest earlier desired sibling present."""
    present = {
        str(record[sequence.identity]): index
        for index, record in enumerate(node)
        if _identified(record, sequence)
    }
    position = order.index(name)
    for earlier in reversed(order[:position]):
        if earlier in present:
            return present[earlier] + 1
    for later in order[position + 1 :]:
        if later in present:
            return present[later]
    return len(node)


def _reconcile_yaml(
    spec: YamlDocumentSpec,
    original: str,
    desired: str,
    base: Value,
    location: MergeLocation,
    *,
    holds: tuple[tuple[str, ...], ...] = (),
    missing_file: bool = False,
    overwrite: bool = False,
) -> YamlReconciliation:
    """Confines accepted semantic edits to independent round-trip AST nodes."""
    desired_ast = _load(desired)
    wanted = cast(dict[str, Value], _keyed(spec, _plain(desired_ast), strict=True))
    doc = _load(original) if not missing_file else _load("{}\n")
    local = cast(dict[str, Value], _keyed(spec, _plain(doc)))
    base = _keyed(spec, base, strict=True)
    ambiguous = _ambiguous(spec, local)
    ambiguities = [
        MergeConflict(
            MergeLocation(
                location.file,
                held,
                held[-1] if spec.sequence_at(held[:-1]) else None,
            ),
            ConflictReason.DUPLICATE_IDENTITY,
        )
        for held in ambiguous
    ]
    remote = deepcopy(wanted)
    declared = deepcopy(wanted)
    for held in (*holds, *ambiguous):
        _hold(remote, base, held)
        _omit(declared, held)
    # Validate explicit membership policy even under overwrite authorization.
    result = reconcile(
        base, MISSING if missing_file else local, remote, location, spec.policy
    )
    value = result.value
    baseline = result.baseline
    conflicts = [*ambiguities, *result.conflicts]
    if overwrite:
        value = deepcopy(local)
        baseline = deepcopy(base) if isinstance(base, dict) else {}
        overlay_declared(value, declared)
        overlay_declared(baseline, declared)
        conflicts = list(ambiguities)
    if value is MISSING:
        return YamlReconciliation(original, _unkeyed(spec, baseline), tuple(conflicts))

    counts: dict[int, int] = {}

    def count_refs(node: Any) -> None:
        if not isinstance(node, (dict, list)) and not getattr(node, "anchor", None):
            return
        anchor = getattr(node, "anchor", None)
        if anchor is not None and anchor.value is not None:
            anchor.always_dump = True
        counts[id(node)] = counts.get(id(node), 0) + 1
        if counts[id(node)] > 1:
            return
        if isinstance(node, dict):
            for child in node.values():
                count_refs(child)
            for source in getattr(node, "merge", ()):
                count_refs(source)
        elif isinstance(node, list):
            for child in node:
                count_refs(child)

    count_refs(doc)

    def hazardous(node: Any) -> bool:
        return counts.get(id(node), 0) > 1 or bool(getattr(node, "merge", ()))

    def contains_hazard(node: Any) -> bool:
        if hazardous(node):
            return True
        children = (
            node.values()
            if isinstance(node, dict)
            else node
            if isinstance(node, list)
            else ()
        )
        return any(contains_hazard(child) for child in children)

    def patch(
        ast: Any,
        before: dict[str, Value],
        after: dict[str, Value],
        owned: dict[str, Value],
        previous: dict[str, Value],
        styled: Any,
        keys: tuple[str, ...],
    ) -> None:
        for key, child in list(after.items()):
            old = before.get(key, MISSING)
            if semantic_equal(old, child):
                continue
            path = (*keys, key)
            node = ast.get(key)
            recursive = isinstance(old, dict) and isinstance(child, dict)
            if hazardous(ast) or (
                hazardous(node) if recursive else contains_hazard(node)
            ):
                if old is MISSING:
                    after.pop(key)
                else:
                    after[key] = deepcopy(old)
                if key in previous:
                    owned[key] = deepcopy(previous[key])
                else:
                    owned.pop(key, None)
                conflicts.append(
                    MergeConflict(
                        MergeLocation(location.file, path),
                        ConflictReason.SHARED_STRUCTURE,
                    )
                )
            elif (
                recursive
                and (sequence := spec.sequence_at(path)) is not None
                and isinstance(node, list)
            ):
                indexed = {
                    str(record[sequence.identity]): record
                    for record in node
                    if _identified(record, sequence)
                }
                order = [str(record[sequence.identity]) for record in styled[key]]
                patch(
                    indexed,
                    cast(dict[str, Value], old),
                    cast(dict[str, Value], child),
                    cast(dict[str, Value], owned.setdefault(key, {})),
                    cast(dict[str, Value], previous.get(key, {})),
                    dict(zip(order, styled[key], strict=True)),
                    path,
                )
                for name in order:
                    if name in cast(dict[str, Value], old) or name not in indexed:
                        continue
                    record = indexed[name]
                    record[sequence.identity] = name
                    node.insert(_insertion_index(node, sequence, order, name), record)
            elif recursive:
                patch(
                    node,
                    cast(dict[str, Value], old),
                    cast(dict[str, Value], child),
                    cast(dict[str, Value], owned.setdefault(key, {})),
                    cast(dict[str, Value], previous.get(key, {})),
                    styled.get(key, {}),
                    path,
                )
            elif (
                isinstance(old, list)
                and isinstance(child, list)
                and path in spec.policy.set_like_paths
                and semantic_equal(old, child[: len(old)])
            ):
                for member in child[len(old) :]:
                    ast[key].append(deepcopy(member))
            else:
                replacement = (
                    deepcopy(styled[key])
                    if key in styled
                    and semantic_equal(
                        _keyed(spec, _plain(styled[key]), path),
                        child,
                    )
                    else deepcopy(_unkeyed(spec, child, path))
                )
                if isinstance(node, str) and isinstance(child, str):
                    replacement = type(node)(child)
                    anchor = getattr(node, "anchor", None)
                    if (
                        isinstance(replacement, ScalarString)
                        and anchor is not None
                        and anchor.value is not None
                    ):
                        replacement.yaml_set_anchor(anchor.value, always_dump=True)
                ast[key] = replacement

    patch(
        doc,
        local,
        cast(dict[str, Value], value),
        baseline if isinstance(baseline, dict) else {},
        base if isinstance(base, dict) else {},
        desired_ast,
        (),
    )

    if isinstance(baseline, dict):
        prune_unapplied(baseline, base if isinstance(base, dict) else {}, local)
        if not baseline and base is MISSING and not missing_file:
            baseline = MISSING
    if semantic_equal(local, value) and not missing_file:
        return YamlReconciliation(original, _unkeyed(spec, baseline), tuple(conflicts))
    if missing_file and semantic_equal(value, wanted):
        # A fully accepted new file keeps the desired text, including its comments.
        content = desired
    else:
        stream = StringIO()
        try:
            _codec(detect_style(original)).dump(doc, stream)
        except (YAMLError, ValueError, TypeError, RecursionError) as error:
            raise _invalid() from error
        content = stream.getvalue()
    decoded = decode_yaml_baseline(content)
    if not semantic_equal(_keyed(spec, decoded), value):
        raise _invalid()
    return YamlReconciliation(content, _unkeyed(spec, baseline), tuple(conflicts))
