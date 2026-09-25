"""Read-only reconciliation reviews consumed by transactional execution."""

import hashlib
import json
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum
from pathlib import Path
from typing import Any

from .config import UserConfig
from .documents import pyproject, vscode
from .errors import (
    ConfigurationError,
    UnmatchedResolutionError,
    UnsupportedResolutionError,
)
from .intent import DependencyGroup, ResolverFootprint
from .manifest import (
    CollisionStrategy,
    DependencyManifest,
    DiagnosticEvent,
    EnvironmentManifest,
)
from .merge import (
    MISSING,
    NO_RESOLUTIONS,
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    Resolutions,
    Value,
)
from .recipe import ProducerContribution, ToolSelection, decode_recipe
from .reconciliation import Reconciliation
from .registry import ResolvedHookRevision
from .review_workspace import CapturedInput, PresenceReader, ReviewWorkspace
from .sync_state import SyncState, serialize_state


class ExecutionPolicy(StrEnum):
    """Explicit side-effect boundary for initialization and lifecycle application."""

    INITIALIZATION = "initialization"
    LIFECYCLE = "lifecycle"


class PreparationPhase(StrEnum):
    """Initialization byte decisions separated by execution-only materialization."""

    BEFORE_INITIALIZERS = "before-initializers"
    BEFORE_RESOLVER = "before-resolver"
    BEFORE_COMMANDS = "before-commands"
    """Both batches before the resolver, for a change review, when no
    initializer creates a file the second one reads (see ``review_phase``)."""
    AFTER_RESOLVER = "after-resolver"
    COMPLETE = "complete"
    RECIPE = "recipe"


@dataclass(frozen=True)
class PreparedEdit:
    """An accepted direct byte change, never a proposed conflicted replacement."""

    path: str
    before: bytes | None
    after: bytes


@dataclass(frozen=True)
class ResolverAction:
    """Accepted requirements and conditional lock work with unknown output."""

    requirements: tuple[tuple[DependencyGroup, tuple[str, ...]], ...]
    blocked: frozenset[DependencyGroup]
    lock_required: bool
    footprint: ResolverFootprint

    def dependency_manifest(self) -> DependencyManifest:
        """Returns accepted requests for the execution-only resolver."""
        groups = dict(self.requirements)
        return DependencyManifest(
            dependencies=list(groups.get(DependencyGroup.MAIN, ())),
            dev_dependencies=list(groups.get(DependencyGroup.DEV, ())),
            docs_dependencies=list(groups.get(DependencyGroup.DOCS, ())),
            resolver_footprint=self.footprint,
        )

    @property
    def pending(self) -> bool:
        """Returns whether execution needs a resolver action."""
        return self.lock_required or any(packages for _, packages in self.requirements)


@dataclass(frozen=True)
class ResolutionRequest:
    """A choice for the conflicts one selector names.

    Attributes:
        selector: A conflict identity, or a file path that names every conflict
            in that file which offers the choice.
        choice: How to settle them.
    """

    selector: str
    choice: ResolutionChoice


def select_resolutions(
    decisions: Sequence[MergeConflict], requests: Sequence[ResolutionRequest]
) -> dict[str, ResolutionChoice]:
    """Turns selectors into choices keyed by decision identity.

    Later requests override earlier ones, so an identity can refine a
    file-wide choice. A file selector names the file's conflicts and
    proposals; a preserved deviation is restored only by its own identity,
    since it is a deliberate local edit.

    Args:
        decisions: The review's open conflicts, proposals, and preserved
            deviations.
        requests: Choices in the order given.

    Returns:
        Choices keyed by conflict identity.

    Raises:
        UnmatchedResolutionError: If a selector names no open conflict.
        UnsupportedResolutionError: If no conflict a selector names offers its
            choice.
    """
    resolutions: dict[str, ResolutionChoice] = {}
    unmatched: list[str] = []
    for request in requests:
        named = [
            decision
            for decision in decisions
            if request.selector == decision.id
            or (
                request.selector == decision.location.file
                and decision.reason is not ConflictReason.PRESERVED
            )
        ]
        if not named:
            unmatched.append(request.selector)
            continue
        chosen = [c for c in named if request.choice in c.choices]
        if not chosen:
            offered = {choice for c in named for choice in c.choices}
            raise UnsupportedResolutionError(
                request.selector,
                request.choice.value,
                tuple(c.value for c in ResolutionChoice if c in offered),
            )
        resolutions.update((conflict.id, request.choice) for conflict in chosen)
    if unmatched:
        raise UnmatchedResolutionError(tuple(unmatched))
    return resolutions


