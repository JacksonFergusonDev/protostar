"""Pure semantic reconciliation; format adapters retain and mutate their own ASTs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from enum import StrEnum
from functools import cached_property
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
    RETRACTED = "retracted"


@dataclass(frozen=True)
class LineSpan:
    """Lines of a local text file, numbered as in a unified diff hunk header.

    Attributes:
        start: One-based number of the first line, or, when ``count`` is zero,
            of the line after which the span sits (zero before the first line).
        count: Number of lines, zero when the local side has none there.
    """

    start: int
    count: int

    def to_dict(self) -> dict[str, int]:
        """Returns the span as a JSON-ready mapping."""
        return {"start": self.start, "count": self.count}


@dataclass(frozen=True)
class MergeLocation:
    """Concrete file, semantic key path, optional record identity, and text lines."""

    file: str
    keys: tuple[str, ...] = ()
    identity: str | None = None
    lines: LineSpan | None = None


def describe_location(location: MergeLocation) -> str:
    """Returns a plain-text label for a location within its file, or ``""``.

    Args:
        location: The location to describe.

    Returns:
        The dotted key path, the line numbers, or an empty string for the
        whole file.
    """
    if location.keys:
        return ".".join(location.keys)
    span = location.lines
    if span is None:
        return ""
    if span.count == 0:
        return f"after line {span.start}" if span.start else "at the start"
    if span.count == 1:
        return f"line {span.start}"
    return f"lines {span.start}-{span.start + span.count - 1}"


class ResolutionChoice(StrEnum):
    """How a conflict is settled. Every choice advances ownership to the update.

    ``LOCAL`` keeps the local content, ``DESIRED`` takes the update, and ``BOTH``
    keeps the local lines of a text hunk followed by the update's.
    """

    LOCAL = "local"
    DESIRED = "desired"
    BOTH = "both"


# Resolution choices keyed by ``MergeConflict.id``.
type Resolutions = Mapping[str, ResolutionChoice]
NO_RESOLUTIONS: Resolutions = {}


@dataclass(frozen=True)
class ConflictSides:
    """What each side holds where a conflict is, so it can be shown and settled.

    Attributes:
        base: The owned baseline there, or ``MISSING`` when never owned.
        local: The workspace content there, or ``MISSING`` when deleted.
        desired: The update there, or ``MISSING`` when it is retracted.
        line: For text, the zero-based line where the hunk starts in the local
            text it was merged in, which tells identical hunks apart; ``None``
            for structured values.
    """

    base: Value
    local: Value
    desired: Value
    line: int | None = None

    @property
    def text(self) -> bool:
        """Returns whether the sides are text rather than structured values."""
        return self.line is not None


@dataclass(frozen=True)
class MergeConflict:
    """Structured conflict without terminal or diagnostic formatting.

    Attributes:
        location: Where the conflict is.
        reason: Why the local content was kept.
        sides: Each side's content, or ``None`` when the conflict can only be
            settled by hand, such as a document-policy hold.
        resolution: The choice that settled it, or ``None`` while open.
    """

    location: MergeLocation
    reason: ConflictReason
    sides: ConflictSides | None = None
    resolution: ResolutionChoice | None = None

    @cached_property
    def id(self) -> str:
        """Returns a content-addressed identity that is stable across reviews.

        It covers the location and every side, but not text line numbers, which
        move when other conflicts are settled. A conflict whose content changed
        since it was reviewed therefore has a different identity.
        """
        sides = self.sides
        payload = [
            self.location.file,
            list(self.location.keys),
            self.location.identity,
            self.reason.value,
            None
            if sides is None
            else [
                _canonical(sides.base),
                _canonical(sides.local),
                _canonical(sides.desired),
                sides.line,
            ],
        ]
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()[:12]

    def __hash__(self) -> int:
        """Hashes by identity, since the sides can hold lists and mappings."""
        return hash((self.id, self.resolution))

    @property
    def choices(self) -> tuple[ResolutionChoice, ...]:
        """Returns the choices that can settle this conflict, if any."""
        if self.sides is None:
            return ()
        if self.sides.text and self.location.lines is not None:
            return (
                ResolutionChoice.LOCAL,
                ResolutionChoice.DESIRED,
                ResolutionChoice.BOTH,
            )
        return (ResolutionChoice.LOCAL, ResolutionChoice.DESIRED)

    def settle(self, resolutions: Resolutions) -> MergeConflict | None:
        """Returns this conflict settled by its chosen resolution, if one applies.

        Args:
            resolutions: Choices keyed by conflict identity.

        Returns:
            The conflict with its resolution, or ``None`` when no choice this
            conflict offers was made.
        """
        choice = resolutions.get(self.id)
        if choice is None or choice not in self.choices:
            return None
        return replace(self, resolution=choice)


def _canonical(value: Value) -> object:
    """Encodes a value for hashing without conflating types JSON would merge."""
    if value is MISSING:
        return ["missing"]
    if isinstance(value, dict):
        return ["map", [[key, _canonical(value[key])] for key in sorted(value)]]
    if isinstance(value, list):
        return ["list", [_canonical(child) for child in value]]
    if isinstance(value, (date, time)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, float):
        return ["float", repr(value)]
    return [type(value).__name__, value]


@dataclass(frozen=True)
class MergePolicy:
    """Explicit set-like paths; every other sequence is atomic.

    Attributes:
        set_like_paths: Key paths whose scalar sequences merge by membership.
        protected_ancestor: Whether the adapter operates under a deleted owned ancestor.
        complete: Whether the remote value is one generator's complete document, so
            owned mapping keys it no longer declares are retracted: removed when
            unedited, kept with a ``retracted`` conflict when edited.
    """

    set_like_paths: frozenset[tuple[str, ...]] = frozenset()
    protected_ancestor: bool = False
    complete: bool = False


DEFAULT_POLICY = MergePolicy()


@dataclass(frozen=True)
class MergeResult:
    """Semantic output and composite owned baseline, detached from all inputs.

    Attributes:
        value: The merged value.
        baseline: The composite owned baseline to record.
        decision: What happened at the root.
        conflicts: Open conflicts, where the local content was kept.
        resolved: Conflicts settled by a resolution.
    """

    value: Value
    baseline: Value
    decision: MergeDecision
    conflicts: tuple[MergeConflict, ...] = ()
    resolved: tuple[MergeConflict, ...] = ()


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
    resolutions: Resolutions = NO_RESOLUTIONS,
) -> MergeResult:
    """Reconciles owned contributions without adoption, pruning, or side effects.

    A resolved conflict owns the desired value either way: keeping the local
    value leaves it as an edit of the update, and taking the update applies it.

    Args:
        base: Only previously applied owned contributions, or explicit absence.
        local: Current decoded workspace value, or explicit absence.
        remote: Desired contribution, or explicit absence.
        location: File/key/identity information carried into conflicts.
        policy: Adapter-selected set-like paths and ancestor deletion protection.
        resolutions: Choices settling conflicts, keyed by conflict identity.

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
            found = MergeConflict(
                loc,
                reason,
                ConflictSides(
                    deepcopy(previous), deepcopy(current), deepcopy(incoming)
                ),
            )
            settled = found.settle(resolutions)
            if settled is None:
                return MergeResult(
                    deepcopy(current),
                    deepcopy(previous),
                    MergeDecision.CONFLICT,
                    (found,),
                )
            if settled.resolution is ResolutionChoice.LOCAL:
                return MergeResult(
                    deepcopy(current),
                    deepcopy(incoming),
                    MergeDecision.KEEP_LOCAL,
                    resolved=(settled,),
                )
            return replace(apply(), resolved=(settled,))

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
            resolved: list[MergeConflict] = []
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
                resolved.extend(child.resolved)
            if policy.complete and isinstance(previous, dict):
                for key in [k for k in previous if k not in incoming]:
                    local = values.get(key, MISSING)
                    if local is MISSING:
                        baseline.pop(key, None)
                    elif semantic_equal(local, previous[key]):
                        values.pop(key)
                        baseline.pop(key, None)
                    else:
                        found = MergeConflict(
                            MergeLocation(loc.file, (*loc.keys, key), loc.identity),
                            ConflictReason.RETRACTED,
                            ConflictSides(
                                deepcopy(previous[key]), deepcopy(local), MISSING
                            ),
                        )
                        settled = found.settle(resolutions)
                        if settled is None:
                            conflicts.append(found)
                            continue
                        # Either way Protostar stops owning the retracted value.
                        baseline.pop(key)
                        if settled.resolution is ResolutionChoice.DESIRED:
                            values.pop(key)
                        resolved.append(settled)
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
            return MergeResult(
                values, owned, decision, tuple(conflicts), tuple(resolved)
            )
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


