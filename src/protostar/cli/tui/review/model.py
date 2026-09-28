"""What init changes, shared by the recipe editor's preview and the change review.

Both screens plan a draft, prepare its first file batch, and label each
planned path the same way. The preview only shows the result; the review
settles its decisions. Planning and preparation read the workspace, so
callers run them off the main thread.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rich.text import Text
from rich.tree import Tree

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
    "entry_tree",
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


# Color says what needs you, not how much changed: modifying a file is the
# expected outcome, and a conflict is a choice in the accent, never a failure.
_STYLES = {
    Change.NEW: "green",
    Change.MODIFIED: "",
    Change.REMOVED: "red",
    Change.CONFLICT: "cyan",
    Change.EXISTS: "dim",
    Change.LATER: "dim",
}
_DECISION = "cyan"

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


def hook_snapshot() -> tuple[ResolvedHookRevision, ...]:
    """Takes the registry snapshot hooks are pinned from.

    Take it once per session and pass it on: execution writes the pins the
    preview and the review showed. It fetches, so run it off the main thread.

    Returns:
        One revision per remote hook, with fallbacks when the registry is
        unreachable.
    """
    return resolve_hook_revisions()


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
    # A file with an open conflict counts by its change; the conflicts count
    # the decisions, as the review's choices do.
    parts = [
        f"{counts[change]} {change.value}"
        for change in Change
        if counts[change] and change is not Change.CONFLICT
    ]
    if conflicts := sum(len(entry.open) for entry in review.entries):
        parts.append(count(conflicts, "conflict"))
    proposals = review.prepared.proposals
    if proposals:
        kept = sum(p.resolution is ResolutionChoice.LOCAL for p in proposals)
        changes = count(len(proposals), "change") + " to your files"
        parts.append(f"{changes} ({kept} kept out)" if kept else changes)
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
    return Text(" · ".join(parts))


def entry_label(entry: Entry) -> Text:
    """Labels a planned path with what init does to it.

    Args:
        entry: The planned path.

    Returns:
        The path's name, then its change and any open or settled decisions.
    """
    name = entry.path.rsplit("/", 1)[-1] + ("/" if entry.directory else "")
    style = _STYLES[entry.change]
    marker: list[tuple[str, str]] = []
    if not (entry.directory and entry.change is Change.EXISTS):
        marker.append((entry.change.value, style))
    if entry.open and entry.change is not Change.CONFLICT:
        marker.append((" · conflict", _DECISION))
    elif any(c.reason is not ConflictReason.PROPOSED for c in entry.conflicts) and (
        not entry.open
    ):
        marker.append((" · resolved", style))
    if entry.proposals:
        kept = sum(p.resolution is ResolutionChoice.LOCAL for p in entry.proposals)
        if kept:
            marker.append((f" · {kept}/{len(entry.proposals)} kept out", style))
    # Color here means change, so only directories keep their kind's color.
    return Text.assemble(
        (name, FOLDER if entry.directory else ""),
        *((("  ", ""), *marker) if marker else ()),
    )


def entry_tree(entries: Sequence[Entry]) -> Tree:
    """Draws the planned paths as a static tree, each labelled with its change.

    Args:
        entries: The review's entries, sorted by path.

    Returns:
        A tree rooted at the workspace.
    """
    tree = Tree(
        Text.assemble((".", "bold blue"), (" (Workspace Root)", "dim")),
        guide_style="bright_black",
    )
    nodes: dict[str, Tree] = {"": tree}
    for entry in entries:
        parts = entry.path.split("/")
        parent = ""
        for index in range(1, len(parts)):
            folder = "/".join(parts[:index])
            if folder not in nodes:
                nodes[folder] = nodes[parent].add(Text(f"{parts[index - 1]}/", FOLDER))
            parent = folder
        nodes[entry.path] = nodes[parent].add(entry_label(entry))
    return tree
