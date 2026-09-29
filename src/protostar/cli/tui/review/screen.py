"""The files init writes before any command, the steps after them, and every decision."""

import asyncio
import shlex
from collections.abc import Sequence
from dataclasses import replace
from typing import ClassVar, cast

from rich.console import Group, RenderableType
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
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

from protostar.cli.changes import (
    FOLDER,
    NETWORK_NOTE,
    Change,
    Entry,
    HookSnapshot,
    Review,
    count,
    entry_label,
    hook_snapshot,
    indented_lines,
    plan_draft,
    prepare_draft,
    steps_text,
    summary,
    walk_entry_hierarchy,
)
from protostar.cli.decisions import MEANING, identity
from protostar.cli.ui import untrusted_commands
from protostar.config import UserConfig
from protostar.errors import ProtostarError
from protostar.init_draft import InitDecision, InitDraft
from protostar.manifest import CollisionStrategy
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    default_choice,
    describe_location,
)

from ..app import DecisionApp
from ..chrome import (
    Column,
    Columns,
    Heading,
    Headline,
    Masthead,
    Panel,
    Section,
    Tab,
    TabbedPanel,
)
from ..code import edit_text
from ..conflicts.decision_list import DecisionList, Node, open_conflicts
from ..conflicts.sides import (
    KEYS,
    OPEN,
    SAID,
    describe_conflict,
    is_conflict,
    side_text,
    sides_diff,
    waiting_note,
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


def describe(
    entry: Entry, *, one_shot: bool = False, only: MergeConflict | None = None
) -> RenderableType:
    """Renders an entry's accepted bytes, or says why none can be shown yet.

    Args:
        entry: The planned path to describe.
        one_shot: Whether the run leaves no ownership state behind.
        only: The one decision to describe above the diff, instead of all of
            the entry's.

    Returns:
        Any conflicts kept as they are, then the diff or a note.
    """
    parts: list[RenderableType] = []
    conflicts = entry.conflicts if only is None else (only,)
    if any(c.reason is ConflictReason.PROPOSED for c in conflicts):
        note = (
            "Changes to content you already have. Each applies unless kept "
            "out; keeping yours out leaves your version in place."
            if one_shot
            else "Changes to content you already have. Each applies unless kept "
            "out; keeping yours out records Protostar's version, so sync "
            "can take it later."
        )
        parts.append(Text(note))
    for conflict in conflicts:
        where = describe_location(conflict.location)
        if conflict.reason is ConflictReason.PROPOSED:
            # One line each; the file's diff below shows the exact bytes.
            kept = conflict.resolution is ResolutionChoice.LOCAL
            named = identity(conflict)
            parts.append(
                Text.assemble(
                    (
                        "  kept out  " if kept else "  adds      ",
                        "cyan" if kept else "green",
                    ),
                    (where or "the file", "bold"),
                    (f" {named}" if named else "", "bold"),
                )
            )
            if only is not None and conflict.sides is not None:
                # One proposal alone shows what it adds; nothing of yours changes.
                parts.append(side_text(conflict, "desired"))
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
        meaning = MEANING[conflict.reason]
        if conflict.location.lines is not None:
            # Both sides edited these lines, so the whole file is kept.
            message = f"{where[:1].upper()}{where[1:]}: your edit is kept. {meaning}"
        else:
            message = f"Your version of {where or 'the file'} is kept. {meaning}"
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


def _trust_text(commands: tuple[tuple[str, ...], ...]) -> RenderableType:
    return Group(
        Text(
            "This template comes from an external source that isn't marked "
            "trusted. Applying runs these commands on your system:"
        ),
        *indented_lines([shlex.join(command) for command in commands], "bold"),
        Text(
            "Configure it as an alias with trusted = true to skip this check.",
            style="dim",
        ),
    )


_SCROLL_DIFF = Binding.Group("Scroll diff")
_PAGE_DIFF: list[BindingType] = [
    Binding("pageup", "screen.scroll_diff(-1)", "Up", group=_SCROLL_DIFF),
    Binding("pagedown", "screen.scroll_diff(1)", "Down", group=_SCROLL_DIFF),
]


class FileTree(Tree[Entry]):
    """The planned paths; page keys scroll the diff rather than the tree."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "Up", group=MOVE),
        Binding("down", "cursor_down", "Down", group=MOVE),
        *_PAGE_DIFF,
    ]


class DecisionTree(DecisionList):
    """The review's decisions; page keys scroll the diff rather than the list."""

    BINDINGS: ClassVar[list[BindingType]] = _PAGE_DIFF


DECISIONS, FILES, SETUP = "decisions", "files", "setup"
TABS = (
    Tab(DECISIONS, "Decisions", "d"),
    Tab(FILES, "Files", "f"),
    Tab(SETUP, "Setup", "s"),
)


class ReviewScreen(KeyboardScreen[InitDecision]):
    """Show what init will change, and settle its decisions and the trust gate.

    How existing files are written is chosen in the recipe editor; the review
    only says which strategy it shows.

    No field takes text, so every decision has a letter.
    """

    ROOMY = (100, 30)

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back", show=False),
        Binding("q", "cancel", "Cancel", show=False),
        Binding("a", "apply", "Apply", show=False),
        Binding("t", "trust", "Trust", show=False),
        Binding("k", "resolve('local')", "Keep mine", show=False),
        Binding("u", "resolve('desired')", "Take update", show=False),
        Binding("b", "resolve('both')", "Keep both", show=False),
        Binding("x", "resolve('open')", "Leave open", show=False),
        Binding("K", "keep_all", "Keep all mine", show=False),
        Binding("n", "next_open", "Next open", show=False),
        *(Binding(tab.key, f"tab('{tab.id}')", tab.title, show=False) for tab in TABS),
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
        self._entries: dict[str, Entry] = {}
        self._opened = False
        self._handed = review
        self._loading = True
        self._shown = False

    def compose(self) -> ComposeResult:
        """Compose the file tree and steps beside the diff, the decisions below it."""
        yield Masthead("init", "review")
        yield Headline("Review changes", "Preparing review…")
        with Columns(id="body"):
            with Column(id="review"):
                yield TabbedPanel(
                    TABS,
                    DecisionTree(self.choices, id=DECISIONS),
                    FileTree(Text("."), id=FILES),
                    VerticalScroll(
                        Static(Text(NETWORK_NOTE), id="network-note"),
                        Static("", id="steps-list"),
                        id=SETUP,
                    ),
                    id="review-panel",
                )
            with Column(id="diff-column"):
                with Panel("Diff", id="diff-panel"), VerticalScroll(id="diff-pane"):
                    yield Static("", id="diff")
                with Section(id="conflict-choice"):
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
                with Section(id="trust-gate"):
                    yield Heading("Untrusted template")
                    yield Static("", id="trust-note")
                    yield Toggle(
                        key_label("I trust this template to run these commands", "t"),
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
        # The decisions show once the review finds some.
        self._panel().hide(DECISIONS)
        files.focus()
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
        self.query_one("#trust-gate").display = bool(commands)
        self.query_one("#trust-note", Static).update(_trust_text(commands))
        self.query_one("#network-note").display = bool(
            self._hooks and self._hooks.unreachable
        )
        self.query_one("#steps-list", Static).update(steps_text(manifest))
        self._status(self._summary(review))
        self.query_one("#keep-all").display = bool(self._keepable())
        self._entries = {entry.path: entry for entry in review.entries}
        file = self._fill_tree(review.entries)
        row = self._fill_decisions(review.entries)
        self._refresh_detail(file=file, row=row)
        self._refresh_apply()

    def _summary(self, review: Review) -> Text:
        """The review's counts, then how it writes into files that already exist."""
        text = summary(review)
        if collisions := len(review.manifest.collisions):
            verb = (
                "Overwriting"
                if self.strategy is CollisionStrategy.OVERWRITE
                else "Merging into"
            )
            text.append(
                f" · {verb} {count(collisions, 'existing file')}; "
                "the recipe editor can change this.",
                style="dim",
            )
        return text

    def _panel(self) -> TabbedPanel:
        return self.query_one("#review-panel", TabbedPanel)

    def _fill_decisions(self, entries: Sequence[Entry]) -> Node | None:
        """List the review's decisions, and open on them the first time there are any.

        Returns:
            The row the list highlights.
        """
        decisions = self.query_one(f"#{DECISIONS}", DecisionTree)
        panel = self._panel()
        found = tuple(c for entry in entries for c in entry.conflicts)
        # Hiding the list moves focus off it, so ask first.
        leaving = not found and self.focused is decisions
        panel.hide(DECISIONS, not found)
        row = decisions.show(found)
        self._note_open()
        if found and not self._opened:
            # Once only: decisions a later strategy brings back wait behind their tab.
            self._opened = True
            self.action_tab(DECISIONS)
        elif leaving:
            self.action_tab(panel.active)
        return row

    def _note_open(self) -> None:
        """Say beside the decisions' tab how many conflicts still wait on a choice."""
        decisions = self.query_one(f"#{DECISIONS}", DecisionTree)
        waiting = len(open_conflicts(decisions.decisions, self.choices))
        self._panel().note(DECISIONS, f"{waiting} open" if waiting else "")

    def _fill_tree(self, entries: Sequence[Entry]) -> Entry | None:
        files: Tree[Entry] = self.query_one("#files", Tree)
        cursor = files.cursor_node
        current = cursor.data.path if cursor and cursor.data else None
        files.clear()
        nodes: dict[str, TreeNode[Entry]] = {"": files.root}
        for parent, path, name, entry in walk_entry_hierarchy(entries):
            if entry is None:
                nodes[path] = nodes[parent].add(Text(name, FOLDER), expand=True)
            else:
                label = entry_label(entry)
                nodes[path] = (
                    nodes[parent].add(label, entry, expand=True)
                    if entry.directory
                    else nodes[parent].add_leaf(label, entry)
                )
        # Keep the file in view across a strategy change, else open the first diff.
        target = next(
            (entry for entry in entries if entry.path == current),
            next((entry for entry in entries if entry.edit), None),
        ) or (entries[0] if entries else None)
        if target is not None:
            files.call_after_refresh(files.move_cursor, nodes[target.path])
        return target

    def _selection(
        self, *, file: Entry | None = None, row: Node | None = None
    ) -> tuple[Entry | None, MergeConflict | None, list[MergeConflict]]:
        """Returns the shown pane's file, its one decision, and what a choice settles.

        Args:
            file: The file to take instead of the files tree's cursor.
            row: The row to take instead of the decision list's cursor.
        """
        if self._panel().active == DECISIONS:
            decisions = self.query_one(f"#{DECISIONS}", DecisionTree)
            row = row or decisions.highlighted()
            if row is None:
                return None, None, []
            targets = [c for c in decisions.targets(row) if c.choices]
            return self._entries.get(row.path), row.conflict, targets
        if file is None:
            cursor = self.query_one("#files", Tree).cursor_node
            file = cursor.data if cursor is not None else None
        return file, None, [c for c in file.conflicts if c.choices] if file else []

    def _refresh_detail(
        self, *, file: Entry | None = None, row: Node | None = None
    ) -> None:
        """Show the selection's diff and the choices that settle it."""
        entry, only, targets = self._selection(file=file, row=row)
        self._show_resolution(targets)
        self._describe(entry, only)

    def _describe(self, entry: Entry | None, only: MergeConflict | None) -> None:
        title = Content("DIFF")
        if entry:
            # A path is data: Content never reads it as markup.
            name = entry.path + ("/" if entry.directory else "")
            title = Content.assemble(title, ("  ", ""), (name, "$foreground"))
        self.query_one("#diff-panel", Panel).retitle(title)
        if entry is None:
            self.query_one("#diff", Static).update(
                Text("Select a file to see its changes.", style="dim")
            )
            return
        parts: list[RenderableType] = []
        # Overlapping lines change together, so one choice alone waits.
        waiting = [
            c
            for c in entry.open
            if c.sides is not None and c.sides.text and c.id in self.choices
        ]
        if waiting:
            parts.append(waiting_note(entry.path))
        parts.append(describe(entry, one_shot=self.draft.one_shot, only=only))
        self.query_one("#diff", Static).update(Group(*parts))

    def _show_resolution(self, conflicts: list[MergeConflict]) -> None:
        """Offer the choices the selected conflicts and proposals can be settled with."""
        group = self.query_one("#conflict-choice")
        group.display = bool(conflicts)
        if not conflicts:
            return
        offered = {choice for conflict in conflicts for choice in conflict.choices}
        # A proposal applies unless kept out, so its choice is never "open".
        picked = {self.choices.get(c.id) or default_choice(c) for c in conflicts}
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
        """Settle the selection's decisions, then prepare the review again.

        Settling a conflict in the decision list moves on to the next open one.
        """
        _, _, targets = self._selection()
        if not targets or self._loading:
            return
        choice = None if value == OPEN else ResolutionChoice(value)
        settled: list[MergeConflict] = []
        for conflict in targets:
            if choice is None and conflict.reason is ConflictReason.PROPOSED:
                continue
            if choice and choice not in conflict.choices:
                continue
            if self.choices.get(conflict.id) == choice:
                continue
            if choice is None:
                self.choices.pop(conflict.id, None)
            else:
                self.choices[conflict.id] = choice
            settled.append(conflict)
        if not settled:
            return
        decisions = self.query_one(f"#{DECISIONS}", DecisionTree)
        decisions.relabel()
        self._note_open()
        if (
            choice is not None
            and self._panel().active == DECISIONS
            and any(is_conflict(c) for c in settled)
        ):
            decisions.next_open()
        self._refresh_detail()
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
            self.query_one(f"#{DECISIONS}", DecisionTree).relabel()
            self._note_open()
            self._refresh_detail()
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
        if self._panel().active != DECISIONS:
            self._refresh_detail(file=event.node.data)

    @on(Tree.NodeHighlighted, f"#{DECISIONS}")
    def show_decision(self, event: Tree.NodeHighlighted[Node]) -> None:
        """Show the highlighted decision above its file's diff."""
        if self._panel().active == DECISIONS:
            self._refresh_detail(row=event.node.data)

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
            ("d / f / s", "Show the decisions, the files, or the setup steps"),
            ("↑ ↓", "Move between decisions or files"),
            ("n", "Next open conflict"),
            ("pgup pgdn", "Scroll the diff"),
            ("space", "Fold or unfold a folder"),
            ("tab", "Next control"),
            ("shift+tab", "Previous control"),
            ("t", "Trust the template's commands, when asked"),
            ("k / u / b", "Keep mine, take the update, or keep both"),
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
        if action == "trust":
            return self.query_one("#trust-gate").display
        if action == "keep_all":
            return self.query_one("#keep-all").display
        if action in ("tab", "next_open"):
            tab = str(parameters[0]) if parameters else DECISIONS
            return self._panel().is_shown(tab)
        if action == "resolve":
            if not self.query_one("#conflict-choice").display:
                return False
            value = str(parameters[0]) if parameters else OPEN
            return not self.query_one(f"#resolve-{value}", RadioButton).disabled
        return True

    def action_back(self) -> None:
        """Return to the recipe editor with its choices intact."""
        self.app.pop_screen()

    def action_resolve(self, value: str) -> None:
        """Settle the highlighted file's conflicts by key."""
        self._resolve(value)

    def action_tab(self, tab: str) -> None:
        """Show a pane of the left panel and move into it."""
        panel = self._panel()
        if not panel.is_shown(tab):
            return
        panel.show(tab)
        self.query_one(f"#{tab}").focus()
        self._refresh_detail()

    def action_next_open(self) -> None:
        """Move to the next conflict that still waits on a choice.

        From another tab, the highlighted decision counts when it is open.
        """
        here = self._panel().active != DECISIONS
        if here:
            self.action_tab(DECISIONS)
        self.query_one(f"#{DECISIONS}", DecisionTree).next_open(here=here)

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
