"""Dependency resolution and package installation via uv."""

from collections import defaultdict
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from .errors import ConfigurationError
from .intent import DependencyGroup
from .manifest import DependencyManifest
from .merge import (
    MISSING,
    NO_RESOLUTIONS,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
    Resolutions,
    Value,
)
from .progress import ProgressStep, no_progress
from .sync_state import DependencyState
from .system import ProcessRunner

__all__ = ["DependencyGroup", "install_dependencies"]


def _install_group(
    packages: list[str],
    group: DependencyGroup,
    process_runner: ProcessRunner,
    progress: ProgressStep,
) -> None:
    """Installs a specific group of packages using uv add, as one progress step.

    Raises:
        CommandExecutionError | CommandTimeoutError: If installation fails.
    """
    if not packages:
        return

    cmd = ["uv", "add", *group.cli_args, *packages]
    noun = "dependency" if len(packages) == 1 else "dependencies"
    with progress(f"Installing {len(packages)} {group.label} {noun}"):
        process_runner.run(cmd, timeout=600)


def install_dependencies(
    dependencies_manifest: DependencyManifest,
    process_runner: ProcessRunner,
    progress: ProgressStep = no_progress,
) -> None:
    """Installs queued dependencies using uv, one progress step per group.

    Raises:
        CommandExecutionError | CommandTimeoutError: If any installation fails.
    """
    _install_group(
        dependencies_manifest.dependencies,
        DependencyGroup.MAIN,
        process_runner,
        progress,
    )
    _install_group(
        dependencies_manifest.dev_dependencies,
        DependencyGroup.DEV,
        process_runner,
        progress,
    )
    _install_group(
        dependencies_manifest.docs_dependencies,
        DependencyGroup.DOCS,
        process_runner,
        progress,
    )


@dataclass(frozen=True)
class DependencySelection:
    """Accepted resolver requests and the decisions about every other request.

    Attributes:
        packages: Requests the resolver adds.
        conflicts: Requests refused because the local requirement differs.
        resolved: Conflicts and preserved requirements a resolution settled.
        proposals: Requests into a project Protostar never owned, applied
            unless a resolution declined them.
        preserved: Owned requirements the user edited or deleted while the
            request stayed the same.
        records: Ownership decided without the resolver: a kept or declined
            request is owned while the file keeps its own requirement.
    """

    packages: tuple[str, ...]
    conflicts: tuple[MergeConflict, ...]
    resolved: tuple[MergeConflict, ...] = ()
    proposals: tuple[MergeConflict, ...] = ()
    preserved: tuple[MergeConflict, ...] = ()
    records: tuple[DependencyState, ...] = ()


def _location(group: DependencyGroup, identity: tuple[str, str]) -> MergeLocation:
    return MergeLocation(
        "pyproject.toml", ("dependencies", group.value), ":".join(identity)
    )


def preserved_requirement(
    record: DependencyState, entries: list[str]
) -> MergeConflict | None:
    """Returns the local edit or deletion of an owned requirement, if any.

    Args:
        record: The owned requirement, whose request is unchanged.
        entries: The requirements the file lists for the same identity.

    Returns:
        A ``preserved`` decision, or ``None`` when the file still lists
        exactly what the resolver wrote.
    """
    if len(entries) == 1 and normalized_requirement(
        entries[0]
    ) == normalized_requirement(record.materialized):
        return None
    local: Value = (
        entries[0] if len(entries) == 1 else list(entries) if entries else MISSING
    )
    return MergeConflict(
        _location(record.group, (record.name, record.marker)),
        ConflictReason.PRESERVED,
        ConflictSides(record.materialized, local, record.declared),
    )


def requirement_identity(content: str) -> tuple[str, str]:
    """Returns canonical package and normalized marker identity."""
    try:
        requirement = Requirement(content)
    except InvalidRequirement as e:
        raise ConfigurationError(
            "Invalid dependency requirement.", hint="Use a valid PEP 508 requirement."
        ) from e
    return canonicalize_name(requirement.name), str(
        requirement.marker
    ) if requirement.marker else ""


def normalized_requirement(content: str) -> str:
    """Normalizes requirement values without discarding extras, constraints, or sources."""
    requirement_identity(content)
    requirement = Requirement(content)
    requirement.name = canonicalize_name(requirement.name)
    requirement.extras = {canonicalize_name(extra) for extra in requirement.extras}
    return str(requirement)


def requirement_entries(data: dict[str, object], group: DependencyGroup) -> list[str]:
    """Reads supported groups, preserving include records outside selection."""
    table = data.get(
        "project" if group is DependencyGroup.MAIN else "dependency-groups", {}
    )
    if not isinstance(table, dict):
        raise ConfigurationError(
            "Invalid dependency table.",
            hint="Use TOML tables for project and dependency-groups.",
        )
    entries = table.get(
        "dependencies" if group is DependencyGroup.MAIN else group.value, []
    )
    if not isinstance(entries, list):
        raise ConfigurationError(
            "Invalid dependency group.",
            hint="Use arrays of requirements and include-group records.",
        )
    return [entry for entry in entries if isinstance(entry, str)]


