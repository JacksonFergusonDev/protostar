"""What init changes, shared by the recipe editor's preview and the change review.

Both screens plan a draft, prepare its first file batch, and label each
planned path the same way. The preview only shows the result; the review
settles its decisions. Planning and preparation read the workspace, so
callers run them off the main thread.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rich.text import Text

from protostar.cli.ui import path_style, planned_paths
from protostar.config import UserConfig
from protostar.init_draft import InitDraft, resolve_init
from protostar.manifest import EnvironmentManifest
from protostar.merge import ConflictReason, MergeConflict, ResolutionChoice
from protostar.models import InitRequest
from protostar.orchestrator import Orchestrator
from protostar.preparation import (
    ExecutionPolicy,
    PreparedEdit,
    PreparedReview,
    prepare_review,
    review_phase,
)
from protostar.registry import ResolvedHookRevision, resolve_hook_revisions

__all__ = [
    "FOLDER",
    "Change",
    "Entry",
    "Review",
    "classify",
    "count",
    "entry_label",
    "hook_snapshot",
    "plan_draft",
    "prepare_draft",
    "summary",
]


class Change(StrEnum):
    """What happens to a planned path before any command runs."""

    NEW = "new"
    MODIFIED = "modified"
    REMOVED = "removed"
    CONFLICT = "conflict"
    EXISTS = "existing"
    LATER = "after setup"


_STYLES = {
    Change.NEW: "green",
    Change.MODIFIED: "yellow",
    Change.REMOVED: "red",
    Change.CONFLICT: "red",
    Change.EXISTS: "dim",
    Change.LATER: "dim",
}

FOLDER = path_style("", directory=True)


@dataclass(frozen=True)
class Entry:
    """One planned path and what the files written before any command do to it.

    Its conflicts are open or, once a choice settled them, resolved. Its
    proposals are changes into content the user already had, applied unless
    kept out.
    """

    path: str
    change: Change
    directory: bool = False
    edit: PreparedEdit | None = None
    conflicts: tuple[MergeConflict, ...] = ()
    creator: tuple[str, ...] | None = None
    merged: bool = False

    @property
    def open(self) -> tuple[MergeConflict, ...]:
        """Returns the conflicts no choice has settled."""
        return tuple(
            c
            for c in self.conflicts
            if c.resolution is None and c.reason is not ConflictReason.PROPOSED
        )

    @property
    def proposals(self) -> tuple[MergeConflict, ...]:
        """Returns the changes into this file's existing content."""
        return tuple(c for c in self.conflicts if c.reason is ConflictReason.PROPOSED)


@dataclass(frozen=True)
class Review:
    """A planned draft and its first file batch."""

    request: InitRequest
    manifest: EnvironmentManifest
    prepared: PreparedReview
    entries: tuple[Entry, ...]


def classify(
    manifest: EnvironmentManifest, prepared: PreparedReview
) -> tuple[Entry, ...]:
    """Sorts every planned path by what the first file batch does to it.

    Only the first batch's bytes are known before commands run. A path it
    leaves alone either exists already, or is written later from command
    output. Reads the workspace, so it runs off the main thread.

    Args:
        manifest: The planned manifest.
        prepared: The first file batch prepared from it.

    Returns:
        One entry per planned path, sorted by path.
    """
    edits = {edit.path: edit for edit in prepared.edits}
    conflicts: dict[str, list[MergeConflict]] = {}
    for conflict in (*prepared.conflicts, *prepared.resolved, *prepared.proposals):
        conflicts.setdefault(conflict.location.file, []).append(conflict)
    tasks = (*manifest.tasks.system_tasks, *manifest.tasks.post_install_tasks)
    creators = {
        path: tuple(task.command) for task in tasks for path in task.owned_files
    }
    written = {path.as_posix() for path in manifest.written_files()}
    paths, directories = planned_paths(manifest)
    entries: list[Entry] = []
    for path in sorted({*paths, *edits, *prepared.directories, *conflicts}):
        edit = edits.get(path)
        if edit is not None:
            change = (
                Change.NEW
                if edit.before is None
                else Change.REMOVED
                if edit.after is None
                else Change.MODIFIED
            )
        elif path in prepared.directories:
            change = Change.NEW
        elif any(c.resolution is None for c in conflicts.get(path, ())):
            change = Change.CONFLICT
        elif Path(path).exists():
            change = Change.EXISTS
        else:
            change = Change.LATER
        entries.append(
            Entry(
                path,
                change,
                path in directories or path in prepared.directories,
                edit,
                tuple(conflicts.get(path, ())),
                creators.get(path),
                path in written,
            )
        )
    return tuple(entries)


