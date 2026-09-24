"""Choose, conflict by conflict, which content a sync keeps."""

import asyncio
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from rich.console import Group, RenderableType
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import Button, Footer, RadioButton, RadioSet, Static, Tree
from textual.widgets.tree import TreeNode

from protostar.cli.reviews import unified_diff
from protostar.errors import ProtostarError
from protostar.lifecycle import PreparedProject
from protostar.merge import MergeConflict, ResolutionChoice, describe_location
from protostar.preparation import PreparedReview

from ..chrome import Heading, Headline, Masthead, Panel
from ..keys import MOVE, ActionBar, Choice, KeyboardScreen, KeyRows, key_label
from .sides import (
    KEYS,
    OPEN,
    SAID,
    describe_conflict,
    diff_text,
    side_text,
    tag,
)


@dataclass(frozen=True)
class Node:
    """A row of the conflict list: a file, or one conflict in it.

    Attributes:
        path: The file.
        conflict: The conflict, or ``None`` for the file's own row.
    """

    path: str
    conflict: MergeConflict | None = None


def _label(conflict: MergeConflict, choice: ResolutionChoice | None) -> Text:
    where = describe_location(conflict.location) or "whole file"
    return Text.assemble(
        where, ("  ", ""), (conflict.reason.value, "dim"), "  ", tag(conflict, choice)
    )


def _file_label(path: str, count: int) -> Text:
    return Text.assemble(path, (f"  {count}", "dim"))


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def summary(
    conflicts: tuple[MergeConflict, ...], choices: Mapping[str, ResolutionChoice]
) -> Text:
    """Counts the conflicts by what happens to them.

    Args:
        conflicts: Every open conflict of the review.
        choices: The choices made so far.

    Returns:
        One line for the screen's subtitle.
    """
    counts = Counter(
        "by hand"
        if not conflict.choices
        else ("resolved" if conflict.id in choices else OPEN)
        for conflict in conflicts
    )
    parts = [_count(len(conflicts), "conflict")]
    parts.extend(f"{counts[kind]} {kind}" for kind in ("resolved", OPEN))
    if counts["by hand"]:
        parts.append(f"{counts['by hand']} by hand")
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
        parts.append(
            Text(
                f"Choose for every conflict in {path} to apply any of them: "
                "its overlapping lines change together.",
                style="yellow",
            )
        )
    if edit is not None:
        parts.append(diff_text(unified_diff(edit)))
    else:
        parts.append(Text("The file stays as it is.", style="dim"))
    return Group(*parts)


_SCROLL = Binding.Group("Scroll sides")


class ConflictTree(Tree[Node]):
    """The conflicts by file; page keys scroll both sides together."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "Up", group=MOVE),
        Binding("down", "cursor_down", "Down", group=MOVE),
        Binding("pageup", "screen.scroll_sides(-1)", "Up", group=_SCROLL),
        Binding("pagedown", "screen.scroll_sides(1)", "Down", group=_SCROLL),
    ]


class ConflictScreen(KeyboardScreen[dict[str, ResolutionChoice]]):
    """Choose which content each conflict keeps, then apply the sync.

    The choices only decide; the sync applies after the app exits. A file row
    takes a choice for every conflict in it that offers that choice.
    """

    LEAVE = "Leave without syncing?"

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
        self.conflicts = project.review.conflicts
        self.choices: dict[str, ResolutionChoice] = {}
        self.preview: PreparedReview | None = None
        self._failed = False
        self._rows: dict[str, TreeNode[Node]] = {}

    def compose(self) -> ComposeResult:
        """Compose the conflict list beside both sides, the choices below them."""
        yield Masthead("sync", "conflicts")
        yield Headline("Resolve conflicts", summary(self.conflicts, self.choices))
        with Horizontal(id="body"):
            with Panel("Conflicts", id="conflicts-panel"):
                yield ConflictTree(Text("."), id="conflicts")
            with Vertical(id="sides-column"):
                with Horizontal(id="sides"):
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
                with Vertical(id="decisions"):
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
        """List the conflicts, highlight the first, and prepare the result."""
        tree = self.query_one("#conflicts", ConflictTree)
        tree.show_root = False
        tree.focus()
        by_file: dict[str, list[MergeConflict]] = {}
        for conflict in self.conflicts:
            by_file.setdefault(conflict.location.file, []).append(conflict)
        first = None
        for path, conflicts in by_file.items():
            parent = tree.root.add(
                _file_label(path, len(conflicts)), Node(path), expand=True
            )
            self._rows[path] = parent
            for conflict in conflicts:
                self._rows[conflict.id] = parent.add_leaf(
                    _label(conflict, None), Node(path, conflict)
                )
                if first is None and conflict.choices:
                    first = self._rows[conflict.id]
        target = first or next(iter(self._rows.values()), None)
        if target is not None:
            tree.call_after_refresh(tree.move_cursor, target)
        self.refresh_preview()

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

    def _highlighted(self) -> Node | None:
        cursor = self.query_one("#conflicts", ConflictTree).cursor_node
        return cursor.data if cursor is not None else None

    def _targets(self, node: Node | None) -> list[MergeConflict]:
        if node is None:
            return []
        if node.conflict is not None:
            return [node.conflict]
        return [c for c in self.conflicts if c.location.file == node.path]

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
        picked = {self.choices.get(c.id) for c in targets if c.choices}
        for choice in ResolutionChoice:
            button = self.query_one(f"#choice-{choice.value}", RadioButton)
            button.disabled = choice not in offered
        leave = self.query_one(f"#choice-{OPEN}", RadioButton)
        leave.disabled = not offered
        pressed = None
        # Mixed choices across a file's conflicts press no button.
        if offered and len(picked) == 1:
            (only,) = picked
            value = only.value if only else OPEN
            pressed = self.query_one(f"#choice-{value}", RadioButton)
        self.query_one("#choice", Choice).show(pressed)

    def _choose(self, choice: ResolutionChoice | None) -> None:
        node = self._highlighted()
        changed = False
        for conflict in self._targets(node):
            if choice is not None and choice not in conflict.choices:
                continue
            if not conflict.choices or self.choices.get(conflict.id) == choice:
                continue
            if choice is None:
                del self.choices[conflict.id]
            else:
                self.choices[conflict.id] = choice
            self._rows[conflict.id].set_label(_label(conflict, choice))
            changed = True
        if changed:
            self._status(summary(self.conflicts, self.choices))
            self._show(node)
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
            return bool(offered) and (value == OPEN or value in offered)
        return True

    def action_choose(self, value: str) -> None:
        """Settle the highlighted conflict, or its file's, by key."""
        self._choose(None if value == OPEN else ResolutionChoice(value))

    def action_next_open(self) -> None:
        """Highlight the next conflict that is still open, wrapping around."""
        tree = self.query_one("#conflicts", ConflictTree)
        node = self._highlighted()
        order = [c for c in self.conflicts if c.choices]
        start = (
            order.index(node.conflict) + 1
            if node is not None and node.conflict in order
            else 0
        )
        for conflict in order[start:] + order[:start]:
            if conflict.id not in self.choices:
                tree.move_cursor(self._rows[conflict.id])
                return

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
