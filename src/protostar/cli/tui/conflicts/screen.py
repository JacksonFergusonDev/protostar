"""Choose, decision by decision, which content a sync keeps.

The list holds the sync's conflicts, its proposed changes to content the user
already had, and the local edits it preserves. A proposal applies and a
preserved edit stays unless chosen otherwise; only a conflict can be left open.
"""

import asyncio
from collections import Counter
from collections.abc import Mapping
from typing import ClassVar

from rich.console import Group, RenderableType
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.content import Content
from textual.widgets import Button, Footer, RadioButton, RadioSet, Static, Tree

from protostar.cli.changes import count
from protostar.errors import ProtostarError
from protostar.lifecycle import PreparedProject
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    default_choice,
)
from protostar.preparation import PreparedReview

from ..chrome import Column, Columns, Heading, Headline, Masthead, Panel, Section
from ..code import edit_text
from ..keys import ActionBar, Choice, KeyboardScreen, KeyRows, key_label
from .decision_list import DecisionList, Node
from .sides import (
    KEYS,
    OPEN,
    SAID,
    describe_conflict,
    is_conflict,
    side_text,
    waiting_note,
)


def summary(
    decisions: tuple[MergeConflict, ...], choices: Mapping[str, ResolutionChoice]
) -> Text:
    """Counts the decisions by what happens to them.

    Args:
        decisions: The review's conflicts, proposals, and preserved edits.
        choices: The choices made so far.

    Returns:
        One line for the screen's subtitle.
    """
    conflicts = [d for d in decisions if is_conflict(d)]
    counts = Counter(
        "by hand"
        if not conflict.choices
        else ("resolved" if conflict.id in choices else OPEN)
        for conflict in conflicts
    )
    parts = []
    if conflicts:
        parts.append(count(len(conflicts), "conflict"))
        parts.extend(f"{counts[kind]} {kind}" for kind in ("resolved", OPEN))
        if counts["by hand"]:
            parts.append(f"{counts['by hand']} by hand")
    proposals = [d for d in decisions if d.reason is ConflictReason.PROPOSED]
    if proposals:
        kept = sum(choices.get(p.id) is ResolutionChoice.LOCAL for p in proposals)
        changes = count(len(proposals), "change") + " to your files"
        parts.append(f"{changes} ({kept} kept out)" if kept else changes)
    preserved = [d for d in decisions if d.reason is ConflictReason.PRESERVED]
    if preserved:
        restored = sum(choices.get(p.id) is ResolutionChoice.DESIRED for p in preserved)
        edits = count(len(preserved), "kept edit")
        parts.append(f"{edits} ({restored} updated)" if restored else edits)
    note = "Open conflicts keep your content; safe changes apply either way."
    return Text(f"{' · '.join(parts)}. {note}")


def _result(
    path: str,
    preview: PreparedReview | None,
    choices: Mapping[str, ResolutionChoice],
) -> RenderableType:
    if preview is None:
        return Text("Preparing the result…", style="dim")
    edit = next((edit for edit in preview.edits if edit.path == path), None)
    # Hunks still open because another hunk of the same text is.
    waiting = {
        conflict.id
        for conflict in preview.conflicts
        if conflict.location.file == path and conflict.sides and conflict.sides.text
    }
    parts: list[RenderableType] = []
    if waiting & choices.keys():
        parts.append(waiting_note(path))
    if edit is not None:
        parts.append(edit_text(edit))
    else:
        parts.append(Text("The file stays as it is.", style="dim"))
    return Group(*parts)


_SCROLL = Binding.Group("Scroll sides")


