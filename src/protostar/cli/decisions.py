"""How a decision reads in plain words, wherever one is shown.

Reasons stay machine codes in JSON. People see a sentence saying what
happened, what Protostar does by default, and the command that chooses
otherwise. ``status``, ``diff``, ``sync``, ``init --dry-run``, and the TUI
screens all read their wording from here.
"""

from collections.abc import Sequence
from typing import cast

from rich.console import Group, RenderableType
from rich.text import Text

from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    describe_location,
)

__all__ = [
    "MEANING",
    "SETTLED",
    "TAGS",
    "conflict_lines",
    "preserved_lines",
    "proposal_lines",
    "resolved_line",
    "where",
]

LOCAL, DESIRED, BOTH = ResolutionChoice

MEANING = {
    ConflictReason.DIVERGED: "You and the update both changed it.",
    ConflictReason.TYPE_MISMATCH: (
        "You and the update changed it to different kinds of value."
    ),
    ConflictReason.UNOWNED: "It was in your file before Protostar managed it.",
    ConflictReason.DELETED_ANCESTOR: "You deleted it, and the update changed it.",
    ConflictReason.RETRACTED: "You edited it, and the update no longer includes it.",
    ConflictReason.DUPLICATE_IDENTITY: (
        "It's defined more than once, so Protostar can't tell which copy to update."
    ),
    ConflictReason.UNSAFE_PIN: (
        "The update would move your pinned hook to an older or unrelated revision."
    ),
    ConflictReason.SHARED_STRUCTURE: (
        "It shares YAML anchors with content Protostar doesn't manage."
    ),
    ConflictReason.PROPOSED: "Protostar adds it; your file doesn't have it yet.",
    ConflictReason.PRESERVED: (
        "You changed it, and the update is still Protostar's version."
    ),
}
"""Why each decision exists, as one sentence."""

TAGS = {
    ConflictReason.DIVERGED: "both changed",
    ConflictReason.TYPE_MISMATCH: "both changed",
    ConflictReason.UNOWNED: "already yours",
    ConflictReason.DELETED_ANCESTOR: "you deleted it",
    ConflictReason.RETRACTED: "no longer included",
    ConflictReason.DUPLICATE_IDENTITY: "defined twice",
    ConflictReason.UNSAFE_PIN: "older pin",
    ConflictReason.SHARED_STRUCTURE: "shared anchors",
    ConflictReason.PROPOSED: "new to your file",
    ConflictReason.PRESERVED: "your edit",
}
"""Why each decision exists, short enough for a list row."""

SETTLED = {
    LOCAL: "you kept yours",
    DESIRED: "you took the update",
    BOTH: "you kept both",
}
"""How a choice settled a decision."""

# What each choice does, where the reason changes what it means.
_KEEP = {ConflictReason.DELETED_ANCESTOR: "keep it deleted"}
_TAKE = {
    ConflictReason.UNOWNED: "replace it with the update's",
    ConflictReason.DELETED_ANCESTOR: "restore it",
    ConflictReason.RETRACTED: "remove it",
}


def where(conflict: MergeConflict) -> str:
    """Returns the file, position, and identity of a conflict on one line."""
    parts = (
        conflict.location.file,
        describe_location(conflict.location),
        # A requirement's identity is its package and marker.
        (conflict.location.identity or "").rstrip(":"),
    )
    return " ".join(part for part in parts if part)


def _heading(conflict: MergeConflict, sentence: str) -> Text:
    return Text.assemble((where(conflict), "bold"), ": ", sentence)


def _commands(
    conflict: MergeConflict,
    resolve: str,
    choices: Sequence[tuple[str, ResolutionChoice]],
) -> Group:
    """Lists each choice beside the command that makes it, aligned.

    Plain lines, not a table, so a copied command has no padding after it.
    """
    width = max(len(label) for label, _ in choices)
    return Group(
        *(
            Text.assemble(
                f"    {label.ljust(width)}  ",
                (f"{resolve} {conflict.id}={choice.value}", "cyan"),
            )
            for label, choice in choices
        )
    )


def conflict_lines(conflict: MergeConflict, resolve: str) -> RenderableType:
    """Says what an open conflict is, and how to settle it.

    Args:
        conflict: A conflict no choice has settled.
        resolve: The command that takes a choice, such as
            ``protostar sync --resolve``.

    Returns:
        The conflict and why, that the user's version stays for now, then
        one command per choice; or, with no choices, how to fix it by hand.
    """
    heading = _heading(conflict, MEANING[conflict.reason])
    if not conflict.choices:
        return Group(
            heading, Text("  Yours stays. Fix it by hand, then run sync again.")
        )
    labels = {
        LOCAL: _KEEP.get(conflict.reason, "keep yours"),
        DESIRED: _TAKE.get(conflict.reason, "use the update's"),
        BOTH: "keep both",
    }
    return Group(
        heading,
        Text("  Yours stays until you choose:"),
        _commands(
            conflict,
            resolve,
            [(labels[choice], choice) for choice in conflict.choices],
        ),
    )


def resolved_line(conflict: MergeConflict) -> Text:
    """Says how a choice settled a conflict or a kept edit."""
    settled = SETTLED[cast(ResolutionChoice, conflict.resolution)]
    return _heading(conflict, f"resolved; {settled}.")


def proposal_lines(
    proposal: MergeConflict, resolve: str | None, *, applied: bool = False
) -> RenderableType:
    """Says what a proposal adds, and how to keep it out.

    Args:
        proposal: A change into content Protostar never owned.
        resolve: The command that takes a choice, or ``None`` when no choice
            is left, as once it was applied.
        applied: Whether the run already applied it.

    Returns:
        What it adds, then whether it applies and the command that keeps it out.
    """
    if proposal.resolution is LOCAL:
        return _heading(proposal, "kept out, as you chose.")
    if applied or resolve is None:
        return _heading(proposal, "Protostar added it to your file.")
    return Group(
        _heading(proposal, MEANING[ConflictReason.PROPOSED]),
        Text("  It applies unless you keep it out:"),
        _commands(proposal, resolve, [("keep it out", LOCAL)]),
    )


def preserved_lines(
    item: MergeConflict, resolve: str, *, deletion: bool
) -> RenderableType:
    """Says that the user's own edit stays, and how to take Protostar's version.

    Args:
        item: A local edit or deletion under an unchanged update.
        resolve: The command that takes a choice.
        deletion: Whether the user deleted it rather than edited it.

    Returns:
        That the edit is kept, then the command that restores Protostar's version.
    """
    return Group(
        _heading(item, f"your {'deletion' if deletion else 'edit'} is kept."),
        _commands(item, resolve, [("use Protostar's version", DESIRED)]),
    )
