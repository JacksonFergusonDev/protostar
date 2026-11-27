"""Bounded YAML 1.2 round-trip codec and spec-driven reconciliation adapter."""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from enum import Enum
from functools import lru_cache
from typing import Any

import yaml_edit as ye

from .errors import ConfigurationError
from .merge import (
    DEFAULT_POLICY,
    MISSING,
    NO_RESOLUTIONS,
    ConflictReason,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    ResolutionChoice,
    Resolutions,
    StructuredReconciliation,
    Value,
    as_mapping,
    hold,
    lookup,
    overlay_declared,
    prune_unapplied,
    reconcile,
    retract_undeclared,
    semantic_equal,
    sort_value_keys,
    validate_value,
)

_MAX_NODES = 10000
_MAX_BYTES = 1_000_000
_ALLOWED_TAGS = frozenset(
    {
        "!!map",
        "!!seq",
        "!!str",
        "!!null",
        "!!bool",
        "!!int",
        "!!float",
        "!!merge",
        "tag:yaml.org,2002:map",
        "tag:yaml.org,2002:seq",
        "tag:yaml.org,2002:str",
        "tag:yaml.org,2002:null",
        "tag:yaml.org,2002:bool",
        "tag:yaml.org,2002:int",
        "tag:yaml.org,2002:float",
        "tag:yaml.org,2002:merge",
    }
)
# Only inspect the properties and separators before a CST node. Skip complete
# comments and tags so an ampersand inside either cannot bind an alias.
_PROPERTY = re.compile(rb"#[^\r\n]*|![^\s,\[\]{}]*|&([^\s,\[\]{}]+)")
_SIMPLE_PLAIN = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_./%+-]*")


def _invalid() -> ConfigurationError:
    return ConfigurationError(
        "Invalid or unsupported YAML configuration.",
        hint="Use one YAML 1.2 mapping with unique string keys, standard JSON-like values, no cyclic aliases, and at most 100 levels/10000 nodes/1 MB.",
    )


def _parse_yaml(content: str) -> ye.YamlFile:
    """Parses YAML text into a lossless CST (benchmark probe seam)."""
    return ye.YamlFile.parse(content)


def _merge_key(node: ye.Node) -> bool:
    scalar = node.as_scalar()
    return scalar is not None and scalar.value() == "<<"


type _Range = tuple[int, int]


@dataclass(frozen=True)
class _Anchor:
    size: int
    height: int
    span: _Range


def _anchor_name(raw: bytes, start: int, end: int) -> str | None:
    for match in _PROPERTY.finditer(raw, start, end):
        if match[1] is not None:
            return match[1].decode("utf-8")
    return None


