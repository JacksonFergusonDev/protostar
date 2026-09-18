"""Pure semantic reconciliation; format adapters retain and mutate their own ASTs."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import cast

from .errors import ConfigurationError


class Missing(StrEnum):
    """Explicit absence, distinct from a present null."""

    VALUE = "missing"


MISSING = Missing.VALUE
type Scalar = str | bool | int | float | date | datetime | time | None
type Value = Scalar | list[Value] | dict[str, Value] | Missing


class MergeDecision(StrEnum):
    """Action for one managed value or subtree."""

    KEEP_LOCAL = "keep-local"
    APPLY_REMOTE = "apply-remote"
    CONFLICT = "conflict"


class ConflictReason(StrEnum):
    """Machine-readable reason for preserving a conflicting local contribution."""

    DUPLICATE_IDENTITY = "duplicate-identity"
    UNSAFE_PIN = "unsafe-pin"
    SHARED_STRUCTURE = "shared-structure"
    UNOWNED = "unowned"
    DIVERGED = "diverged"
    TYPE_MISMATCH = "type-mismatch"
    DELETED_ANCESTOR = "deleted-ancestor"


@dataclass(frozen=True)
class MergeLocation:
    """Concrete file, semantic key path, and optional adapter record identity."""

    file: str
    keys: tuple[str, ...] = ()
    identity: str | None = None


@dataclass(frozen=True)
class MergeConflict:
    """Structured conflict without terminal or diagnostic formatting."""

    location: MergeLocation
    reason: ConflictReason


@dataclass(frozen=True)
class MergePolicy:
    """Explicit set-like paths; every other sequence is atomic."""

    set_like_paths: frozenset[tuple[str, ...]] = frozenset()
    protected_ancestor: bool = False


DEFAULT_POLICY = MergePolicy()


@dataclass(frozen=True)
class MergeResult:
    """Semantic output and composite owned baseline, detached from all inputs."""

    value: Value
    baseline: Value
    decision: MergeDecision
    conflicts: tuple[MergeConflict, ...] = ()


def validate_value(value: Value) -> None:
    """Rejects unsupported shapes, cyclic containers, and excessive nesting."""
    active: set[int] = set()

    def visit(node: Value, depth: int) -> None:
        if depth > 100:
            raise ConfigurationError(
                "Semantic value is too deeply nested.",
                hint="Limit configuration nesting to 100 levels.",
            )
        if node is MISSING or type(node) in (
            str,
            bool,
            int,
            float,
            date,
            datetime,
            time,
            type(None),
        ):
            return
        if type(node) not in (dict, list):
            raise ConfigurationError(
                "Unsupported semantic value type.",
                hint="Pass decoded scalar, mapping, or sequence values to reconciliation.",
            )
        if id(node) in active:
            raise ConfigurationError(
                "Cyclic semantic configuration.",
                hint="Remove cyclic aliases before reconciliation.",
            )
        active.add(id(node))
        if isinstance(node, dict):
            for key, child in node.items():
                if type(key) is not str or child is MISSING:
                    raise ConfigurationError(
                        "Invalid semantic mapping entry.",
                        hint="Use string keys and omit missing entries.",
                    )
                visit(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                if child is MISSING:
                    raise ConfigurationError(
                        "Missing sequence member.",
                        hint="Use absence only for entire values.",
                    )
                visit(child, depth + 1)
        active.remove(id(node))

    visit(value, 0)


def semantic_equal(left: Value, right: Value) -> bool:
    """Compares decoded values without conflating booleans, numbers, or nulls."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            semantic_equal(v, right[k]) for k, v in left.items()
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            semantic_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    if (
        isinstance(left, float)
        and isinstance(right, float)
        and math.isnan(left)
        and math.isnan(right)
    ):
        return True
    return left == right


