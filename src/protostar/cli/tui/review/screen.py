"""The first file batch, the steps after it, and the collision and trust decisions."""

import asyncio
import shlex
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    RadioButton,
    RadioSet,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from protostar.cli.reviews import unified_diff
from protostar.cli.ui import path_style, planned_paths, untrusted_commands
from protostar.config import UserConfig
from protostar.errors import ProtostarError
from protostar.init_draft import InitDecision, InitDraft, resolve_init
from protostar.intent import DependencyGroup
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.merge import MergeConflict, describe_location
from protostar.models import InitRequest
from protostar.orchestrator import Orchestrator
from protostar.preparation import (
    ExecutionPolicy,
    PreparationPhase,
    PreparedEdit,
    PreparedReview,
    prepare_review,
)
from protostar.registry import ResolvedHookRevision, resolve_hook_revisions

from ..chrome import Heading, Headline, Masthead, Panel
from ..conflicts.sides import diff_text
from ..keys import (
    MOVE,
    ActionBar,
    Choice,
    KeyboardScreen,
    KeyRows,
    Toggle,
    key_label,
)


class Change(StrEnum):
    """What happens to a planned path before any command runs."""

    NEW = "new"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    EXISTS = "existing"
    LATER = "after setup"


_STYLES = {
    Change.NEW: "green",
    Change.MODIFIED: "yellow",
    Change.CONFLICT: "red",
    Change.EXISTS: "dim",
    Change.LATER: "dim",
}

_FOLDER = path_style("", directory=True)


@dataclass(frozen=True)
class Entry:
    """One planned path and what the first file batch does to it."""

    path: str
    change: Change
    directory: bool = False
    edit: PreparedEdit | None = None
    conflicts: tuple[MergeConflict, ...] = ()
    creator: tuple[str, ...] | None = None


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
    for conflict in prepared.conflicts:
        conflicts.setdefault(conflict.location.file, []).append(conflict)
    creators = {
        path: tuple(task.command)
        for task in manifest.tasks.system_tasks
        for path in task.owned_files
    }
    paths, directories = planned_paths(manifest)
    entries: list[Entry] = []
    for path in sorted({*paths, *edits, *prepared.directories, *conflicts}):
        edit = edits.get(path)
        if edit is not None:
            change = Change.NEW if edit.before is None else Change.MODIFIED
        elif path in prepared.directories:
            change = Change.NEW
        elif path in conflicts:
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
            )
        )
    return tuple(entries)


def _plan(
    draft: InitDraft, config: UserConfig
) -> tuple[InitRequest, EnvironmentManifest]:
    modules, request = resolve_init(draft, config)
    return request, Orchestrator(modules, config, request=request).plan()


def _prepare(
    request: InitRequest,
    manifest: EnvironmentManifest,
    config: UserConfig,
    hook_revisions: tuple[ResolvedHookRevision, ...],
) -> Review:
    prepared = prepare_review(
        manifest,
        config,
        hook_revisions=hook_revisions,
        policy=ExecutionPolicy.INITIALIZATION,
        phase=PreparationPhase.BEFORE_INITIALIZERS,
    )
    return Review(request, manifest, prepared, classify(manifest, prepared))


def describe(entry: Entry) -> RenderableType:
    """Renders an entry's accepted bytes, or says why none can be shown yet.

    Args:
        entry: The planned path to describe.

    Returns:
        Any conflicts kept as they are, then the diff or a note.
    """
    parts: list[RenderableType] = []
    for conflict in entry.conflicts:
        where = describe_location(conflict.location)
        reason = conflict.reason.value
        if conflict.location.lines is not None:
            # Both sides edited these lines, so the whole file is kept.
            message = f"{where[:1].upper()}{where[1:]}: your edit is kept ({reason})."
        else:
            message = f"Your version of {where or 'the file'} is kept ({reason})."
        parts.append(Text(message, "red"))
    if entry.edit is not None:
        parts.append(diff_text(unified_diff(entry.edit)))
    elif entry.directory:
        parts.append(
            Text("A new directory." if entry.change is Change.NEW else "Exists.")
        )
    elif entry.change is Change.EXISTS:
        parts.append(
            Text(
                "Already exists. Nothing is written to it before setup; a later "
                "step may merge Protostar's settings into it."
            )
        )
    elif entry.change is Change.LATER:
        origin = (
            f"Created by {shlex.join(entry.creator)}, then Protostar merges its "
            "settings into it."
            if entry.creator
            else "Written after the commands and packages run."
        )
        parts.append(
            Text(
                f"{origin} Its content depends on their output, so it can't be shown yet."
            )
        )
    return Group(*parts)


