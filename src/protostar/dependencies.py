"""Dependency resolution and package installation via uv."""

import logging
from collections import defaultdict
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from .errors import ConfigurationError
from .intent import DependencyGroup
from .manifest import DependencyManifest
from .merge import ConflictReason, MergeConflict, MergeLocation
from .sync_state import DependencyState
from .system import ProcessRunner

logger = logging.getLogger("protostar")

__all__ = ["DependencyGroup", "install_dependencies"]


def _install_group(
    packages: list[str],
    group: DependencyGroup,
    process_runner: ProcessRunner,
) -> None:
    """Installs a specific group of packages using uv add.

    Raises:
        CommandExecutionError | CommandTimeoutError: If installation fails.
    """
    if not packages:
        return

    cmd = ["uv", "add", *group.cli_args, *packages]
    logger.info(f"Resolving and installing {len(packages)} {group.label} dependencies")
    process_runner.run(cmd, timeout=600)


def install_dependencies(
    dependencies_manifest: DependencyManifest,
    process_runner: ProcessRunner,
) -> None:
    """Installs queued dependencies using uv.

    Raises:
        CommandExecutionError | CommandTimeoutError: If any installation fails.
    """
    if (
        not dependencies_manifest.dependencies
        and not dependencies_manifest.dev_dependencies
        and not dependencies_manifest.docs_dependencies
    ):
        return

    _install_group(
        dependencies_manifest.dependencies, DependencyGroup.MAIN, process_runner
    )
    _install_group(
        dependencies_manifest.dev_dependencies, DependencyGroup.DEV, process_runner
    )
    _install_group(
        dependencies_manifest.docs_dependencies, DependencyGroup.DOCS, process_runner
    )


@dataclass(frozen=True)
class DependencySelection:
    """Accepted resolver requests and preserved ownership conflicts."""

    packages: tuple[str, ...]
    conflicts: tuple[MergeConflict, ...]


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
) -> DependencySelection:
    """Selects safe uv requests before any resolver can reset user constraints."""
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
    for identity, requests in incoming.items():
        entries = current.get(identity, [])
        record = owned.get(identity)
        reason = ConflictReason.DIVERGED
        if len(requests) != 1 or len(entries) > 1:
            pass
        elif overwrite:
            if not entries or normalized_requirement(
                entries[0]
            ) != normalized_requirement(requests[0]):
                accepted.append(requests[0])
            continue
        elif (
            record
            and normalized_requirement(requests[0])
            == normalized_requirement(record.declared)
        ) or (
            entries
            and normalized_requirement(entries[0])
            == normalized_requirement(requests[0])
        ):
            continue
        elif record is None and not entries:
            accepted.append(requests[0])
            continue
        elif (
            record
            and entries
            and normalized_requirement(entries[0])
            == normalized_requirement(record.materialized)
        ):
            old = Requirement(record.materialized)
            new = Requirement(requests[0])
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
                s.operator in (">=", "==") and "*" not in s.version
                for s in old.specifier
            )
            simple_new = len(list(new.specifier)) <= 1 and all(
                s.operator in (">=", "==") and "*" not in s.version
                for s in new.specifier
            )
            if (
                old.url == new.url
                and simple_old
                and simple_new
                and (
                    (not old_bounds and not old.url)
                    or (new_bounds and max(new_bounds) >= max(old_bounds))
                )
            ):
                accepted.append(requests[0])
                continue
        elif record is None:
            reason = ConflictReason.UNOWNED
        elif not entries:
            reason = ConflictReason.DELETED_ANCESTOR
        conflicts.append(
            MergeConflict(
                MergeLocation(
                    "pyproject.toml", ("dependencies", group.value), ":".join(identity)
                ),
                reason,
            )
        )
    return DependencySelection(tuple(accepted), tuple(conflicts))
