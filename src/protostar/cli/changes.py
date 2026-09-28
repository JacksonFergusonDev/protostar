"""What init changes: one model for the recipe preview, the change review, and --dry-run.

Each plans a draft, prepares its first file batch, and labels every planned
path the same way. The recipe preview and ``init --dry-run`` only show the
result; the change review settles its decisions. Planning and preparation
read the workspace, so the TUI runs them off the main thread.
"""

import shlex
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text
from rich.tree import Tree

from protostar.cli import ui
from protostar.cli.ui import path_style, planned_paths
from protostar.config import UserConfig
from protostar.init_draft import InitDraft, resolve_init
from protostar.intent import DependencyGroup
from protostar.manifest import EnvironmentManifest
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    describe_location,
)
from protostar.models import InitRequest
from protostar.orchestrator import Orchestrator
from protostar.preparation import (
    ExecutionPolicy,
    PreparedEdit,
    PreparedReview,
    prepare_review,
    review_phase,
)
from protostar.registry import (
    ResolvedHookRevision,
    hook_registry_unreachable,
    resolve_hook_revisions,
)

__all__ = [
    "FOLDER",
    "NETWORK_NOTE",
    "SETTLED",
    "Change",
    "Entry",
    "HookSnapshot",
    "Review",
    "changes_to_your_files",
    "classify",
    "count",
    "entries_record",
    "entry_label",
    "entry_tree",
    "hook_snapshot",
    "indented_lines",
    "pending_entries",
    "plan_draft",
    "prepare_draft",
    "print_dry_run",
    "steps_text",
    "summary",
    "where",
]


class Change(StrEnum):
    """What happens to a planned path before any command runs."""

    NEW = "new"
    MODIFIED = "modified"
    REMOVED = "removed"
    CONFLICT = "conflict"
    EXISTS = "existing"
    LATER = "after-setup"

    @property
    def label(self) -> str:
        """Returns how the change reads beside a path."""
        return self.value.replace("-", " ")


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

SETTLED = {
    ResolutionChoice.LOCAL: "kept local content",
    ResolutionChoice.DESIRED: "took the update",
    ResolutionChoice.BOTH: "kept both",
}
"""How each choice settled a conflict, for the lines that list them."""


def where(conflict: MergeConflict) -> str:
    """Returns the file, position, and identity of a conflict on one line."""
    parts = (
        conflict.location.file,
        describe_location(conflict.location),
        # A requirement's identity is its package and marker.
        (conflict.location.identity or "").rstrip(":"),
    )
    return " ".join(part for part in parts if part)


@dataclass(frozen=True)
class Entry:
    """One planned path and what the files written before any command do to it.

    Its conflicts are open or, once a choice settled them, resolved. Its
    proposals are changes into content the user already had, applied unless
    kept out. Its preserved edits are the user's own, kept under an update
    that has not changed there.
    """

    path: str
    change: Change
    directory: bool = False
    edit: PreparedEdit | None = None
    conflicts: tuple[MergeConflict, ...] = ()
    creator: tuple[str, ...] | None = None
    merged: bool = False
    preserved: tuple[MergeConflict, ...] = ()

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
    preserved: dict[str, list[MergeConflict]] = {}
    for item in prepared.preserved:
        preserved.setdefault(item.location.file, []).append(item)
    tasks = (*manifest.tasks.system_tasks, *manifest.tasks.post_install_tasks)
    creators = {
        path: tuple(task.command) for task in tasks for path in task.owned_files
    }
    written = {path.as_posix() for path in manifest.written_files()}
    paths, directories = planned_paths(manifest)
    entries: list[Entry] = []
    for path in sorted({*paths, *edits, *prepared.directories, *conflicts, *preserved}):
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
                tuple(preserved.get(path, ())),
            )
        )
    return tuple(entries)


_PENDING = frozenset({Change.NEW, Change.MODIFIED, Change.REMOVED, Change.CONFLICT})


def pending_entries(entries: Sequence[Entry]) -> tuple[Entry, ...]:
    """Keeps the paths a sync changes or asks about.

    A managed file the update leaves alone would otherwise fill the tree as
    ``existing``, so only a change or a decision earns a path its place.

    Args:
        entries: Every classified path, sorted by path.

    Returns:
        The paths with a change, a conflict, a proposal, or a preserved edit.
    """
    return tuple(
        entry
        for entry in entries
        if entry.change in _PENDING or entry.conflicts or entry.preserved
    )


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


NETWORK_NOTE = (
    "Protostar couldn't reach the network. Installing packages needs it unless "
    "they're already in uv's cache."
)
"""Shown before applying when the registry fetch never connected."""


@dataclass(frozen=True)
class HookSnapshot:
    """The registry snapshot hooks are pinned from, and whether it connected.

    Attributes:
        revisions: One revision per remote hook, with fallbacks when the
            registry couldn't be read.
        unreachable: Whether the fetch never reached a server, a sign that
            installing packages will fail too.
    """

    revisions: tuple[ResolvedHookRevision, ...]
    unreachable: bool

    def pins(self, manifest: EnvironmentManifest) -> tuple[ResolvedHookRevision, ...]:
        """Returns the revisions a planned draft pins: none unless it wants hooks.

        Args:
            manifest: The planned manifest.

        Returns:
            The revisions, or nothing when the draft has no hooks.
        """
        return self.revisions if manifest.tooling.wants_hooks else ()