def _indented(lines: Sequence[str], style: str = "") -> list[RenderableType]:
    # Padding keeps a wrapped command's continuation under its first line.
    return [Padding(Text(line, style), (0, 0, 0, 2)) for line in lines]


def steps_text(manifest: EnvironmentManifest) -> RenderableType:
    """Lists the commands and package installs that follow the first batch.

    Args:
        manifest: The planned manifest.

    Returns:
        Commands, packages by group, and the commands that run after install.
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
    )
    parts: list[RenderableType] = []
    for title, lines in sections:
        if lines:
            parts.append(Text(title, style="bold"))
            parts.extend(_indented(lines))
    return Group(*parts) if parts else Text("No commands or packages.", style="dim")


def _count(number: int, noun: str) -> str:
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
        _count(
            len(dependencies.dependencies)
            + len(dependencies.dev_dependencies)
            + len(dependencies.docs_dependencies),
            "package",
        )
    )
    parts.append(
        _count(len(tasks.system_tasks) + len(tasks.post_install_tasks), "command")
    )
    return Text(" · ".join(parts))


def _label(entry: Entry) -> Text:
    name = entry.path.rsplit("/", 1)[-1] + ("/" if entry.directory else "")
    marker = (
        "" if entry.directory and entry.change is Change.EXISTS else entry.change.value
    )
    if entry.conflicts and entry.change is not Change.CONFLICT:
        marker += " · conflict"
    # Color here means change, so only directories keep their kind's color.
    return Text.assemble(
        (name, _FOLDER if entry.directory else ""),
        (f"  {marker}", _STYLES[entry.change]) if marker else "",
    )


def _trust_text(commands: tuple[tuple[str, ...], ...]) -> RenderableType:
    return Group(
        Text(
            "This template comes from an external source that isn't marked "
            "trusted. Applying runs these commands on your system:"
        ),
        *_indented([shlex.join(command) for command in commands], "bold"),
        Text(
            "Configure it as an alias with trusted = true to skip this check.",
            style="dim",
        ),
    )


_SCROLL_DIFF = Binding.Group("Scroll diff")


class FileTree(Tree[Entry]):
    """The planned paths; page keys scroll the diff rather than the tree."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "Up", group=MOVE),
        Binding("down", "cursor_down", "Down", group=MOVE),
        Binding("pageup", "screen.scroll_diff(-1)", "Up", group=_SCROLL_DIFF),
        Binding("pagedown", "screen.scroll_diff(1)", "Down", group=_SCROLL_DIFF),
    ]