def plan_draft(
    draft: InitDraft, config: UserConfig
) -> tuple[InitRequest, EnvironmentManifest]:
    """Resolves a draft and plans it, without writing anything.

    Args:
        draft: The init draft.
        config: The user's configuration.

    Returns:
        The resolved request and its planned manifest.
    """
    modules, request = resolve_init(draft, config)
    return request, Orchestrator(modules, config, request=request).plan()


def hook_snapshot(manifest: EnvironmentManifest) -> tuple[ResolvedHookRevision, ...]:
    """Takes the registry snapshot a planned draft's hooks are pinned from.

    Take it once per session and pass it on: execution writes the pins the
    preview and the review showed. It fetches, so run it off the main thread.

    Args:
        manifest: The planned manifest.

    Returns:
        One revision per remote hook, or nothing when no hooks are wanted.
    """
    return resolve_hook_revisions() if manifest.tooling.wants_hooks else ()


def prepare_draft(
    request: InitRequest,
    manifest: EnvironmentManifest,
    config: UserConfig,
    hook_revisions: tuple[ResolvedHookRevision, ...],
    choices: Mapping[str, ResolutionChoice],
) -> Review:
    """Prepares a planned draft's first file batch and sorts its paths.

    Args:
        request: The resolved request.
        manifest: Its planned manifest.
        config: The user's configuration.
        hook_revisions: The registry snapshot execution will write.
        choices: Resolutions keyed by conflict id; ones the plan no longer
            has lapse.

    Returns:
        The review of what init changes.
    """
    # A project whose files no command creates shows its merges here too.
    phase = review_phase(manifest)

    def prepared_with(resolutions: Mapping[str, ResolutionChoice]) -> PreparedReview:
        return prepare_review(
            manifest,
            config,
            hook_revisions=hook_revisions,
            policy=ExecutionPolicy.INITIALIZATION,
            phase=phase,
            resolutions=resolutions,
        )

    prepared = prepared_with({})
    # Choices made for decisions a changed plan no longer has lapse.
    kept = {c.id: choices[c.id] for c in prepared.decisions if c.id in choices}
    if kept:
        prepared = prepared_with(kept)
    return Review(request, manifest, prepared, classify(manifest, prepared))


def count(number: int, noun: str) -> str:
    """Returns ``number`` with ``noun``, plural unless it is one."""
    return f"{number} {noun}{'' if number == 1 else 's'}"


def summary(review: Review) -> Text:
    """Counts the planned files by change, then the packages and commands.

    Args:
        review: The prepared review.

    Returns:
        One line for the screen's subtitle.
    """
    counts = Counter(
        entry.change
        for entry in review.entries
        if not (entry.directory and entry.change is Change.EXISTS)
    )
    dependencies = review.manifest.dependencies
    tasks = review.manifest.tasks
    parts = [f"{counts[change]} {change.value}" for change in Change if counts[change]]
    parts.append(
        count(
            len(dependencies.dependencies)
            + len(dependencies.dev_dependencies)
            + len(dependencies.docs_dependencies),
            "package",
        )
    )
    parts.append(
        count(len(tasks.system_tasks) + len(tasks.post_install_tasks), "command")
    )
    proposals = review.prepared.proposals
    if proposals:
        kept = sum(p.resolution is ResolutionChoice.LOCAL for p in proposals)
        changes = count(len(proposals), "change") + " to your files"
        parts.append(f"{changes} ({kept} kept out)" if kept else changes)
    return Text(" · ".join(parts))


def entry_label(entry: Entry) -> Text:
    """Labels a planned path with what init does to it.

    Args:
        entry: The planned path.

    Returns:
        The path's name, then its change and any open or settled decisions.
    """
    name = entry.path.rsplit("/", 1)[-1] + ("/" if entry.directory else "")
    marker = (
        "" if entry.directory and entry.change is Change.EXISTS else entry.change.value
    )
    if entry.open and entry.change is not Change.CONFLICT:
        marker += " · conflict"
    elif any(c.reason is not ConflictReason.PROPOSED for c in entry.conflicts) and (
        not entry.open
    ):
        marker += " · resolved"
    if entry.proposals:
        kept = sum(p.resolution is ResolutionChoice.LOCAL for p in entry.proposals)
        marker += f" · {kept}/{len(entry.proposals)} kept out" if kept else ""
    # Color here means change, so only directories keep their kind's color.
    return Text.assemble(
        (name, FOLDER if entry.directory else ""),
        (f"  {marker}", _STYLES[entry.change]) if marker else "",
    )