def select_dependencies(
    desired: list[str],
    local: list[str],
    records: tuple[DependencyState, ...],
    group: DependencyGroup,
    *,
    overwrite: bool = False,
    proposing: bool = False,
    resolutions: Resolutions = NO_RESOLUTIONS,
) -> DependencySelection:
    """Selects safe uv requests before any resolver can reset user constraints.

    Args:
        desired: The group's requested requirements.
        local: The requirements the file lists in the group.
        records: Owned requirements.
        group: The dependency group.
        overwrite: Whether every differing request is taken.
        proposing: Whether the project existed before Protostar owned any of
            it, so each new request is a proposal that can be declined.
        resolutions: Choices settling decisions, keyed by identity.

    Returns:
        The requests to resolve and every other decision.
    """
    current: dict[tuple[str, str], list[str]] = defaultdict(list)
    incoming: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in local:
        current[requirement_identity(entry)].append(entry)
    for entry in desired:
        incoming[requirement_identity(entry)].append(entry)
    owned = {
        (r.name, r.marker): r
        for r in records
        if r.group is group and r.path == "pyproject.toml"
    }
    accepted: list[str] = []
    conflicts: list[MergeConflict] = []
    resolved: list[MergeConflict] = []
    proposals: list[MergeConflict] = []
    preserved: list[MergeConflict] = []
    kept: list[DependencyState] = []
    for identity, requests in incoming.items():
        entries = current.get(identity, [])
        record = owned.get(identity)
        location = _location(group, identity)
        if len(requests) != 1 or len(entries) > 1:
            # Several requirements for one identity can only be sorted by hand.
            conflicts.append(MergeConflict(location, ConflictReason.DIVERGED))
            continue
        request = requests[0]
        if overwrite:
            if not entries or normalized_requirement(
                entries[0]
            ) != normalized_requirement(request):
                accepted.append(request)
            continue
        if record and normalized_requirement(request) == normalized_requirement(
            record.declared
        ):
            found = preserved_requirement(record, entries)
            settled = found.settle(resolutions) if found is not None else None
            if settled is not None:
                resolved.append(settled)
                if settled.resolution is ResolutionChoice.DESIRED:
                    accepted.append(request)
            elif found is not None:
                preserved.append(found)
            continue
        if entries and normalized_requirement(entries[0]) == normalized_requirement(
            request
        ):
            continue
        if record is None and not entries:
            if proposing:
                found = MergeConflict(
                    location,
                    ConflictReason.PROPOSED,
                    ConflictSides(MISSING, MISSING, request),
                )
                settled = found.settle(resolutions)
                proposals.append(settled or found)
                if settled is not None and settled.resolution is ResolutionChoice.LOCAL:
                    # Declined: owned as requested, then deleted, so sync can restore it.
                    kept.append(
                        DependencyState(
                            "pyproject.toml", group, *identity, request, request
                        )
                    )
                    continue
            accepted.append(request)
            continue
        if (
            record
            and entries
            and normalized_requirement(entries[0])
            == normalized_requirement(record.materialized)
            and _upgrades(record.materialized, request)
        ):
            accepted.append(request)
            continue
        reason = (
            ConflictReason.UNOWNED
            if record is None
            else ConflictReason.DELETED_ANCESTOR
            if not entries
            else ConflictReason.DIVERGED
        )
        found = MergeConflict(
            location,
            reason,
            ConflictSides(
                record.declared if record else MISSING,
                entries[0] if entries else MISSING,
                request,
            ),
        )
        settled = found.settle(resolutions)
        if settled is None:
            conflicts.append(found)
            continue
        resolved.append(settled)
        if settled.resolution is ResolutionChoice.DESIRED:
            accepted.append(request)
            continue
        # Kept: the local requirement stands for the request from now on, and
        # a deleted one stays deleted as the request's materialization.
        materialized = (
            entries[0] if entries else record.materialized if record else request
        )
        kept.append(
            DependencyState("pyproject.toml", group, *identity, request, materialized)
        )
    return DependencySelection(
        tuple(accepted),
        tuple(conflicts),
        tuple(resolved),
        tuple(proposals),
        tuple(preserved),
        tuple(kept),
    )


def _upgrades(materialized: str, request: str) -> bool:
    """Returns whether a request only raises the lower bound the resolver wrote."""
    old = Requirement(materialized)
    new = Requirement(request)
    old_bounds = [
        Version(s.version)
        for s in old.specifier
        if s.operator in (">=", "==") and "*" not in s.version
    ]
    new_bounds = [
        Version(s.version)
        for s in new.specifier
        if s.operator in (">=", "==") and "*" not in s.version
    ]
    simple_old = all(
        s.operator in (">=", "==") and "*" not in s.version for s in old.specifier
    )
    simple_new = len(list(new.specifier)) <= 1 and all(
        s.operator in (">=", "==") and "*" not in s.version for s in new.specifier
    )
    return bool(
        old.url == new.url
        and simple_old
        and simple_new
        and (
            (not old_bounds and not old.url)
            or (old_bounds and new_bounds and max(new_bounds) >= max(old_bounds))
        )
    )
