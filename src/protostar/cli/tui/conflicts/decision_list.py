"""The list of decisions a review asks for, shared by init's review and sync's.

Rows group the decisions by file, the files with conflicts first. Each row
starts with what happens to its decision, so the column reads as a checklist:
the choice made, the default dimmed, or ``open`` while a conflict still waits.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from rich.text import Text
from textual.binding import Binding, BindingType
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from protostar.cli.decisions import TAGS
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    describe_location,
)

from ..keys import MOVE
from .sides import OPEN, SAID, is_conflict, tag

# Every status fits the column, so the locations after it line up.
_STATUS_WIDTH = max(len(said) for said in (*SAID.values(), OPEN, "by hand")) + 2


@dataclass(frozen=True)
class Node:
    """A row of the decision list: a file, or one decision in it.

    Attributes:
        path: The file.
        conflict: The decision, or ``None`` for the file's own row.
    """

    path: str
    conflict: MergeConflict | None = None


def decision_label(conflict: MergeConflict, choice: ResolutionChoice | None) -> Text:
    """Labels a decision's row with where it is, why, and what happens to it.

    Args:
        conflict: The conflict, proposal, or preserved edit.
        choice: The choice made for it, or ``None`` when none was.

    Returns:
        The row's label.
    """
    where = describe_location(conflict.location) or "whole file"
    # A requirement's identity is its package and marker; a region's is
    # internal, and its lines already say where it is.
    identity = (conflict.location.identity or "").rstrip(":")
    if identity and conflict.location.keys:
        where = f"{where} {identity}"
    status = tag(conflict, choice)
    status.pad_right(_STATUS_WIDTH - status.cell_len)
    return Text.assemble(status, where, "  ", (TAGS[conflict.reason], "dim"))


def _file_label(path: str, decisions: int) -> Text:
    return Text.assemble(path, (f"  {decisions}", "dim"))


def open_conflicts(
    decisions: Sequence[MergeConflict], choices: Mapping[str, ResolutionChoice]
) -> list[MergeConflict]:
    """Returns the conflicts a choice could settle that none has yet.

    Args:
        decisions: The review's decisions.
        choices: The choices made so far.

    Returns:
        The open conflicts, in list order.
    """
    return [
        c for c in decisions if c.choices and is_conflict(c) and c.id not in choices
    ]


class DecisionList(Tree[Node]):
    """Every decision by file, each row tagged with what happens to it.

    The list reads the screen's choices, so a row changes as soon as a choice
    is made, before the review behind it is prepared again.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "Up", group=MOVE),
        Binding("down", "cursor_down", "Down", group=MOVE),
    ]

    def __init__(
        self,
        choices: Mapping[str, ResolutionChoice],
        *,
        id: str | None = None,  # noqa: A002 - Textual's name
    ) -> None:
        """Create the list.

        Args:
            choices: The screen's choices, read whenever a row is labelled.
            id: The widget's id.
        """
        super().__init__(Text("."), id=id)
        self.show_root = False
        self.choices = choices
        self.decisions: tuple[MergeConflict, ...] = ()
        self._rows: dict[str, TreeNode[Node]] = {}
        # Where each decision and file first showed; a row never moves after.
        self._seen: dict[str, int] = {}

    def show(self, decisions: Sequence[MergeConflict]) -> Node | None:
        """List the decisions, keeping the highlighted row where it still exists.

        Without one, the first open conflict is highlighted, else the first row.

        Args:
            decisions: The review's decisions.

        Returns:
            The row highlighted, once the list has refreshed.
        """
        current = self.highlighted()
        self.decisions = tuple(decisions)
        self.clear()
        self._rows = {}
        for conflict in self.decisions:
            for key in (conflict.location.file, conflict.id):
                self._seen.setdefault(key, len(self._seen))
        # What needs the user comes first: files with conflicts, and in a file
        # its conflicts before the changes that apply by default.
        ordered = sorted(
            self.decisions,
            key=lambda c: (not is_conflict(c), self._seen[c.id]),
        )
        conflicted = {c.location.file for c in ordered if is_conflict(c)}
        by_file: dict[str, list[MergeConflict]] = {}
        for conflict in sorted(
            ordered,
            key=lambda c: (
                c.location.file not in conflicted,
                self._seen[c.location.file],
            ),
        ):
            by_file.setdefault(conflict.location.file, []).append(conflict)
        self.decisions = tuple(c for group in by_file.values() for c in group)
        for path, conflicts in by_file.items():
            if (
                conflicted
                and path not in conflicted
                and path == next(p for p in by_file if p not in conflicted)
            ):
                # What follows needs no choice: each row happens by default.
                self.root.add_leaf(Text("Happens unless you choose otherwise", "dim"))
            parent = self.root.add(
                _file_label(path, len(conflicts)), Node(path), expand=True
            )
            self._rows[path] = parent
            for conflict in conflicts:
                self._rows[conflict.id] = parent.add_leaf(
                    decision_label(conflict, self.choices.get(conflict.id)),
                    Node(path, conflict),
                )
        target = None
        if current is not None:
            key = current.conflict.id if current.conflict else current.path
            target = self._rows.get(key)
        if target is None:
            first = next(iter(open_conflicts(self.decisions, self.choices)), None)
            target = self._rows[first.id] if first else None
        if target is None:
            target = next(iter(self._rows.values()), None)
        if target is None:
            return None
        self.call_after_refresh(self.move_cursor, target)
        return target.data

    def relabel(self) -> None:
        """Say again what happens to each decision, after a choice."""
        for conflict in self.decisions:
            self._rows[conflict.id].set_label(
                decision_label(conflict, self.choices.get(conflict.id))
            )

    def highlighted(self) -> Node | None:
        """Returns the highlighted row, or ``None`` when the list is empty."""
        cursor = self.cursor_node
        return cursor.data if cursor is not None else None

    def targets(self, node: Node | None = None) -> list[MergeConflict]:
        """Returns the decisions a choice on a row settles.

        A decision's row settles it alone; a file's row, every decision in it
        except the edits it preserves.

        Args:
            node: The row, or ``None`` for the highlighted one.

        Returns:
            The decisions, in list order.
        """
        node = node or self.highlighted()
        if node is None:
            return []
        if node.conflict is not None:
            return [node.conflict]
        # A preserved edit is deliberate, so only its own row takes the update.
        return [
            c
            for c in self.decisions
            if c.location.file == node.path and c.reason is not ConflictReason.PRESERVED
        ]

    def next_open(self, *, here: bool = False) -> bool:
        """Highlight the next open conflict after the highlighted row, wrapping.

        Args:
            here: Whether a highlighted open conflict counts as the next.

        Returns:
            Whether an open conflict was found.
        """
        waiting = open_conflicts(self.decisions, self.choices)
        if not waiting:
            return False
        node = self.highlighted()
        if here and node is not None and node.conflict in waiting:
            return True
        order = [c for c in self.decisions if c.choices and is_conflict(c)]
        if node is not None and node.conflict in order:
            start = order.index(node.conflict) + 1
        else:
            # From a file's row, its own conflicts come first.
            start = next(
                (
                    index
                    for index, c in enumerate(order)
                    if node is not None and c.location.file == node.path
                ),
                0,
            )
        target = next(c for c in order[start:] + order[:start] if c in waiting)
        self.move_cursor(self._rows[target.id])
        return True
