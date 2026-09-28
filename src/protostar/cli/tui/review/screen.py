"""The files init writes before any command, the steps after them, and every decision."""

import asyncio
import shlex
from collections.abc import Sequence
from dataclasses import replace
from typing import ClassVar, cast

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

from protostar.cli.ui import untrusted_commands
from protostar.config import UserConfig
from protostar.errors import ProtostarError
from protostar.init_draft import InitDecision, InitDraft
from protostar.intent import DependencyGroup
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    default_choice,
    describe_location,
)

from ..app import DecisionApp
from ..chrome import Heading, Headline, Masthead, Panel
from ..code import edit_text
from ..conflicts.sides import (
    KEYS,
    OPEN,
    SAID,
    describe_conflict,
    sides_diff,
)
from ..keys import (
    MOVE,
    ActionBar,
    Choice,
    KeyboardScreen,
    KeyRows,
    Toggle,
    key_label,
)
from .model import (
    FOLDER,
    NETWORK_NOTE,
    Change,
    Entry,
    HookSnapshot,
    Review,
    count,
    entry_label,
    hook_snapshot,
    plan_draft,
    prepare_draft,
    summary,
)


def describe(entry: Entry, *, one_shot: bool = False) -> RenderableType:
    """Renders an entry's accepted bytes, or says why none can be shown yet.

    Args:
        entry: The planned path to describe.
        one_shot: Whether the run leaves no ownership state behind.

    Returns:
        Any conflicts kept as they are, then the diff or a note.
    """
    parts: list[RenderableType] = []
    if entry.proposals:
        note = (
            "Changes to content you already have. Each applies unless kept "
            "out; keeping yours out leaves your version in place."
            if one_shot
            else "Changes to content you already have. Each applies unless kept "
            "out; keeping yours out records Protostar's version, so sync "
            "can take it later."
        )
        parts.append(Text(note))
    for conflict in entry.conflicts:
        where = describe_location(conflict.location)
        reason = conflict.reason.value
        if conflict.reason is ConflictReason.PROPOSED:
            # One line each; the file's diff below shows the exact bytes.
            kept = conflict.resolution is ResolutionChoice.LOCAL
            # A requirement's identity is its package and marker.
            identity = (conflict.location.identity or "").rstrip(":")
            parts.append(
                Text.assemble(
                    (
                        "  kept out  " if kept else "  adds      ",
                        "cyan" if kept else "green",
                    ),
                    (where or "the file", "bold"),
                    (f" {identity}" if identity else "", "bold"),
                )
            )
            continue
        if conflict.resolution is not None:
            parts.append(
                Text(
                    f"Resolved {where or 'the file'}: {SAID[conflict.resolution]}.",
                    "cyan",
                )
            )
            continue
        if conflict.choices:
            parts.append(describe_conflict(conflict))
            parts.append(sides_diff(conflict))
            continue
        if conflict.location.lines is not None:
            # Both sides edited these lines, so the whole file is kept.
            message = f"{where[:1].upper()}{where[1:]}: your edit is kept ({reason})."
        else:
            message = f"Your version of {where or 'the file'} is kept ({reason})."
        parts.append(Text(message, "red"))
    if entry.edit is not None:
        parts.append(edit_text(entry.edit))
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
        if entry.creator is None:
            origin = "Written after the commands and packages run."
        elif entry.merged:
            origin = (
                f"Created by {shlex.join(entry.creator)}, then Protostar merges "
                "its settings into it."
            )
        else:
            origin = f"Created by {shlex.join(entry.creator)}."
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
            parts.extend(_indented(lines))
    return Group(*parts) if parts else Text("No commands or packages.", style="dim")


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
        Binding("k", "resolve('local')", "Keep mine", show=False),
        Binding("u", "resolve('desired')", "Take update", show=False),
        Binding("b", "resolve('both')", "Keep both", show=False),
        Binding("x", "resolve('open')", "Leave open", show=False),
        Binding("K", "keep_all", "Keep all mine", show=False),
    ]

    def __init__(
        self,
        draft: InitDraft,
        config: UserConfig,
        *,
        can_go_back: bool = False,
        review: Review | None = None,
        hooks: HookSnapshot | None = None,
    ) -> None:
        """Create the screen.

        Args:
            draft: The draft to review.
            config: The user's configuration.
            can_go_back: Whether ``Esc`` returns to the recipe editor.
            review: The draft's review, already prepared by the editor's
                preview, shown at once instead of preparing it again.
            hooks: The registry snapshot the preview took; the screen takes
                its own only when this is ``None``.
        """
        super().__init__()
        self.draft = draft
        self.config = config
        self.can_go_back = can_go_back
        self.strategy = draft.collision_strategy or CollisionStrategy.MERGE
        self.review: Review | None = None
        self.commands: tuple[tuple[str, ...], ...] = ()
        self.choices: dict[str, ResolutionChoice] = {}
        self._hooks = hooks
        self._handed = review
        self._loading = True
        self._shown = False

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
                    yield Static(Text(NETWORK_NOTE), id="network-note")
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
                    with Vertical(id="conflict-choice"):
                        yield Heading("Conflicts").set_class(True, "choice-heading")
                        yield Static("", id="conflict-note")
                        with Choice(id="resolution"):
                            for choice in ResolutionChoice:
                                yield RadioButton(
                                    key_label(SAID[choice].capitalize(), KEYS[choice]),
                                    id=f"resolve-{choice.value}",
                                )
                            yield RadioButton(
                                key_label("Leave open", "x"), id=f"resolve-{OPEN}"
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
                    yield Button(key_label("Keep all mine", "K"), id="keep-all")
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
        self.query_one("#conflict-choice").display = False
        self.query_one("#keep-all").display = False
        self.query_one("#trust-gate").display = False
        if self._handed is None:
            self.prepare()
            return
        self._loading = False
        self._shown = True
        self._show(self._handed)

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
            request, manifest = await asyncio.to_thread(plan_draft, draft, self.config)
            if self._hooks is None:
                # One registry snapshot per review: execution writes the pins
                # it shows. Taken even without hooks, to warn when offline.
                self._hooks = await asyncio.to_thread(hook_snapshot)
            review = await asyncio.to_thread(
                prepare_draft,
                request,
                manifest,
                self.config,
                self._hooks.pins(manifest),
                dict(self.choices),
            )
        except ProtostarError as exc:
            if not self._shown and not self.can_go_back:
                # No choice here can fix a review that never prepared.
                cast("DecisionApp[InitDecision]", self.app).fail(exc)
                return
            self.review = None
            self._loading = False
            self._status(
                Text.assemble(str(exc), (f"  {exc.hint}", "dim") if exc.hint else ""),
                error=True,
            )
            self._refresh_apply()
            return
        self._loading = False
        self._shown = True
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
            # The files tree names each one; the note only says how many.
            Text(
                f"{count(len(collisions), 'file')} already "
                f"{'exists' if len(collisions) == 1 else 'exist'}. "
                "Choose how Protostar writes into them."
            )
        )
        self.query_one("#trust-gate").display = bool(commands)
        self.query_one("#trust-note", Static).update(_trust_text(commands))
        self.query_one("#network-note").display = bool(
            self._hooks and self._hooks.unreachable
        )
        self.query_one("#steps-list", Static).update(steps_text(manifest))
        self._status(summary(review))
        self.query_one("#keep-all").display = bool(self._keepable())
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
                        Text(f"{parts[index - 1]}/", FOLDER), expand=True
                    )
                parent = folder
            label = entry_label(entry)
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
        self._show_resolution(entry)
        title = Content("DIFF")
        if entry:
            # A path is data: Content never reads it as markup.
            name = entry.path + ("/" if entry.directory else "")
            title = Content.assemble(title, ("  ", ""), (name, "$foreground"))
        self.query_one("#diff-panel", Panel).retitle(title)
        self.query_one("#diff", Static).update(
            describe(entry, one_shot=self.draft.one_shot)
            if entry
            else Text("Select a file to see its changes.", style="dim")
        )

    def _show_resolution(self, entry: Entry | None) -> None:
        """Offer the choices the entry's conflicts and proposals can be settled with."""
        conflicts = [c for c in entry.conflicts if c.choices] if entry else []
        group = self.query_one("#conflict-choice")
        group.display = bool(conflicts)
        if not conflicts:
            return
        offered = {choice for conflict in conflicts for choice in conflict.choices}
        # A proposal applies unless kept out, so its choice is never "open".
        picked = {c.resolution or default_choice(c) for c in conflicts}
        proposals = sum(c.reason is ConflictReason.PROPOSED for c in conflicts)
        only_proposals = proposals == len(conflicts)
        heading = self.query_one(".choice-heading", Heading)
        heading.label = "Changes to your file" if only_proposals else "Conflicts"
        heading.refresh()
        noun = "changes" if only_proposals else "decisions"
        count = f"{len(conflicts)} {noun} here. " if len(conflicts) > 1 else ""
        if self.draft.one_shot:
            note = (
                "Keeping yours leaves your version in place."
                if only_proposals
                else "This choice applies to this run only."
            )
        else:
            note = (
                "Keeping yours records Protostar's version without writing it; "
                "sync can take it later."
                if only_proposals
                else "Whichever you choose, Protostar manages it from now on."
            )
        self.query_one("#conflict-note", Static).update(Text(f"{count}{note}"))
        for choice in ResolutionChoice:
            button = self.query_one(f"#resolve-{choice.value}", RadioButton)
            button.disabled = choice not in offered
        self.query_one(f"#resolve-{OPEN}", RadioButton).disabled = only_proposals
        pressed = None
        # Mixed choices across a file's conflicts press no button.
        if len(picked) == 1:
            (only,) = picked
            value = only.value if only else OPEN
            pressed = self.query_one(f"#resolve-{value}", RadioButton)
        self.query_one("#resolution", Choice).show(pressed)

    def _resolve(self, value: str) -> None:
        """Settle the highlighted file's conflicts, then prepare the review again."""
        cursor = self.query_one("#files", Tree).cursor_node
        entry = cursor.data if cursor is not None else None
        if entry is None or self._loading:
            return
        choice = None if value == OPEN else ResolutionChoice(value)
        changed = False
        for conflict in entry.conflicts:
            if choice is None and conflict.reason is ConflictReason.PROPOSED:
                continue
            if not conflict.choices or (choice and choice not in conflict.choices):
                continue
            if self.choices.get(conflict.id) == choice:
                continue
            if choice is None:
                self.choices.pop(conflict.id, None)
            else:
                self.choices[conflict.id] = choice
            changed = True
        if changed:
            self.prepare()

    def _keepable(self) -> list[MergeConflict]:
        """Returns every decision in the review that can keep the local content."""
        if self.review is None:
            return []
        return [
            c
            for entry in self.review.entries
            for c in entry.conflicts
            if ResolutionChoice.LOCAL in c.choices
        ]

    def action_keep_all(self) -> None:
        """Keep the local content everywhere a choice allows it."""
        if self._loading:
            return
        keepable = self._keepable()
        if any(self.choices.get(c.id) is not ResolutionChoice.LOCAL for c in keepable):
            self.choices.update((c.id, ResolutionChoice.LOCAL) for c in keepable)
            self.prepare()

    @on(Button.Pressed, "#keep-all")
    def _keep_all_pressed(self) -> None:
        self.action_keep_all()

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

    @on(RadioSet.Changed, "#resolution")
    def choose_resolution(self, event: RadioSet.Changed) -> None:
        """Settle the highlighted file's conflicts with the pressed choice."""
        self._resolve(str(event.pressed.id).removeprefix("resolve-"))

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
            ("k / u / b", "Keep mine, take the update, or keep both, for a file"),
            ("x", "Leave a conflict open"),
            ("K", "Keep mine for every conflict and change to your files"),
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
        if action == "keep_all":
            return self.query_one("#keep-all").display
        if action == "resolve":
            if not self.query_one("#conflict-choice").display:
                return False
            value = str(parameters[0]) if parameters else OPEN
            return not self.query_one(f"#resolve-{value}", RadioButton).disabled
        return True

    def action_back(self) -> None:
        """Return to the recipe editor with its choices intact."""
        self.app.pop_screen()

    def action_strategy(self, strategy: str) -> None:
        """Choose how existing files are handled."""
        self.query_one(f"#strategy-{strategy}", RadioButton).value = True

    def action_resolve(self, value: str) -> None:
        """Settle the highlighted file's conflicts by key."""
        self._resolve(value)

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
                    # Exactly the choices this review applied.
                    {
                        c.id: c.resolution
                        for c in (
                            *self.review.prepared.resolved,
                            *self.review.prepared.proposals,
                        )
                        if c.resolution is not None
                    },
                )
            )