class ReviewScreen(KeyboardScreen[InitDecision]):
    """Show what init will change, and settle the collision and trust decisions.

    No field takes text, so every decision has a letter.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back", show=False),
        Binding("q", "cancel", "Cancel", show=False),
        Binding("a", "apply", "Apply", show=False),
        Binding("m", "strategy('merge')", "Merge", show=False),
        Binding("o", "strategy('overwrite')", "Overwrite", show=False),
        Binding("t", "trust", "Trust", show=False),
    ]

    def __init__(
        self, draft: InitDraft, config: UserConfig, *, can_go_back: bool = False
    ) -> None:
        super().__init__()
        self.draft = draft
        self.config = config
        self.can_go_back = can_go_back
        self.strategy = draft.collision_strategy or CollisionStrategy.MERGE
        self.review: Review | None = None
        self.commands: tuple[tuple[str, ...], ...] = ()
        self._hook_revisions: tuple[ResolvedHookRevision, ...] | None = None
        self._loading = True

    def compose(self) -> ComposeResult:
        """Compose the file tree and steps beside the diff, the decisions below it."""
        yield Masthead("init", "review")
        yield Headline("Review changes", "Preparing review…")
        with Horizontal(id="body"):
            with Vertical(id="review"):
                with Panel("Files", id="files-panel"):
                    yield FileTree(Text("."), id="files")
                with (
                    Panel("Commands & packages", id="steps-panel"),
                    VerticalScroll(id="steps"),
                ):
                    yield Static("", id="steps-list")
            with Vertical(id="diff-column"):
                with Panel("Diff", id="diff-panel"), VerticalScroll(id="diff-pane"):
                    yield Static("", id="diff")
                with Vertical(id="decisions"):
                    with Vertical(id="collision-choice"):
                        yield Heading("Existing files")
                        yield Static("", id="collision-note")
                        with Choice(id="collision"):
                            yield RadioButton(
                                key_label(
                                    "Merge · keep your values and add what's missing",
                                    "m",
                                ),
                                value=self.strategy is CollisionStrategy.MERGE,
                                id="strategy-merge",
                            )
                            yield RadioButton(
                                key_label(
                                    "Overwrite · replace them with Protostar's version",
                                    "o",
                                ),
                                value=self.strategy is CollisionStrategy.OVERWRITE,
                                id="strategy-overwrite",
                            )
                    with Vertical(id="trust-gate"):
                        yield Heading("Untrusted template")
                        yield Static("", id="trust-note")
                        yield Toggle(
                            key_label(
                                "I trust this template to run these commands", "t"
                            ),
                            id="trust",
                        )
                with ActionBar(id="actions"):
                    if self.can_go_back:
                        yield Button(key_label("Back", "esc"), id="back")
                    yield Button(
                        key_label("Cancel", "q" if self.can_go_back else "esc"),
                        id="cancel",
                    )
                    yield Button(
                        key_label("Apply", "a"),
                        variant="primary",
                        id="apply",
                        disabled=True,
                    )
        yield Footer()

    def on_mount(self) -> None:
        """Hide the decisions until the review shows they are needed, then prepare."""
        files = self.query_one("#files", Tree)
        files.show_root = False
        files.focus()
        self.query_one("#collision-choice").display = False
        self.query_one("#trust-gate").display = False
        self.prepare()

    @work(exclusive=True, group="review")
    async def prepare(self) -> None:
        """Plan the draft and prepare its first file batch; a newer call cancels this one.

        Planning and preparation are read-only, so both run in a thread.
        ``execute()`` never runs while the app does.
        """
        self._loading = True
        self._status(Text("Preparing review…"))
        self._refresh_apply()
        draft = replace(self.draft, collision_strategy=self.strategy)
        try:
            request, manifest = await asyncio.to_thread(_plan, draft, self.config)
            if self._hook_revisions is None:
                # One registry snapshot per review: execution writes the pins it shows.
                self._hook_revisions = (
                    await asyncio.to_thread(resolve_hook_revisions)
                    if manifest.tooling.wants_hooks
                    else ()
                )
            review = await asyncio.to_thread(
                _prepare, request, manifest, self.config, self._hook_revisions
            )
        except ProtostarError as exc:
            self.review = None
            self._loading = False
            self._status(Text(str(exc)), error=True)
            self._refresh_apply()
            return
        self._loading = False
        self._show(review)

    def _show(self, review: Review) -> None:
        self.review = review
        manifest = review.manifest
        commands = untrusted_commands(review.request, manifest)
        if commands != self.commands:
            # A confirmation covers exactly the commands it was given.
            self.commands = commands
            trust = self.query_one("#trust", Checkbox)
            with trust.prevent(Checkbox.Changed):
                trust.value = False
        collisions = sorted(path.as_posix() for path in manifest.collisions)
        self.query_one("#collision-choice").display = bool(collisions)
        self.query_one("#collision-note", Static).update(
            Text(f"Already in the workspace: {', '.join(collisions)}")
        )
        self.query_one("#trust-gate").display = bool(commands)
        self.query_one("#trust-note", Static).update(_trust_text(commands))
        self.query_one("#steps-list", Static).update(steps_text(manifest))
        self._status(summary(review))
        self._fill_tree(review.entries)
        self._refresh_apply()

    def _fill_tree(self, entries: Sequence[Entry]) -> None:
        files: Tree[Entry] = self.query_one("#files", Tree)
        cursor = files.cursor_node
        current = cursor.data.path if cursor and cursor.data else None
        files.clear()
        nodes: dict[str, TreeNode[Entry]] = {"": files.root}
        for entry in entries:
            parts = entry.path.split("/")
            parent = ""
            for index in range(1, len(parts)):
                folder = "/".join(parts[:index])
                if folder not in nodes:
                    nodes[folder] = nodes[parent].add(
                        Text(f"{parts[index - 1]}/", _FOLDER), expand=True
                    )
                parent = folder
            label = _label(entry)
            nodes[entry.path] = (
                nodes[parent].add(label, entry, expand=True)
                if entry.directory
                else nodes[parent].add_leaf(label, entry)
            )
        # Keep the file in view across a strategy change, else open the first diff.
        target = next(
            (entry for entry in entries if entry.path == current),
            next((entry for entry in entries if entry.edit), None),
        ) or (entries[0] if entries else None)
        self._describe(target)
        if target is not None:
            files.call_after_refresh(files.move_cursor, nodes[target.path])

    def _describe(self, entry: Entry | None) -> None:
        title = Content("DIFF")
        if entry:
            # A path is data: Content never reads it as markup.
            name = entry.path + ("/" if entry.directory else "")
            title = Content.assemble(title, ("  ", ""), (name, "$foreground"))
        self.query_one("#diff-panel", Panel).retitle(title)
        self.query_one("#diff", Static).update(
            describe(entry)
            if entry
            else Text("Select a file to see its changes.", style="dim")
        )

    def _status(self, message: Text, *, error: bool = False) -> None:
        subtitle = self.query_one("#subtitle", Static)
        subtitle.update(message)
        subtitle.set_class(error, "-error")

    def _refresh_apply(self) -> None:
        confirmed = not self.commands or self.query_one("#trust", Checkbox).value
        self.query_one("#apply", Button).disabled = (
            self._loading or self.review is None or not confirmed
        )

    @on(Tree.NodeHighlighted, "#files")
    def show_changes(self, event: Tree.NodeHighlighted[Entry]) -> None:
        """Show the highlighted file's diff, or why it has none yet."""
        self._describe(event.node.data)

    @on(RadioSet.Changed, "#collision")
    def choose_strategy(self, event: RadioSet.Changed) -> None:
        """Re-prepare the batch, since merge and overwrite write different bytes."""
        strategy = CollisionStrategy(str(event.pressed.id).removeprefix("strategy-"))
        if strategy is self.strategy:
            return
        self.strategy = strategy
        self.prepare()

    @on(Checkbox.Changed, "#trust")
    def confirm_trust(self) -> None:
        """Allow applying only once the listed commands are confirmed."""
        self._refresh_apply()

    def key_rows(self) -> KeyRows:
        """The review's keys; escape goes back only when there is an editor."""
        leave = (
            (("esc", "Back to the editor"), ("q", "Cancel, after asking"))
            if self.can_go_back
            else (("esc", "Cancel, after asking"),)
        )
        return (
            ("↑ ↓", "Move between files"),
            ("pgup pgdn", "Scroll the diff"),
            ("space", "Fold or unfold a folder"),
            ("tab", "Next control"),
            ("shift+tab", "Previous control"),
            ("m / o", "Merge into or overwrite existing files, when asked"),
            ("t", "Trust the template's commands, when asked"),
            ("a", "Apply"),
            *leave,
            ("^c", "Quit immediately"),
        )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable the keys whose control is hidden.

        Escape falls through to the app's cancel when there is no editor to go
        back to.
        """
        if action == "back":
            return self.can_go_back
        if action == "strategy":
            return self.query_one("#collision-choice").display
        if action == "trust":
            return self.query_one("#trust-gate").display
        return True

    def action_back(self) -> None:
        """Return to the recipe editor with its choices intact."""
        self.app.pop_screen()

    def action_strategy(self, strategy: str) -> None:
        """Choose how existing files are handled."""
        self.query_one(f"#strategy-{strategy}", RadioButton).value = True

    def action_trust(self) -> None:
        """Toggle the confirmation that the listed commands may run."""
        self.query_one("#trust", Checkbox).toggle()

    def action_scroll_diff(self, direction: int) -> None:
        """Page the diff without leaving the file tree."""
        pane = self.query_one("#diff-pane", VerticalScroll)
        if direction > 0:
            pane.scroll_page_down(animate=False)
        else:
            pane.scroll_page_up(animate=False)

    @on(Button.Pressed, "#back")
    def _back_pressed(self) -> None:
        self.action_back()

    @on(Button.Pressed, "#cancel")
    def _cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#apply")
    def action_apply(self) -> None:
        """Exit with the decision; execution starts after the app has exited."""
        if self.review is not None and not self.query_one("#apply", Button).disabled:
            # The choice applies only where the review asked for one.
            strategy = (
                self.strategy
                if self.review.manifest.collisions
                else self.draft.collision_strategy
            )
            self.app.exit(
                InitDecision(
                    replace(self.draft, collision_strategy=strategy),
                    self.review.prepared.hook_revisions,
                    self.commands,
                )
            )