def reconcile(
    base: Value,
    local: Value,
    remote: Value,
    location: MergeLocation,
    policy: MergePolicy = DEFAULT_POLICY,
) -> MergeResult:
    """Reconciles owned contributions without adoption, pruning, or side effects.

    Args:
        base: Only previously applied owned contributions, or explicit absence.
        local: Current decoded workspace value, or explicit absence.
        remote: Desired contribution, or explicit absence.
        location: File/key/identity information carried into conflicts.
        policy: Adapter-selected set-like paths and ancestor deletion protection.

    Returns:
        Detached semantic values and the baseline for a candidate transaction.
    """
    for value in (base, local, remote):
        validate_value(value)

    def merge(
        previous: Value,
        current: Value,
        incoming: Value,
        loc: MergeLocation,
        protected: bool,
    ) -> MergeResult:
        def keep() -> MergeResult:
            return MergeResult(
                deepcopy(current), deepcopy(previous), MergeDecision.KEEP_LOCAL
            )

        def conflict(reason: ConflictReason) -> MergeResult:
            return MergeResult(
                deepcopy(current),
                deepcopy(previous),
                MergeDecision.CONFLICT,
                (MergeConflict(loc, reason),),
            )

        def apply() -> MergeResult:
            return MergeResult(
                deepcopy(incoming), deepcopy(incoming), MergeDecision.APPLY_REMOTE
            )

        if incoming is MISSING:
            return keep()
        if protected:
            if semantic_equal(incoming, previous):
                return keep()
            return conflict(ConflictReason.DELETED_ANCESTOR)
        # Recurse collections so foreign siblings/members are never adopted.
        if (
            previous is not MISSING
            and semantic_equal(current, incoming)
            and not isinstance(incoming, dict)
            and not (isinstance(incoming, list) and loc.keys in policy.set_like_paths)
        ):
            return MergeResult(
                deepcopy(current), deepcopy(incoming), MergeDecision.KEEP_LOCAL
            )
        if previous is not MISSING and semantic_equal(incoming, previous):
            return keep()
        if previous is not MISSING and current is MISSING:
            return conflict(ConflictReason.DELETED_ANCESTOR)
        if isinstance(incoming, dict):
            if current is not MISSING and not isinstance(current, dict):
                return conflict(ConflictReason.TYPE_MISMATCH)
            if previous is not MISSING and not isinstance(previous, dict):
                return conflict(ConflictReason.TYPE_MISMATCH)
            values: dict[str, Value] = (
                deepcopy(current) if isinstance(current, dict) else {}
            )
            baseline: dict[str, Value] = (
                deepcopy(previous) if isinstance(previous, dict) else {}
            )
            conflicts: list[MergeConflict] = []
            for key, desired in incoming.items():
                child = merge(
                    baseline.get(key, MISSING),
                    values.get(key, MISSING),
                    desired,
                    MergeLocation(loc.file, (*loc.keys, key), loc.identity),
                    False,
                )
                if child.value is not MISSING:
                    values[key] = child.value
                if child.baseline is not MISSING:
                    baseline[key] = child.baseline
                conflicts.extend(child.conflicts)
            owned: Value = (
                baseline
                if baseline or previous is not MISSING or current is MISSING
                else MISSING
            )
            decision = (
                MergeDecision.CONFLICT
                if conflicts
                else (
                    MergeDecision.KEEP_LOCAL
                    if semantic_equal(values, current)
                    else MergeDecision.APPLY_REMOTE
                )
            )
            return MergeResult(values, owned, decision, tuple(conflicts))
        if isinstance(incoming, list) and loc.keys in policy.set_like_paths:
            if (current is not MISSING and not isinstance(current, list)) or (
                previous is not MISSING and not isinstance(previous, list)
            ):
                return conflict(ConflictReason.TYPE_MISMATCH)
            members = deepcopy(current) if isinstance(current, list) else []
            owned_members = deepcopy(previous) if isinstance(previous, list) else []
            for member in incoming:
                if any(semantic_equal(member, owned) for owned in owned_members):
                    continue
                if not any(semantic_equal(member, existing) for existing in members):
                    members.append(deepcopy(member))
                    owned_members.append(deepcopy(member))
            owned = (
                owned_members
                if owned_members or previous is not MISSING or current is MISSING
                else MISSING
            )
            return MergeResult(
                members,
                owned,
                MergeDecision.KEEP_LOCAL
                if semantic_equal(members, current)
                else MergeDecision.APPLY_REMOTE,
            )
        if previous is MISSING:
            if current is MISSING:
                return apply()
            if semantic_equal(current, incoming):
                return keep()
            return conflict(ConflictReason.UNOWNED)
        if type(current) is not type(incoming):
            return conflict(ConflictReason.TYPE_MISMATCH)
        if semantic_equal(current, previous):
            return apply()
        return conflict(ConflictReason.DIVERGED)

    def validate_policy(node: Value, keys: tuple[str, ...]) -> None:
        if keys in policy.set_like_paths and isinstance(node, list):
            for index, member in enumerate(node):
                if isinstance(member, (dict, list)) or any(
                    semantic_equal(member, earlier) for earlier in node[:index]
                ):
                    raise ConfigurationError(
                        "Ambiguous set-like sequence.",
                        hint="Use unique scalar members or an atomic/file-specific sequence policy.",
                    )
        if isinstance(node, dict):
            for key, child in node.items():
                validate_policy(child, (*keys, key))

    for value in (base, local, remote):
        validate_policy(value, location.keys)
    return merge(base, local, remote, location, policy.protected_ancestor)


def overlay_declared(target: dict[str, Value], incoming: dict[str, Value]) -> None:
    """Overlays declared leaves onto ``target`` in place, retaining foreign siblings.

    Mappings present on both sides merge recursively; every other declared value
    replaces the target with a detached copy. Used for explicit overwrite, which owns
    declared values but never undeclared siblings.

    Args:
        target: Mapping mutated in place.
        incoming: Declared contribution copied into ``target``.
    """
    for key, child in incoming.items():
        existing = target.get(key)
        if isinstance(child, dict) and isinstance(existing, dict):
            overlay_declared(existing, child)
        else:
            target[key] = deepcopy(child)


def prune_unapplied(
    owned: dict[str, Value], previous: dict[str, Value], current: dict[str, Value]
) -> None:
    """Drops newly created owned mappings that the adapter left empty, in place.

    An owned mapping that accepted no children and did not exist in the previous
    baseline was never applied, so it must not become owned.

    Args:
        owned: Composite baseline mutated in place.
        previous: Baseline before this reconciliation.
        current: Local semantic value the accepted edits were applied to.
    """
    for key, child in list(owned.items()):
        if isinstance(child, dict) and isinstance(current.get(key), dict):
            prior = previous.get(key, {})
            prune_unapplied(
                child,
                prior if isinstance(prior, dict) else {},
                cast(dict[str, Value], current[key]),
            )
            if not child and key not in previous:
                owned.pop(key)