def _plain(value: Value) -> Any:
    """Returns a decoded value as JSON-ready data, with dates in ISO form."""
    if isinstance(value, dict):
        return {key: _plain(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_plain(child) for child in value]
    if isinstance(value, (date, time)):
        return value.isoformat()
    return value


def conflict_record(conflict: MergeConflict) -> dict[str, Any]:
    """Serializes a conflict, with its sides and choices, for machine output.

    Args:
        conflict: An open or settled conflict.

    Returns:
        A JSON-ready mapping; ``resolution`` appears only once it is settled.
    """
    location = conflict.location
    sides = conflict.sides

    def side(value: Value) -> dict[str, Any] | None:
        return None if value is MISSING else {"value": _plain(value)}

    record: dict[str, Any] = {
        "id": conflict.id,
        "file": location.file,
        "keys": list(location.keys),
        "identity": location.identity,
        "lines": location.lines.to_dict() if location.lines else None,
        "reason": conflict.reason.value,
        "choices": [choice.value for choice in conflict.choices],
        "sides": None
        if sides is None
        else {
            "text": sides.text,
            "base": side(sides.base),
            "local": side(sides.local),
            "desired": side(sides.desired),
        },
    }
    if conflict.resolution is not None:
        record["resolution"] = conflict.resolution.value
    return record


@dataclass(frozen=True)
class PreparedReview:
    """Immutable accepted bytes, ownership decisions, and captured workspace inputs."""

    root: Path
    hook_revisions: tuple[ResolvedHookRevision, ...]
    manifest_digest: str
    selections: tuple[ToolSelection, ...]
    producers: tuple[ProducerContribution, ...]
    policy: ExecutionPolicy
    one_shot: bool
    inputs: tuple[CapturedInput, ...]
    edits: tuple[PreparedEdit, ...]
    directories: tuple[str, ...]
    conflicts: tuple[MergeConflict, ...]
    resolved: tuple[MergeConflict, ...]
    proposals: tuple[MergeConflict, ...]
    preserved: tuple[MergeConflict, ...]
    diagnostics: tuple[DiagnosticEvent, ...]
    candidate_state: SyncState
    state_before: bytes | None
    resolver: ResolverAction
    initialization_only: tuple[tuple[str, ...], ...]
    initialization_only_ide_probe: bool
    preserve_deleted_pyproject: bool

    @property
    def decisions(self) -> tuple[MergeConflict, ...]:
        """Returns every decision a resolution can name.

        These are the open conflicts, the proposals, and the preserved
        deviations.
        """
        return (*self.conflicts, *self.proposals, *self.preserved)

    @property
    def state_changed(self) -> bool:
        """Returns whether ownership/provenance must advance."""
        return not self.one_shot and (
            serialize_state(self.candidate_state).encode() != self.state_before
        )

    @property
    def pending(self) -> bool:
        """Returns pending direct, state, resolver, or conflicting work."""
        return bool(
            self.edits
            or self.directories
            or self.conflicts
            or self.state_changed
            or self.resolver.pending
        )

    def validate_inputs(self) -> None:
        """Revalidates every captured input before any execution mutation."""
        if Path.cwd().resolve() != self.root:
            raise ConfigurationError(
                "Review workspace changed.",
                hint="Apply the review from its original project root.",
            )
        for item in self.inputs:
            item.validate(self.root)

    def to_dict(self) -> dict[str, Any]:
        """Serializes deterministic review data without fabricated resolver output."""
        return {
            "edits": [
                {
                    "path": edit.path,
                    "before": edit.before.decode() if edit.before is not None else None,
                    "after": edit.after.decode(),
                }
                for edit in self.edits
            ],
            "directories": list(self.directories),
            "conflicts": [conflict_record(conflict) for conflict in self.conflicts],
            "resolved": [conflict_record(conflict) for conflict in self.resolved],
            "proposals": [
                {"resolution": None, **conflict_record(proposal)}
                for proposal in self.proposals
            ],
            "preserved": [
                {**conflict_record(item), "deleted": deleted(item)}
                for item in self.preserved
            ],
            "state_changed": self.state_changed,
            "resolver": {
                "requirements": {
                    group.value: list(packages)
                    for group, packages in self.resolver.requirements
                },
                "lock_required": self.resolver.lock_required,
                "footprint": self.resolver.footprint.to_dict(),
                "output": "unknown" if self.resolver.pending else None,
            },
            "initialization_only": [
                list(command) for command in self.initialization_only
            ],
            "initialization_only_ide_probe": self.initialization_only_ide_probe,
            "selections": [
                {
                    "tool": selection.tool.value,
                    "enabled": selection.enabled,
                    "layer": selection.layer.value,
                }
                for selection in self.selections
            ],
            "producers": [
                {
                    "producer": item.producer,
                    "tool": item.tool.value if item.tool else None,
                    "path": list(item.path),
                }
                for item in self.producers
            ],
        }


def prepare_review(
    manifest: EnvironmentManifest,
    config: UserConfig,
    *,
    hook_revisions: tuple[ResolvedHookRevision, ...] = (),
    policy: ExecutionPolicy = ExecutionPolicy.LIFECYCLE,
    phase: PreparationPhase = PreparationPhase.COMPLETE,
    candidate_state: SyncState | None = None,
    presence: PresenceReader | None = None,
    preserve_deleted_pyproject: bool = False,
    resolutions: Resolutions = NO_RESOLUTIONS,
    partial_resolutions: bool = False,
) -> PreparedReview:
    """Computes accepted bytes using the shared kernel, without executing side effects.

    Source acquisition, tool selection, and registry acquisition precede this
    boundary. Initializers and resolvers cannot be simulated here; initialization
    prepares fresh batches around their actual execution.

    Resolutions settle conflicts, proposals, and preserved deviations by
    identity. One that names no decision raises, so a choice made for content
    that changed since is never applied elsewhere, unless
    ``partial_resolutions`` says the choices span several batches; the caller
    then checks that every one was used.
    A text hunk's resolution applies only with every other hunk in its text, so
    until those are chosen too it stays open without raising.

    Raises:
        UnmatchedResolutionError: If a resolution names no conflict.
        UnsupportedResolutionError: If a conflict does not offer its choice.
    """
    if (
        policy is ExecutionPolicy.LIFECYCLE
        and manifest.collision_strategy is CollisionStrategy.OVERWRITE
    ):
        raise ConfigurationError(
            "Lifecycle overwrite is unsupported.",
            hint="Use ordinary reconciliation for lifecycle updates.",
        )
    workspace = ReviewWorkspace(Path.cwd().resolve(), presence)
    decisions = Reconciliation(
        manifest, config, workspace, workspace, workspace, hook_revisions, resolutions
    )
    if manifest.recipe:
        decode_recipe(manifest.recipe.to_dict())
    decisions._load_state()
    if candidate_state is not None:
        decisions.candidate_state = candidate_state
    decisions._preserve_deleted_pyproject |= preserve_deleted_pyproject
    workspace.capture(Path("pyproject.toml"))
    workspace.capture(Path("uv.lock"))
    try:
        data = tomllib.loads(workspace.read_text(Path("pyproject.toml")))
        tool = data.get("tool", {})
        if not isinstance(tool, dict):
            raise ConfigurationError("Invalid pyproject tool table.")
        if "protostar" in tool:
            decode_recipe(tool["protostar"])
    except (UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(
            "Cannot read project recipe.",
            hint="Correct pyproject.toml encoding and TOML syntax.",
        ) from error
    decisions._validate_targets()
    # Validate all direct read/write targets before the first initialization batch.
    for path in manifest.target_files():
        workspace.capture(path)
    if manifest.filesystem.vcs_ignores:
        workspace.capture(Path(".gitignore"))
    if manifest.ide_settings:
        workspace.capture(Path(vscode.SETTINGS_TARGET))
    for resolver_path in manifest.dependencies.resolver_footprint.paths:
        workspace.capture(Path(resolver_path))
    if phase in (
        PreparationPhase.COMPLETE,
        PreparationPhase.BEFORE_INITIALIZERS,
        PreparationPhase.BEFORE_COMMANDS,
    ):
        decisions._create_directories()
        decisions._write_injected_files()
        decisions._write_pre_commit_config()
        decisions._write_ci_workflow()
        decisions._write_release_workflow()
        decisions._write_justfile()
    accepted = DependencyManifest()
    blocked: set[DependencyGroup] = set()
    if phase in (
        PreparationPhase.COMPLETE,
        PreparationPhase.BEFORE_RESOLVER,
        PreparationPhase.BEFORE_COMMANDS,
    ):
        decisions._append_files()
        decisions._apply_dependency_includes()
        accepted, blocked = decisions._select_dependencies()
        # Baseline convergence can be known; resolver-generated values cannot.
        decisions._materialize_dependencies(DependencyManifest(), blocked)
    if phase in (PreparationPhase.COMPLETE, PreparationPhase.AFTER_RESOLVER):
        decisions._write_ignores()
        decisions._write_docker_artifacts()
        decisions._write_ide_settings()
    # A lifecycle run writes the recipe too, which changes it only when the
    # run moved it, as sync --to moves the template's ref.
    if not manifest.one_shot and phase in (
        PreparationPhase.COMPLETE,
        PreparationPhase.RECIPE,
    ):
        decisions._write_recipe()
    edits = tuple(
        PreparedEdit(path, workspace.inputs[path].original.file_content, content)
        for path, content in sorted(workspace.contents.items())
        if content != workspace.inputs[path].original.file_content
    )
    if (
        decisions._resolution_dirty
        or accepted.dependencies
        or accepted.dev_dependencies
        or accepted.docs_dependencies
    ) and not {"pyproject.toml", "uv.lock"}.issubset(
        manifest.dependencies.resolver_footprint.paths
    ):
        raise ConfigurationError(
            "Incomplete resolver footprint.",
            hint="Declare pyproject.toml and uv.lock before resolver execution.",
        )
    requirements = tuple(
        (group, tuple(packages))
        for group, packages in (
            (DependencyGroup.MAIN, accepted.dependencies),
            (DependencyGroup.DEV, accepted.dev_dependencies),
            (DependencyGroup.DOCS, accepted.docs_dependencies),
        )
    )
    conflicts = tuple(
        sorted(
            (
                event.conflict
                for event in decisions.diagnostics
                if event.conflict is not None
            ),
            key=_conflict_order,
        )
    )
    resolved = tuple(
        sorted(
            (
                event.resolved
                for event in decisions.diagnostics
                if event.resolved is not None
            ),
            key=_conflict_order,
        )
    )
    proposals = tuple(sorted(decisions.proposals, key=_conflict_order))
    preserved = tuple(sorted(decisions.preserved, key=_conflict_order))
    if not partial_resolutions:
        check_resolutions(resolutions, (*conflicts, *resolved, *proposals))
    return PreparedReview(
        workspace.workspace_root,
        hook_revisions,
        manifest_digest(manifest),
        manifest.selections,
        manifest.producer_contributions,
        policy,
        manifest.one_shot,
        tuple(workspace.inputs[path] for path in sorted(workspace.inputs)),
        edits,
        tuple(sorted(workspace.directories)),
        conflicts,
        resolved,
        proposals,
        preserved,
        tuple(decisions.diagnostics),
        decisions.candidate_state,
        decisions._state_bytes,
        ResolverAction(
            requirements,
            frozenset(blocked),
            decisions._resolution_dirty,
            manifest.dependencies.resolver_footprint,
        ),
        tuple(
            tuple(task.command)
            for task in (
                *manifest.tasks.system_tasks,
                *manifest.tasks.post_install_tasks,
            )
        ),
        bool(manifest.tooling.ide_extensions),
        decisions._preserve_deleted_pyproject,
    )


def _conflict_order(
    conflict: MergeConflict,
) -> tuple[str, tuple[str, ...], str, int, str]:
    """Orders conflicts by file, then position within it."""
    location = conflict.location
    return (
        location.file,
        location.keys,
        location.identity or "",
        location.lines.start if location.lines else 0,
        conflict.reason.value,
    )


def check_resolutions(
    resolutions: Resolutions, decisions: Sequence[MergeConflict]
) -> None:
    """Rejects resolutions that name no decision or a choice it does not offer.

    Args:
        resolutions: Choices keyed by identity.
        decisions: Every decision the choices could name, open or settled.

    Raises:
        UnmatchedResolutionError: If a resolution names no decision.
        UnsupportedResolutionError: If a decision does not offer its choice.
    """
    found = {decision.id: decision for decision in decisions}
    unmatched = tuple(identity for identity in resolutions if identity not in found)
    if unmatched:
        raise UnmatchedResolutionError(unmatched)
    for identity, choice in resolutions.items():
        choices = found[identity].choices
        if choice not in choices:
            raise UnsupportedResolutionError(
                identity, choice.value, tuple(c.value for c in choices)
            )


def deleted(decision: MergeConflict) -> bool:
    """Returns whether a preserved deviation is a deletion rather than an edit."""
    return decision.sides is not None and decision.sides.local is MISSING


def review_phase(manifest: EnvironmentManifest) -> PreparationPhase:
    """Returns how much of an initialization a change review can show.

    The batch after the initializers merges configuration and selects
    dependencies. When no initializer creates a file it reads, as in a project
    that already has its ``pyproject.toml``, its bytes are known before any
    command runs, so the review shows it too and its decisions can be made
    there.

    Args:
        manifest: The planned initialization.

    Returns:
        ``BEFORE_COMMANDS`` when both batches are known, else
        ``BEFORE_INITIALIZERS``.
    """
    created = {
        path for task in manifest.tasks.system_tasks for path in task.owned_files
    }
    read = {
        *manifest.filesystem.structured,
        *manifest.filesystem.regions,
        pyproject.TARGET,
    }
    if created & read:
        return PreparationPhase.BEFORE_INITIALIZERS
    return PreparationPhase.BEFORE_COMMANDS


def manifest_digest(manifest: EnvironmentManifest) -> str:
    """Fingerprints the captured desired revision without storing executable plans."""
    return hashlib.sha256(
        json.dumps(
            {
                "manifest": manifest.to_dict(),
                "recipe": manifest.recipe.to_dict() if manifest.recipe else None,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
