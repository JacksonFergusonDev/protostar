"""Bounded YAML 1.2 round-trip codec and Codecov reconciliation adapter."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from typing import Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from ruamel.yaml.scalarstring import ScalarString

from .errors import ConfigurationError
from .merge import (
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

CODECOV_POLICY = MergePolicy(frozenset({("ignore",)}))
_MAX_NODES = 10000
_MAX_BYTES = 1_000_000
_TAGS = {"map", "seq", "str", "null", "bool", "int", "float", "merge"}


def _invalid() -> ConfigurationError:
    return ConfigurationError(
        "Invalid or unsupported YAML configuration.",
        hint="Use one YAML 1.2 mapping with unique string keys, standard JSON-like values, no cyclic aliases, and at most 100 levels/10000 nodes/1 MB.",
    )


def _codec() -> YAML:
    codec = YAML(typ="rt", pure=True)
    codec.preserve_quotes = True
    codec.allow_duplicate_keys = False
    codec.indent(mapping=2, sequence=4, offset=2)
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


def reconcile_codecov(
    original: str,
    desired: str,
    base: Value,
    location: MergeLocation,
    *,
    missing_file: bool = False,
    overwrite: bool = False,
) -> YamlReconciliation:
    """Reconciles Codecov with explicit set-like ignore membership."""
    return _reconcile_yaml(
        original,
        desired,
        base,
        location,
        missing_file=missing_file,
        overwrite=overwrite,
    )


def reconcile_pre_commit(
    original: str,
    desired: str,
    base: Value,
    location: MergeLocation,
    *,
    missing_file: bool = False,
    overwrite: bool = False,
) -> YamlReconciliation:
    """Reconciles exact repository/hook identities without owning foreign fields."""
    return _reconcile_yaml(
        original,
        desired,
        base,
        location,
        missing_file=missing_file,
        overwrite=overwrite,
        keyed=True,
    )


def validate_pre_commit_baseline(value: Value) -> None:
    """Validates unique repository/hook identities in desired or owned snapshots."""
    _keyed(value, strict=True)


def _identity_key(path: tuple[str, ...]) -> str | None:
    if path == ("repos",):
        return "repo"
    if len(path) == 3 and path[0] == "repos" and path[2] == "hooks":
        return "id"
    return None


def _keyed(value: Value, path: tuple[str, ...] = (), *, strict: bool = False) -> Value:
    identity = _identity_key(path)
    if identity is not None:
        if not isinstance(value, list):
            raise ConfigurationError(
                "Invalid pre-commit record sequence.",
                hint="Use lists of repositories and hooks with non-empty repo/id strings.",
            )
        grouped: dict[str, list[Value]] = {}
        for record in value:
            if (
                not isinstance(record, dict)
                or not isinstance(record.get(identity), str)
                or not record[identity]
            ):
                raise ConfigurationError(
                    "Invalid pre-commit identity.",
                    hint="Give every repository/hook a non-empty repo/id string.",
                )
            if (
                identity == "repo"
                and "rev" in record
                and (not isinstance(record["rev"], str) or not record["rev"])
            ):
                raise ConfigurationError(
                    "Invalid pre-commit revision.",
                    hint="Quote repository revisions as non-empty strings.",
                )
            name = cast(str, record[identity])
            grouped.setdefault(name, []).append(record)
        records: dict[str, Value] = {}
        for name, members in grouped.items():
            if len(members) > 1:
                if strict:
                    raise ConfigurationError(
                        "Duplicate desired or owned pre-commit identity.",
                        hint="Declare each repository and hook ID once.",
                    )
                records[name] = deepcopy(members)
            else:
                record = cast(dict[str, Value], members[0])
                records[name] = _keyed(
                    {k: v for k, v in record.items() if k != identity},
                    (*path, name),
                    strict=strict,
                )
        return records
    if isinstance(value, dict):
        return {k: _keyed(v, (*path, k), strict=strict) for k, v in value.items()}
    return deepcopy(value)


def _unkeyed(value: Value, path: tuple[str, ...] = ()) -> Value:
    if isinstance(value, dict):
        identity = _identity_key(path)
        if identity:
            records: list[Value] = []
            for name, record in value.items():
                if isinstance(record, list):
                    records.extend(deepcopy(record))
                else:
                    records.append(
                        {
                            identity: name,
                            **cast(dict[str, Value], _unkeyed(record, (*path, name))),
                        }
                    )
            return records
        return {k: _unkeyed(v, (*path, k)) for k, v in value.items()}
    return deepcopy(value)


def _reconcile_yaml(
    original: str,
    desired: str,
    base: Value,
    location: MergeLocation,
    *,
    missing_file: bool = False,
    overwrite: bool = False,
    keyed: bool = False,
) -> YamlReconciliation:
    """Confines accepted semantic edits to independent round-trip AST nodes."""
    desired_ast = _load(desired)
    remote = cast(dict[str, Value], _plain(desired_ast))
    doc = _load(original) if not missing_file else _load("{}\n")
    local = cast(dict[str, Value], _plain(doc))
    ambiguities: list[MergeConflict] = []
    policy = MergePolicy() if keyed else CODECOV_POLICY
    if keyed:
        remote = cast(dict[str, Value], _keyed(remote, strict=True))
        local = cast(dict[str, Value], _keyed(local))
        base = _keyed(base, strict=True)
        repositories = local.get("repos", MISSING)
        if isinstance(repositories, dict):
            for name, record in repositories.items():
                hooks = record.get("hooks", {}) if isinstance(record, dict) else {}
                if isinstance(record, list) or (
                    isinstance(hooks, dict)
                    and any(isinstance(hook, list) for hook in hooks.values())
                ):
                    planned = remote.get("repos")
                    if isinstance(planned, dict):
                        planned.pop(name, None)
                    ambiguities.append(
                        MergeConflict(
                            MergeLocation(location.file, ("repos", name), name),
                            ConflictReason.DUPLICATE_IDENTITY,
                        )
                    )
    # Validate explicit membership policy even under overwrite authorization.
    result = reconcile(
        base, MISSING if missing_file else local, remote, location, policy
    )
    value = result.value
    baseline = result.baseline
    conflicts = [*ambiguities, *result.conflicts]
    if overwrite:
        value = deepcopy(local)
        baseline = deepcopy(base) if isinstance(base, dict) else {}
        overlay_declared(value, remote)
        overlay_declared(baseline, remote)
        conflicts = list(ambiguities)
    if value is MISSING:
        return YamlReconciliation(
            original, _unkeyed(baseline) if keyed else baseline, tuple(conflicts)
        )

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
            elif recursive and keyed and _identity_key(path) and isinstance(node, list):
                identity = _identity_key(path)
                indexed = {str(record[identity]): record for record in node}
                desired_index = {
                    str(record[identity]): record for record in styled[key]
                }
                patch(
                    indexed,
                    cast(dict[str, Value], old),
                    cast(dict[str, Value], child),
                    cast(dict[str, Value], owned.setdefault(key, {})),
                    cast(dict[str, Value], previous.get(key, {})),
                    desired_index,
                    path,
                )
                for name, record in indexed.items():
                    if name not in cast(dict[str, Value], old):
                        record[identity] = name
                        node.append(record)
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
                and path in policy.set_like_paths
                and semantic_equal(old, child[: len(old)])
            ):
                for member in child[len(old) :]:
                    ast[key].append(deepcopy(member))
            else:
                replacement = (
                    deepcopy(styled[key])
                    if key in styled
                    and semantic_equal(
                        _keyed(_plain(styled[key]), path)
                        if keyed
                        else _plain(styled[key]),
                        child,
                    )
                    else deepcopy(_unkeyed(child, path) if keyed else child)
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
        return YamlReconciliation(
            original, _unkeyed(baseline) if keyed else baseline, tuple(conflicts)
        )
    stream = StringIO()
    try:
        _codec().dump(doc, stream)
    except (YAMLError, ValueError, TypeError, RecursionError) as error:
        raise _invalid() from error
    content = stream.getvalue()
    decoded = decode_yaml_baseline(content)
    if not semantic_equal(_keyed(decoded) if keyed else decoded, value):
        raise _invalid()
    return YamlReconciliation(
        content, _unkeyed(baseline) if keyed else baseline, tuple(conflicts)
    )