def _load(content: str) -> tuple[ye.YamlFile, dict[str, Value], set[_Range]]:
    raw = content.encode("utf-8")
    if len(raw) > _MAX_BYTES:
        raise _invalid()
    try:
        parsed = _parse_yaml(content)
        for directive in parsed.directives():
            if directive.is_yaml_version() and directive.value() != "1.2":
                raise _invalid()
        documents = parsed.documents()
        if len(documents) != 1:
            raise _invalid()
        document = documents[0]
        root = document.root()
        if root is None or not root.is_mapping():
            raise _invalid()

        # Remember each completed anchor's expanded size and height. Charging
        # these at every alias bounds construction without expanding the graph.
        anchors: dict[str, _Anchor] = {}
        shared: set[_Range] = set()
        has_anchors = b"&" in raw
        count = 0

        def visit(node: ye.Node, depth: int, prefix: int) -> int:
            nonlocal count
            before = count
            count += 1
            if count > _MAX_NODES or depth > 100:
                raise _invalid()
            tagged = node.as_tagged()
            if tagged is not None and tagged.tag() not in _ALLOWED_TAGS:
                raise _invalid()
            mapping = tagged.as_mapping() if tagged else node.as_mapping()
            sequence = tagged.as_sequence() if tagged else node.as_sequence()
            anchor = None
            if has_anchors:
                # Properties precede the value. A tagged node includes those
                # properties in its range, so use its inner value's start.
                inner = mapping if mapping is not None else sequence
                start = node.byte_range()[0]
                if inner is not None:
                    start = inner.byte_range()[0]
                elif tagged is not None and (scalar := tagged.value()) is not None:
                    start = scalar.byte_range()[0]
                anchor = _anchor_name(raw, prefix, start)
                if anchor is not None:
                    anchors.pop(anchor, None)  # A new binding shadows the old one.

            height = 0
            if (alias := node.as_alias()) is not None:
                target = anchors.get(alias.name())
                if target is None:
                    raise _invalid()
                shared.update((node.byte_range(), target.span))
                height = target.height
                count += target.size - 1
                if count > _MAX_NODES or depth + height > 100:
                    raise _invalid()
            elif mapping is not None:
                seen: set[str] = set()
                for entry in mapping.entries():
                    key = entry.key()
                    if key is None or not key.is_scalar():
                        raise _invalid()
                    name = key.to_python()
                    if not isinstance(name, str) or name in seen:
                        raise _invalid()
                    seen.add(name)
                    visit(key, depth + 1, entry.byte_range()[0])
                    height = max(height, 1)
                    if (value := entry.value()) is not None:
                        height = max(
                            height, 1 + visit(value, depth + 1, key.byte_range()[1])
                        )
            elif sequence is not None:
                start = sequence.byte_range()[0]
                for child in sequence.values():
                    height = max(height, 1 + visit(child, depth + 1, start))
                    start = child.byte_range()[1]
            if anchor is not None:
                anchors[anchor] = _Anchor(count - before, height, node.byte_range())
            return height

        visit(root, 0, 0)
        # Resolve aliases and merge keys from the checked CST without reparsing.
        plain = as_mapping(_plain(document.to_python()))
        return parsed, plain, shared
    except ConfigurationError:
        raise
    except (
        ye.YamlError,
        ye.ParseError,
        ye.ResolveError,
        ValueError,
        TypeError,
        RecursionError,
    ) as error:
        raise _invalid() from error


def _plain(node: object) -> Value:
    if isinstance(node, dict):
        result: dict[str, Value] = {}
        for key, value in node.items():
            if not isinstance(key, str):
                raise _invalid()
            result[key] = _plain(value)
        return result
    if isinstance(node, list):
        return [_plain(value) for value in node]
    if node is None:
        return None
    if isinstance(node, bool):
        return bool(node)
    if isinstance(node, str):
        return str(node)
    if isinstance(node, int):
        return int(node)
    if isinstance(node, float):
        return float(node)
    raise _invalid()


def decode_yaml_baseline(content: str) -> dict[str, Value]:
    """Decodes a bounded YAML mapping into detached, type-aware semantic values."""
    return deepcopy(_decode_yaml_baseline(content))


@lru_cache(maxsize=256)
def _decode_yaml_baseline(content: str) -> dict[str, Value]:
    # One sync decodes the same baselines repeatedly; callers get a copy, so sharing is safe.
    _, value, _ = _load(content)
    validate_value(value)
    return value


def encode_yaml_baseline(value: dict[str, Value]) -> str:
    """Encodes owned values deterministically without local comments or aliases."""
    validate_value(value)
    sorted_value = as_mapping(sort_value_keys(value))
    try:
        if not sorted_value:
            content = "{}\n"
        else:
            document = ye.Document.parse("k: 0\n")
            document.remove("k")
            for key, item in sorted_value.items():
                payload: Any = item
                document.set(key, payload)
            content = str(document)
            if not content.endswith("\n"):
                content += "\n"
    except (ye.YamlError, ValueError, TypeError, RecursionError) as error:
        raise _invalid() from error
    decode_yaml_baseline(content)
    return content


@dataclass(frozen=True)
class YamlReconciliation(StructuredReconciliation):
    """Round-trip output, owned composite baseline, and structured conflicts."""


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
            pattern is WILDCARD or pattern == path[i]
            for i, pattern in enumerate(self.path)
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