def hook_snapshot() -> HookSnapshot:
    """Takes the registry snapshot hooks are pinned from.

    Take it once per session and pass it on: execution writes the pins the
    preview and the review showed. It fetches, so run it off the main thread.

    Returns:
        The snapshot, and whether its fetch reached the network.
    """
    return HookSnapshot(resolve_hook_revisions(), hook_registry_unreachable())


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
        f"{counts[change]} {change.label}"
        for change in Change
        if counts[change] and change is not Change.CONFLICT
    ]
    if conflicts := sum(len(entry.open) for entry in review.entries):
        parts.append(count(conflicts, "conflict"))
    if proposals := review.prepared.proposals:
        parts.append(changes_to_your_files(proposals))
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


def changes_to_your_files(proposals: Sequence[MergeConflict]) -> str:
    """Counts the proposals, and how many were kept out, for a summary line."""
    kept = sum(p.resolution is ResolutionChoice.LOCAL for p in proposals)
    changes = count(len(proposals), "change") + " to your files"
    return f"{changes} ({kept} kept out)" if kept else changes


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
        marker.append((entry.change.label, style))
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
    if entry.preserved:
        marker.append((f" · {count(len(entry.preserved), 'kept edit')}", "dim"))
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


def indented_lines(lines: Sequence[str], style: str = "") -> list[RenderableType]:
    """Indents each line; a wrapped line continues under its own start."""
    return [Padding(Text(line, style), (0, 0, 0, 2)) for line in lines]


def steps_text(manifest: EnvironmentManifest) -> RenderableType:
    """Lists the commands and package installs that follow the first batch.

    Args:
        manifest: The planned manifest.

    Returns:
        Commands, packages by group, the commands that run after install, and
        the steps planning skipped, such as one whose tool is not installed.
    """
    dependencies = manifest.dependencies
    packages = (
        (DependencyGroup.MAIN, dependencies.dependencies),
        (DependencyGroup.DEV, dependencies.dev_dependencies),
        (DependencyGroup.DOCS, dependencies.docs_dependencies),
    )
    sections = (
        (
            "Commands",
            [shlex.join(task.command) for task in manifest.tasks.system_tasks],
        ),
        (
            "Packages",
            [f"{group}: {', '.join(names)}" for group, names in packages if names],
        ),
        (
            "After install",
            [shlex.join(task.command) for task in manifest.tasks.post_install_tasks],
        ),
        ("Skipped", [event.message for event in manifest.diagnostics]),
    )
    parts: list[RenderableType] = []
    for title, lines in sections:
        if lines:
            parts.append(Text(title, style="bold"))
            parts.extend(indented_lines(lines))
    return Group(*parts) if parts else Text("No commands or packages.", style="dim")


def entries_record(entries: Sequence[Entry]) -> list[dict[str, Any]]:
    """Serializes each planned path and its change for the dry-run payload.

    Args:
        entries: The review's entries, sorted by path.

    Returns:
        One record per path, sorted by path: its change, whether it is a
        directory, and the ids of its conflicts and proposals.
    """
    return [
        {
            "path": entry.path,
            "change": entry.change.value,
            "directory": entry.directory,
            "conflicts": [conflict.id for conflict in entry.open],
            "proposals": [proposal.id for proposal in entry.proposals],
        }
        for entry in entries
    ]


def print_dry_run(review: Review, *, unreachable: bool = False) -> None:
    """Prints what an init would change, the same way the change review shows it.

    Args:
        review: The prepared review of the planned init.
        unreachable: Whether the registry fetch never reached the network.
    """
    manifest = review.manifest
    sections: list[tuple[str, RenderableType]] = [
        ("Summary", summary(review)),
    ]
    if review.entries:
        sections.append(("Files", entry_tree(review.entries)))
    sections.append(("Commands & packages", steps_text(manifest)))
    if lines := _decision_lines(review):
        sections.append(("Decisions", Group(*lines)))
    for title, body in sections:
        ui.console.print()
        ui.console.print(ui.heading(title))
        ui.console.print(ui.indented(body))
    ui.console.print()
    if unreachable:
        ui.console.print(Text(NETWORK_NOTE, "yellow"))
    if manifest.collisions and manifest.collision_strategy is None:
        ui.console.print(
            Text(
                "Files already exist, so a run needs --force-merge or "
                "--force-replace; this shows a merge.",
                "yellow",
            )
        )
    ui.console.print(Text("No changes were made to your system.", "dim"))


def _decision_lines(review: Review) -> list[Text]:
    """One line per conflict and proposal, with the id that settles it.

    A conflict or proposal ``--resolve`` settled says how it was settled.
    """
    prepared = review.prepared
    lines = [
        Text.assemble(
            (f"Conflict {conflict.id}: ", "cyan"),
            (where(conflict), "bold"),
            f": {conflict.reason.value}; your version is kept.",
        )
        for conflict in prepared.conflicts
    ]
    lines.extend(
        Text.assemble(
            (f"Resolved {conflict.id}: ", "bold"),
            (where(conflict), "bold"),
            f": {SETTLED[cast(ResolutionChoice, conflict.resolution)]}.",
        )
        for conflict in prepared.resolved
    )
    lines.extend(
        Text.assemble(
            (f"Proposed {proposal.id}: ", "bold"),
            (where(proposal), "bold"),
            ": kept out; your content stays."
            if proposal.resolution is ResolutionChoice.LOCAL
            else ": applies to content you already have.",
        )
        for proposal in prepared.proposals
    )
    return lines
