"""How a conflict's sides and choices read, shared by every screen that settles one."""

import difflib
import json
from pathlib import Path
from typing import Any

import tomlkit
from rich.console import Group, RenderableType
from rich.text import Text

from protostar.errors import ProtostarError
from protostar.merge import (
    MISSING,
    MergeConflict,
    ResolutionChoice,
    Value,
    describe_location,
)
from protostar.yaml_ast import encode_yaml_baseline

LOCAL, DESIRED, BOTH = ResolutionChoice

# What each choice does, as the list and the choice buttons say it.
SAID = {LOCAL: "keep mine", DESIRED: "take update", BOTH: "keep both"}
KEYS = {LOCAL: "k", DESIRED: "u", BOTH: "b"}
_TAG_STYLES = {LOCAL: "cyan", DESIRED: "green", BOTH: "yellow"}
OPEN = "open"
"""The choice button that leaves a conflict open."""


def diff_text(diff: str) -> Text:
    """Colors a unified diff whose lines stay literal text, never markup.

    Args:
        diff: A unified diff.

    Returns:
        The diff with added, removed, and hunk lines styled.
    """
    text = Text()
    for line in diff.splitlines(keepends=True):
        if line.startswith(("+++", "---")):
            style = "bold"
        elif line.startswith("+"):
            style = "green"
        elif line.startswith("-"):
            style = "red"
        elif line.startswith("@@"):
            style = "cyan"
        else:
            style = ""
        text.append(line, style)
    text.rstrip()
    return text


def _structured(conflict: MergeConflict, value: Value) -> str:
    """Renders a value in its file's own format, keyed by its last key."""
    keys = conflict.location.keys
    data: Any = {keys[-1]: value} if keys else value
    suffix = Path(conflict.location.file).suffix
    try:
        if suffix == ".toml" and isinstance(data, dict):
            return tomlkit.dumps(data).rstrip("\n")
        if suffix in (".yaml", ".yml") and isinstance(data, dict):
            return encode_yaml_baseline(data).rstrip("\n")
    except (ProtostarError, ValueError, TypeError):
        pass  # Shown as JSON below; a presenter never raises.
    # Dates read as their ISO form, as machine output shows them.
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _side(conflict: MergeConflict, side: str) -> str | None:
    """Returns one side as text, or ``None`` when it holds nothing."""
    sides = conflict.sides
    if sides is None:
        return None
    value = sides.local if side == "local" else sides.desired
    if value is MISSING:
        return None
    if sides.text:
        return str(value)
    return _structured(conflict, value) + "\n"


def side_text(conflict: MergeConflict, side: str) -> Text:
    """Renders what one side holds where a conflict is.

    Args:
        conflict: A conflict with sides.
        side: ``"local"`` or ``"desired"``.

    Returns:
        The side's text or value as literal text, or why it has none.
    """
    if conflict.sides is None:
        return Text("Protostar can't show this side.", style="dim")
    text = _side(conflict, side)
    if text is None:
        return Text(
            "Deleted." if side == "local" else "No longer generated.", style="dim"
        )
    return Text(text.rstrip("\n")) if text else Text("No lines.", style="dim")


def sides_diff(conflict: MergeConflict) -> RenderableType:
    """Renders a conflict as a diff from the local side to the update's.

    Args:
        conflict: A conflict with sides.

    Returns:
        The diff, or both sides' notes when either holds nothing.
    """
    local, desired = _side(conflict, "local"), _side(conflict, "desired")
    if local is None or desired is None:
        return Group(
            Text.assemble(("Yours: ", "bold"), side_text(conflict, "local")),
            Text.assemble(("Update: ", "bold"), side_text(conflict, "desired")),
        )
    lines = difflib.unified_diff(
        local.splitlines(keepends=True),
        desired.splitlines(keepends=True),
        "yours",
        "update",
    )
    return diff_text(
        "".join(line if line.endswith("\n") else line + "\n" for line in lines)
    )


def describe_conflict(conflict: MergeConflict) -> Text:
    """Says in a sentence what the conflict is and what the choices mean.

    Args:
        conflict: The conflict to describe.

    Returns:
        One or two sentences for the space above the choices.
    """
    # A key path is data, so it keeps its case.
    where = describe_location(conflict.location) or "Whole file"
    reason = conflict.reason.value
    if not conflict.choices:
        return Text(
            f"{where} ({reason}) can only be fixed by hand. "
            "Edit the file, then run sync again.",
            style="dim",
        )
    meaning = {
        "diverged": "You and the update both changed it.",
        "type-mismatch": "You and the update changed it to different kinds of value.",
        "unowned": "It was already there before Protostar managed it.",
        "deleted-ancestor": "You deleted it, and the update changed it.",
        "retracted": "You edited it, and the update no longer generates it.",
    }.get(reason, "")
    return Text.assemble((where, "bold"), f"  {meaning}")


def tag(conflict: MergeConflict, choice: ResolutionChoice | None) -> Text:
    """Returns what happens to a conflict, as its list row says it.

    Args:
        conflict: The conflict.
        choice: The choice made for it, or ``None`` while open.

    Returns:
        A short colored tag.
    """
    if not conflict.choices:
        return Text("by hand", "dim")
    if choice is None:
        return Text(OPEN, "red")
    return Text(SAID[choice], _TAG_STYLES[choice])