def lookup(value: Value, path: tuple[str, ...]) -> Value:
    """Returns the value at a key path, or ``MISSING`` when any key is absent.

    Args:
        value: Decoded value to walk.
        path: Mapping keys from the root.

    Returns:
        The value at ``path``, not copied, or ``MISSING``.
    """
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def hold(remote: dict[str, Value], base: Value, path: tuple[str, ...]) -> None:
    """Replaces the desired value at ``path`` by its baseline, or drops it, in place.

    A held value reads as unchanged to the kernel, so local content and previous
    ownership there are kept without a conflict. Holding is never done by omission
    alone, which would read as a retraction or change of an owned value.

    Args:
        remote: Desired value mutated in place.
        base: Owned baseline, or ``MISSING``.
        path: Key path to hold; nothing happens when its parent is not declared.
    """
    parent = lookup(remote, path[:-1])
    if not isinstance(parent, dict):
        return
    prior = lookup(base, path)
    if prior is MISSING:
        parent.pop(path[-1], None)
    else:
        parent[path[-1]] = deepcopy(prior)


def without_paths(
    value: dict[str, Value], paths: frozenset[tuple[str, ...]]
) -> dict[str, Value]:
    """Returns a detached copy of ``value`` without the given key paths.

    Used for seed paths, which never merge into an existing document. A mapping
    left empty by a removal is removed too, so a contribution that declared only
    seeds leaves no empty table behind; mappings that were already empty are kept.

    Args:
        value: Decoded mapping, such as a desired document or baseline.
        paths: Key paths to remove.

    Returns:
        The copy without ``paths``.
    """

    def remove(node: dict[str, Value], path: tuple[str, ...]) -> bool:
        key, *rest = path
        if key not in node:
            return False
        if not rest:
            del node[key]
            return True
        child = node[key]
        if not isinstance(child, dict) or not remove(child, tuple(rest)):
            return False
        if not child:
            del node[key]
        return True

    result = deepcopy(value)
    for path in paths:
        remove(result, path)
    return result


def retract_undeclared(
    target: dict[str, Value], owned: dict[str, Value], incoming: dict[str, Value]
) -> None:
    """Removes owned keys that ``incoming`` no longer declares, in place.

    Used for explicit overwrite of a complete document: retracted owned content is
    removed from ``target`` and ``owned`` even when edited. Foreign keys, which
    ``owned`` never contains, are untouched.

    Args:
        target: Mapping mutated in place.
        owned: Owned baseline mutated in place.
        incoming: Complete desired contribution.
    """
    for key in list(owned):
        if key not in incoming:
            target.pop(key, None)
            owned.pop(key)
        elif isinstance(owned[key], dict) and isinstance(incoming[key], dict):
            child = target.get(key)
            retract_undeclared(
                child if isinstance(child, dict) else {},
                cast(dict[str, Value], owned[key]),
                cast(dict[str, Value], incoming[key]),
            )


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