class ConflictTree(DecisionList):
    """The decisions by file; page keys scroll both sides together."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("pageup", "screen.scroll_sides(-1)", "Up", group=_SCROLL),
        Binding("pagedown", "screen.scroll_sides(1)", "Down", group=_SCROLL),
    ]


class ConflictScreen(KeyboardScreen[dict[str, ResolutionChoice]]):
    """Choose which content each conflict keeps, then apply the sync.

    The choices only decide; the sync applies after the app exits. A file row
    takes a choice for every conflict in it that offers that choice.
    """

    LEAVE = "Leave without syncing?"
    ROOMY = (100, 30)

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("k", "choose('local')", "Keep mine", show=False),
        Binding("u", "choose('desired')", "Take update", show=False),
        Binding("b", "choose('both')", "Keep both", show=False),
        Binding("x", "choose('open')", "Leave open", show=False),
        Binding("n", "next_open", "Next open", show=False),
        Binding("a", "apply", "Apply", show=False),
    ]

    def __init__(self, project: PreparedProject) -> None:
        """Create the screen.

        Args:
            project: The prepared sync whose conflicts to settle.
        """
        super().__init__()
        self.project = project
        self.conflicts = project.review.decisions
        self.choices: dict[str, ResolutionChoice] = {}
        # With nothing chosen yet, the sync's own review is the result.
        self.preview: PreparedReview | None = project.review
        self._failed = False

    def compose(self) -> ComposeResult:
        """Compose the conflict list beside both sides, the choices below them."""
        yield Masthead("sync", "conflicts")
        yield Headline("Review sync", summary(self.conflicts, self.choices))
        with Columns(id="body"):
            with Panel("Decisions", id="conflicts-panel"):
                yield ConflictTree(self.choices, id="conflicts")
            with Column(id="sides-column"):
                with Columns(id="sides"):
                    with (
                        Panel("Yours", id="local-panel"),
                        VerticalScroll(id="local-pane", classes="side"),
                    ):
                        yield Static("", id="local")
                    with (
                        Panel("Update", id="desired-panel"),
                        VerticalScroll(id="desired-pane", classes="side"),
                    ):
                        yield Static("", id="desired")
                with (
                    Panel("Result", id="result-panel"),
                    VerticalScroll(id="result-pane"),
                ):
                    yield Static("", id="result")
                with Section(id="resolution"):
                    yield Heading("Resolution")
                    yield Static("", id="meaning")
                    with Choice(id="choice"):
                        for choice in ResolutionChoice:
                            yield RadioButton(
                                key_label(SAID[choice].capitalize(), KEYS[choice]),
                                id=f"choice-{choice.value}",
                            )
                        yield RadioButton(
                            key_label("Leave open", "x"), id=f"choice-{OPEN}"
                        )
                with ActionBar(id="actions"):
                    yield Button(key_label("Cancel", "esc"), id="cancel")
                    yield Button(key_label("Apply", "a"), variant="primary", id="apply")
        yield Footer()

    def on_mount(self) -> None:
        """List the conflicts and show the first one complete before the first paint.

        The review the sync already prepared is the result until a choice
        changes it, so nothing waits on a worker here.
        """
        tree = self.query_one("#conflicts", ConflictTree)
        tree.focus()
        # The cursor lands after the list refreshes; show its row now.
        self._show(tree.show(self.conflicts))

    @work(exclusive=True, group="preview")
    async def refresh_preview(self) -> None:
        """Review the sync with the choices made so far, off the main thread.

        Only the read-only review runs here; the sync applies after exit.
        """
        choices = dict(self.choices)
        try:
            resolved = await asyncio.to_thread(self.project.resolve, choices)
        except ProtostarError as error:
            self.preview = None
            self._failed = True
            self._status(Text(str(error)), error=True)
            self._refresh_apply()
            return
        self._failed = False
        self.preview = resolved.review
        self._status(summary(self.conflicts, self.choices))
        self._show(self._highlighted())
        self._refresh_apply()

    def _tree(self) -> ConflictTree:
        return self.query_one("#conflicts", ConflictTree)

    def _highlighted(self) -> Node | None:
        return self._tree().highlighted()

    def _targets(self, node: Node | None) -> list[MergeConflict]:
        return self._tree().targets(node) if node is not None else []

    def _show(self, node: Node | None) -> None:
        targets = self._targets(node)
        # A file row shows its conflict's sides when it has only one.
        shown = targets[0] if len(targets) == 1 else None
        for side in ("local", "desired"):
            self.query_one(f"#{side}", Static).update(
                side_text(shown, side)
                if shown is not None
                else Text("Select a conflict to see both sides.", style="dim")
            )
        title = Content("RESULT")
        if node is not None:
            # A path is data: Content never reads it as markup.
            title = Content.assemble(title, ("  ", ""), (node.path, "$foreground"))
            self.query_one("#result", Static).update(
                _result(node.path, self.preview, self.choices)
            )
        self.query_one("#result-panel", Panel).retitle(title)
        self.query_one("#meaning", Static).update(
            describe_conflict(node.conflict)
            if node is not None and node.conflict is not None
            else Text(
                f"A choice here applies to every conflict in {node.path} that offers it."
                if node is not None
                else "",
                style="dim",
            )
        )
        self._show_choice(targets)

    def _show_choice(self, targets: list[MergeConflict]) -> None:
        offered = {choice for conflict in targets for choice in conflict.choices}
        picked = {
            self.choices.get(c.id) or default_choice(c) for c in targets if c.choices
        }
        for choice in ResolutionChoice:
            button = self.query_one(f"#choice-{choice.value}", RadioButton)
            button.disabled = choice not in offered
        leave = self.query_one(f"#choice-{OPEN}", RadioButton)
        leave.disabled = not any(c.choices and is_conflict(c) for c in targets)
        pressed = None
        # Mixed choices across a file's conflicts press no button.
        if offered and len(picked) == 1:
            (only,) = picked
            value = only.value if only else OPEN
            pressed = self.query_one(f"#choice-{value}", RadioButton)
        self.query_one("#choice", Choice).show(pressed)

    def _choose(self, choice: ResolutionChoice | None) -> None:
        """Settle the highlighted row's decisions; a settled conflict moves on."""
        node = self._highlighted()
        settled: list[MergeConflict] = []
        for conflict in self._targets(node):
            if choice is not None and choice not in conflict.choices:
                continue
            if choice is None and not is_conflict(conflict):
                continue
            if not conflict.choices or self.choices.get(conflict.id) == choice:
                continue
            if choice is None:
                del self.choices[conflict.id]
            else:
                self.choices[conflict.id] = choice
            settled.append(conflict)
        if not settled:
            return
        tree = self._tree()
        tree.relabel()
        self._status(summary(self.conflicts, self.choices))
        if choice is not None and any(is_conflict(c) for c in settled):
            tree.next_open()
        self._show(self._highlighted())
        self.refresh_preview()

    def _status(self, message: Text, *, error: bool = False) -> None:
        subtitle = self.query_one("#subtitle", Static)
        subtitle.update(message)
        subtitle.set_class(error, "-error")

    def _refresh_apply(self) -> None:
        self.query_one("#apply", Button).disabled = self._failed

    @on(Tree.NodeHighlighted, "#conflicts")
    def show_conflict(self, event: Tree.NodeHighlighted[Node]) -> None:
        """Show the highlighted conflict's sides and the file's result."""
        # A root is never a row: listing the decisions replaces the hidden
        # root, and its late highlight must not blank the row shown at mount.
        if event.node.parent is None:
            return
        self._show(event.node.data)

    @on(RadioSet.Changed, "#choice")
    def pick(self, event: RadioSet.Changed) -> None:
        """Settle the highlighted conflict, or its file's, with the pressed choice."""
        value = str(event.pressed.id).removeprefix("choice-")
        self._choose(None if value == OPEN else ResolutionChoice(value))

    def key_rows(self) -> KeyRows:
        """The conflict screen's keys."""
        return (
            ("↑ ↓", "Move between conflicts"),
            ("pgup pgdn", "Scroll both sides"),
            ("space", "Fold or unfold a file"),
            ("k", "Keep mine"),
            ("u", "Take the update"),
            ("b", "Keep both, for overlapping lines"),
            ("x", "Leave open"),
            ("n", "Next open conflict"),
            ("tab", "Next control"),
            ("shift+tab", "Previous control"),
            ("a", "Apply the sync"),
            ("esc", "Cancel, after asking"),
            ("^c", "Quit immediately"),
        )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable a choice no highlighted conflict offers."""
        if action == "choose":
            targets = self._targets(self._highlighted())
            offered = {choice for conflict in targets for choice in conflict.choices}
            value = str(parameters[0]) if parameters else OPEN
            if value == OPEN:
                return any(c.choices and is_conflict(c) for c in targets)
            return value in offered
        return True

    def action_choose(self, value: str) -> None:
        """Settle the highlighted conflict, or its file's, by key."""
        self._choose(None if value == OPEN else ResolutionChoice(value))

    def action_next_open(self) -> None:
        """Highlight the next conflict that is still open, wrapping around."""
        self._tree().next_open()

    def action_scroll_sides(self, direction: int) -> None:
        """Page both sides together without leaving the list."""
        for pane in self.query(".side").results(VerticalScroll):
            if direction > 0:
                pane.scroll_page_down(animate=False)
            else:
                pane.scroll_page_up(animate=False)

    @on(Button.Pressed, "#cancel")
    def _cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#apply")
    def action_apply(self) -> None:
        """Exit with the choices; the sync applies after the app has exited."""
        if not self.query_one("#apply", Button).disabled:
            self.app.exit(dict(self.choices))