@dataclass(frozen=True)
class YamlGuard:
    """Document-policy input to a reconciliation: where to hold and what to report.

    Attributes:
        holds: Keyed-view paths whose desired value is replaced by the owned
            baseline (or dropped when unowned), so local content and previous
            ownership are kept there without a conflict of their own.
        conflicts: Conflicts the policy found, reported ahead of the merge's own.
            One at a held path with sides can be settled: the hold is lifted
            and the merge then keeps the local value as an edit of the update,
            or takes the update.
    """

    holds: tuple[tuple[str, ...], ...] = ()
    conflicts: tuple[MergeConflict, ...] = ()


NO_GUARD = YamlGuard()
# Decides where a YAML document's policy holds, from the workspace path being
# reconciled and its decoded desired value, local value, and owned baseline.
type YamlGuardPolicy = Callable[[str, Value, Value, Value], YamlGuard]


def validate_yaml_baseline(spec: YamlDocumentSpec, value: Value) -> None:
    """Validates identities and fields of desired or owned snapshots strictly."""
    keyed_view(spec, value, strict=True)


def _identified(record: object, sequence: KeyedSequence) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(record.get(sequence.identity), str)
        and bool(record[sequence.identity])
    )


def keyed_view(
    spec: YamlDocumentSpec,
    value: Value,
    path: tuple[str, ...] = (),
    *,
    strict: bool = False,
) -> Value:
    """Presents keyed sequences as mappings from identity to record.

    Duplicate local identities map to the list of their records, which marks them
    ambiguous. Local records without an identity are foreign: they are left out of
    the keyed view and stay in place in the round-trip CST. Desired and owned
    snapshots (``strict``) must identify every record exactly once. Paths into the
    result are the paths a ``YamlGuard`` holds.

    Args:
        spec: Keyed sequences for this document.
        value: Decoded document, or a subtree of one at ``path``.
        path: Keyed-view path of ``value`` within its document.
        strict: Whether every record must carry a unique identity.

    Returns:
        The value with each keyed sequence replaced by an identity mapping.
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
            record = as_mapping(record)
            for field in sequence.string_fields:
                if field in record and (
                    not isinstance(record[field], str) or not record[field]
                ):
                    raise ConfigurationError(
                        f"Invalid {spec.name} field '{field}'.",
                        hint=f"Quote '{field}' values as non-empty strings.",
                    )
            grouped.setdefault(str(record[sequence.identity]), []).append(record)
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
                record = as_mapping(members[0])
                records[name] = keyed_view(
                    spec,
                    {k: v for k, v in record.items() if k != sequence.identity},
                    (*path, name),
                    strict=strict,
                )
        return records
    if isinstance(value, dict):
        return {
            k: keyed_view(spec, v, (*path, k), strict=strict) for k, v in value.items()
        }
    return deepcopy(value)


def _unkeyed(spec: YamlDocumentSpec, value: Value, path: tuple[str, ...] = ()) -> Value:
    if isinstance(value, dict):
        sequence = spec.sequence_at(path)
        if sequence is not None:
            records: list[Value] = []
            for name, record in value.items():
                if isinstance(record, list):
                    # Duplicates are held, so they never reach a write; this only
                    # keeps every record if one ever does.
                    records.extend(deepcopy(record))  # pragma: no mutate
                else:
                    records.append(
                        {
                            sequence.identity: name,
                            **as_mapping(_unkeyed(spec, record, (*path, name))),
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


def _omit(remote: dict[str, Value], path: tuple[str, ...]) -> None:
    parent = lookup(remote, path[:-1])
    if isinstance(parent, dict):
        parent.pop(path[-1], None)


def _key_position(present: list[str], order: list[str], key: str) -> int:
    """Places a new mapping key after its nearest earlier desired sibling present."""
    position = order.index(key)
    for earlier in reversed(order[:position]):
        if earlier in present:
            return present.index(earlier) + 1
    for later in order[position + 1 :]:
        if later in present:
            return present.index(later)
    return len(present)


def _insertion_index(
    items: list[Any], sequence: KeyedSequence, order: list[str], name: str
) -> int:
    """Places a new record after its nearest earlier desired sibling present."""
    present = {
        str(record[sequence.identity]): index
        for index, record in enumerate(items)
        if _identified(record, sequence)
    }
    position = order.index(name)
    for earlier in reversed(order[:position]):
        if earlier in present:
            return present[earlier] + 1
    for later in order[position + 1 :]:
        if later in present:
            return present[later]
    return len(items)


def _place(base: Value, path: tuple[str, ...], value: Value) -> Value:
    """Returns ``base`` with ``value`` at a key path, creating mappings on the way."""
    root: dict[str, Value] = deepcopy(base) if isinstance(base, dict) else {}
    node = root
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = deepcopy(value)
    return root


def _mapping_keys(mapping: ye.Mapping) -> list[str]:
    return list(mapping.keys())


def _set_mapping_value(
    mapping: ye.Mapping,
    key: str,
    replacement: Any,
    desired_order: list[str] | None,
) -> None:
    if mapping.contains_key(key):
        mapping.set(key, replacement)
    elif desired_order is not None and key in desired_order:
        position = _key_position(_mapping_keys(mapping), desired_order, key)
        mapping.insert_at_index(position, key, replacement)
    else:
        mapping.set(key, replacement)


def reconcile_yaml(
    spec: YamlDocumentSpec,
    original: str,
    desired: str,
    base: Value,
    location: MergeLocation,
    *,
    guard: YamlGuard = NO_GUARD,
    missing_file: bool = False,
    overwrite: bool = False,
    resolutions: Resolutions = NO_RESOLUTIONS,
    proposing: bool = False,
) -> YamlReconciliation:
    """Reconciles a YAML document under its spec without owning foreign content.

    Accepted semantic edits are confined to independent round-trip CST nodes.

    Args:
        spec: Keyed sequences and kernel policy for this document.
        original: Current workspace text; ignored when ``missing_file`` is set.
        desired: Desired contribution text.
        base: Previously applied owned contributions, or ``MISSING``.
        location: File location carried into conflicts.
        guard: Document-policy holds and conflicts, applied ahead of the merge.
        missing_file: Whether the workspace file is absent.
        overwrite: Whether explicit overwrite owns declared values.
        resolutions: Choices settling conflicts, keyed by conflict identity.
        proposing: Whether the document existed before Protostar owned any of
            it, so each change into it is a proposal.

    Returns:
        Emitted text, the composite owned baseline, and structured conflicts.
    """
    desired_file, desired_plain, _ = _load(desired)
    wanted = as_mapping(keyed_view(spec, desired_plain, strict=True))
    local_file, doc_plain, shared_ranges = (
        _load(original) if not missing_file else _load("{}\n")
    )
    doc = local_file[0]
    local = as_mapping(keyed_view(spec, doc_plain))
    base = keyed_view(spec, base, strict=True)
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
    guard_open: list[MergeConflict] = []
    guard_settled: list[MergeConflict] = []
    lifted: set[tuple[str, ...]] = set()
    for found in guard.conflicts:
        settled = found.settle(resolutions) if not overwrite else None
        if settled is None or found.sides is None:
            guard_open.append(found)
            continue
        # The side the merge must see as owned for it to reach the choice:
        # the update's to keep local content as an edit of it, local's to take it.
        owned = (
            found.sides.desired
            if settled.resolution is ResolutionChoice.LOCAL
            else found.sides.local
        )
        base = _place(base, found.location.keys, owned)
        lifted.add(found.location.keys)
        guard_settled.append(settled)
    for held in (*guard.holds, *ambiguous):
        if held in lifted:
            continue
        hold(remote, base, held)
        _omit(declared, held)
    # Validate explicit membership policy even under overwrite authorization.
    result = reconcile(
        base,
        MISSING if missing_file else local,
        remote,
        location,
        replace(spec.policy, proposing=proposing),
        resolutions,
    )
    value = result.value
    baseline = result.baseline
    conflicts = [*guard_open, *ambiguities, *result.conflicts]
    resolved = (*guard_settled, *result.resolved)
    proposals = result.proposals
    preserved = result.preserved
    if overwrite:
        value = deepcopy(local)
        baseline = deepcopy(base) if isinstance(base, dict) else {}
        if spec.policy.complete and isinstance(value, dict):
            # Held paths keep their owned value in ``remote``, so they are not retracted.
            retract_undeclared(value, baseline, remote)
        overlay_declared(value, declared)
        overlay_declared(baseline, declared)
        conflicts = [*guard.conflicts, *ambiguities]
        resolved = ()
        proposals = preserved = ()
    if value is MISSING:
        return YamlReconciliation(
            original,
            _unkeyed(spec, baseline),
            tuple(conflicts),
            tuple(resolved),
            proposals,
            preserved,
        )

    doc_root = doc.root()
    if doc_root is None:
        raise _invalid()

    # Snapshot hazard paths on the untouched CST before edits shift byte offsets.
    hazardous_paths: set[tuple[str, ...]] = set()
    contains_hazard_paths: set[tuple[str, ...]] = set()

    def scan_hazards(node: ye.Node, path: tuple[str, ...]) -> bool:
        is_shared = node.byte_range() in shared_ranges
        has_merge = False
        child_hazard = False
        if node.is_mapping():
            mapping = node.as_mapping()
            if mapping is not None:
                for entry in mapping.entries():
                    key_node = entry.key()
                    val_node = entry.value()
                    if key_node is not None and _merge_key(key_node):
                        has_merge = True
                    if key_node is not None and val_node is not None:
                        key_name = str(key_node.to_python())
                        if scan_hazards(val_node, (*path, key_name)):
                            child_hazard = True
        elif node.is_sequence():
            sequence = node.as_sequence()
            sequence_spec = spec.sequence_at(path)
            if sequence is not None:
                for idx, item in enumerate(sequence.values()):
                    item_path = (*path, str(idx))
                    if sequence_spec is not None and item.is_mapping():
                        item_py = item.to_python()
                        if _identified(item_py, sequence_spec):
                            item_path = (*path, str(item_py[sequence_spec.identity]))
                    if scan_hazards(item, item_path):
                        child_hazard = True
        is_haz = is_shared or has_merge
        if is_haz:
            hazardous_paths.add(path)
        if is_haz or child_hazard:
            contains_hazard_paths.add(path)
            return True
        return False

    scan_hazards(doc_root, ())

    def patch_mapping(
        mapping: ye.Mapping,
        before: dict[str, Value],
        after: dict[str, Value],
        owned: dict[str, Value],
        previous: dict[str, Value],
        styled_mapping: ye.Mapping | None,
        keys: tuple[str, ...],
    ) -> None:
        desired_order = (
            _mapping_keys(styled_mapping) if styled_mapping is not None else None
        )
        # Complete documents retract owned content; delete what the merge dropped.
        for key in [k for k in before if k not in after]:
            path = (*keys, key)
            if keys in hazardous_paths or path in contains_hazard_paths:
                after[key] = deepcopy(before[key])
                if key in previous:
                    owned[key] = deepcopy(previous[key])
                conflicts.append(
                    MergeConflict(
                        MergeLocation(location.file, path),
                        ConflictReason.SHARED_STRUCTURE,
                    )
                )
            else:
                mapping.remove(key)

        for key, child in list(after.items()):
            old = before.get(key, MISSING)
            if semantic_equal(old, child):
                continue
            path = (*keys, key)
            node = mapping.get(key)
            recursive = isinstance(old, dict) and isinstance(child, dict)
            if keys in hazardous_paths or (
                path in hazardous_paths if recursive else path in contains_hazard_paths
            ):
                if old is MISSING:
                    after.pop(key)
                else:
                    after[key] = deepcopy(old)
                if key in previous:
                    owned[key] = deepcopy(previous[key])
                else:
                    # A blocked change was owned.
                    owned.pop(key, None)  # pragma: no mutate
                conflicts.append(
                    MergeConflict(
                        MergeLocation(location.file, path),
                        ConflictReason.SHARED_STRUCTURE,
                    )
                )
            elif (
                recursive
                and (sequence_spec := spec.sequence_at(path)) is not None
                and node is not None
                and node.is_sequence()
            ):
                seq = node.as_sequence()
                if seq is None:
                    continue
                styled_seq = (
                    styled_mapping.get_sequence(key)
                    if styled_mapping is not None
                    else None
                )
                styled_records: dict[str, ye.Node] = {}
                styled_order: list[str] = []
                if styled_seq is not None:
                    for item in styled_seq.values():
                        item_py = item.to_python()
                        if _identified(item_py, sequence_spec):
                            name = str(item_py[sequence_spec.identity])
                            styled_records[name] = item
                            styled_order.append(name)

                old_map = as_mapping(old)
                child_map = as_mapping(child)
                owned_map = as_mapping(owned.setdefault(key, {}))  # pragma: no mutate
                prev_map = as_mapping(previous.get(key, {}))

                # Delete removed records first.
                removed = {name for name in old_map if name not in child_map}
                seq_vals = list(seq.values())
                for index in reversed(range(len(seq_vals))):
                    rec_py = seq_vals[index].to_python()
                    if (
                        _identified(rec_py, sequence_spec)
                        and str(rec_py[sequence_spec.identity]) in removed
                    ):
                        rec_name = str(rec_py[sequence_spec.identity])
                        rec_path = (*path, rec_name)
                        if path in hazardous_paths or rec_path in contains_hazard_paths:
                            child_map[rec_name] = deepcopy(old_map[rec_name])
                            if rec_name in prev_map:
                                owned_map[rec_name] = deepcopy(prev_map[rec_name])
                            conflicts.append(
                                MergeConflict(
                                    MergeLocation(location.file, rec_path),
                                    ConflictReason.SHARED_STRUCTURE,
                                )
                            )
                        else:
                            seq.pop(index)

                # Patch kept records in place.
                for item in seq.values():
                    rec_py = item.to_python()
                    if not _identified(rec_py, sequence_spec):
                        continue
                    rec_name = str(rec_py[sequence_spec.identity])
                    if rec_name not in old_map or rec_name not in child_map:
                        continue
                    if semantic_equal(old_map[rec_name], child_map[rec_name]):
                        continue
                    rec_path = (*path, rec_name)
                    if path in hazardous_paths or rec_path in hazardous_paths:
                        child_map[rec_name] = deepcopy(old_map[rec_name])
                        if rec_name in prev_map:
                            owned_map[rec_name] = deepcopy(prev_map[rec_name])
                        conflicts.append(
                            MergeConflict(
                                MergeLocation(location.file, rec_path),
                                ConflictReason.SHARED_STRUCTURE,
                            )
                        )
                        continue
                    item_mapping = item.as_mapping()
                    if item_mapping is None:
                        continue
                    styled_rec_node = styled_records.get(rec_name)
                    styled_rec_mapping = (
                        styled_rec_node.as_mapping()
                        if styled_rec_node is not None and styled_rec_node.is_mapping()
                        else None
                    )
                    patch_mapping(
                        item_mapping,
                        as_mapping(old_map[rec_name]),
                        as_mapping(child_map[rec_name]),
                        as_mapping(owned_map.setdefault(rec_name, {})),
                        as_mapping(prev_map.get(rec_name, {})),
                        styled_rec_mapping,
                        rec_path,
                    )

                # Insert new records at sibling-relative index.
                for name in styled_order:
                    if name in old_map or name not in child_map:
                        continue
                    rec_path = (*path, name)
                    if path in hazardous_paths:
                        child_map.pop(name, None)
                        owned_map.pop(name, None)
                        conflicts.append(
                            MergeConflict(
                                MergeLocation(location.file, rec_path),
                                ConflictReason.SHARED_STRUCTURE,
                            )
                        )
                        continue
                    current_items = [it.to_python() for it in seq.values()]
                    idx = _insertion_index(
                        current_items, sequence_spec, styled_order, name
                    )
                    styled_rec = styled_records.get(name)
                    if styled_rec is not None and semantic_equal(
                        keyed_view(spec, _plain(styled_rec.to_python()), rec_path),
                        {sequence_spec.identity: name, **as_mapping(child_map[name])},
                    ):
                        seq.insert(idx, styled_rec)
                    else:
                        record_value = {
                            sequence_spec.identity: name,
                            **as_mapping(_unkeyed(spec, child_map[name], rec_path)),
                        }
                        seq.insert(idx, record_value)
            elif recursive and node is not None and node.is_mapping():
                child_mapping = node.as_mapping()
                if child_mapping is None:
                    continue
                styled_sub = (
                    styled_mapping.get_mapping(key)
                    if styled_mapping is not None
                    else None
                )
                patch_mapping(
                    child_mapping,
                    as_mapping(old),
                    as_mapping(child),
                    # A changed mapping is always owned.
                    as_mapping(owned.setdefault(key, {})),  # pragma: no mutate
                    as_mapping(previous.get(key, {})),
                    styled_sub,
                    path,
                )
            elif (
                isinstance(old, list)
                and isinstance(child, list)
                and path in spec.policy.set_like_paths
                and semantic_equal(old, child[: len(old)])
                and node is not None
                and node.is_sequence()
            ):
                seq = node.as_sequence()
                if seq is not None:
                    for member in child[len(old) :]:
                        item_val: Any = deepcopy(member)
                        seq.append(item_val)
            else:
                styled_val = (
                    styled_mapping.get(key) if styled_mapping is not None else None
                )
                if (
                    node is not None
                    and (scalar := node.as_scalar()) is not None
                    and isinstance(old, str)
                    and isinstance(child, str)
                ):
                    # The string emitter quotes for the destination mapping.
                    # Reuse simple plain spellings such as 85% in either layout.
                    replacement: Any = child
                    if scalar.style() != "plain":
                        replacement = ye.ScalarValue(child, style=scalar.style())
                    elif (
                        styled_val is not None
                        and (desired_scalar := styled_val.as_scalar()) is not None
                        and desired_scalar.value() == child
                        and desired_scalar.to_python() == child
                        and _SIMPLE_PLAIN.fullmatch(child)
                    ):
                        replacement = styled_val
                elif styled_val is not None and semantic_equal(
                    keyed_view(spec, _plain(styled_val.to_python()), path),
                    child,
                ):
                    replacement = styled_val
                else:
                    replacement = deepcopy(_unkeyed(spec, child, path))
                _set_mapping_value(mapping, key, replacement, desired_order)

    root_mapping = doc.as_mapping()
    if root_mapping is None:
        raise _invalid()
    patch_mapping(
        root_mapping,
        local,
        as_mapping(value),
        # A document that reaches the patch is owned.
        baseline if isinstance(baseline, dict) else {},  # pragma: no mutate
        base if isinstance(base, dict) else {},
        desired_file[0].as_mapping(),
        (),
    )

    if isinstance(baseline, dict):
        prune_unapplied(baseline, base if isinstance(base, dict) else {}, local)
        if not baseline and base is MISSING and not missing_file:
            baseline = MISSING
    if semantic_equal(local, value) and not missing_file:
        return YamlReconciliation(
            original,
            _unkeyed(spec, baseline),
            tuple(conflicts),
            tuple(resolved),
            proposals,
            preserved,
        )
    if missing_file and semantic_equal(value, wanted):
        # A fully accepted new file keeps the desired text, including its comments.
        content = desired
    else:
        content = str(local_file)
        if not original.endswith("\n\n"):
            # A removed trailing item leaves its separator blank line on the item before.
            content = content.rstrip("\n") + "\n"
    decoded = decode_yaml_baseline(content)
    if not semantic_equal(keyed_view(spec, decoded), value):
        raise _invalid()
    return YamlReconciliation(
        content,
        _unkeyed(spec, baseline),
        tuple(conflicts),
        tuple(resolved),
        proposals,
        preserved,
    )
