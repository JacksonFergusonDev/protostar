"""Pure line-based three-way text merge; adapters decide what a conflict does to a file.

The merge is diff3 (Khanna, Kunal & Pierce, "A Formal Investigation of Diff3",
2007) over patience-diff alignments (Bram Cohen), with ``difflib`` aligning the
stretches between unique anchor lines. It runs in-process with no subprocess,
filesystem access, or terminal output, so planning and review can call it.
"""

from __future__ import annotations

import difflib
import re
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = ["TextConflict", "TextMerge", "merge_text"]

type _Lines = Sequence[str]
type _Match = tuple[int, int]

_LINE = re.compile(r"[^\n]*\n|[^\n]+")

# Above this many compared line pairs, a stretch with no unique anchor line is
# treated as wholly changed instead of aligned by difflib, which is quadratic in
# the worst case. Losing matches only coarsens hunks: the merge stays correct
# and can at most report a conflict where a finer alignment would not.
_FALLBACK_CELLS = 1_000_000


@dataclass(frozen=True)
class TextConflict:
    """One region that both sides changed differently.

    Attributes:
        start: Zero-based index of the region's first line in the local text.
        base: The region's lines in the common ancestor.
        local: The region's lines in the local text.
        remote: The region's lines in the remote text.
    """

    start: int
    base: tuple[str, ...]
    local: tuple[str, ...]
    remote: tuple[str, ...]

    @property
    def stop(self) -> int:
        """Returns the zero-based index just past the region in the local text."""
        return self.start + len(self.local)


@dataclass(frozen=True)
class TextMerge:
    """The merged text, or every conflict that prevented one.

    Attributes:
        content: The merged text in the local newline style, or ``None`` when
            any region conflicts. No partially merged text is offered: two
            hunks of one change can depend on each other, so the caller keeps
            the local text whole or accepts the merge whole.
        conflicts: Conflicting regions in local line order.
    """

    content: str | None
    conflicts: tuple[TextConflict, ...] = ()

    @property
    def clean(self) -> bool:
        """Returns whether the merge produced text."""
        return self.content is not None


def merge_text(base: str, local: str, remote: str) -> TextMerge:
    """Merges the local and remote edits of a common ancestor, line by line.

    Lines keep their terminators, so a missing final newline is a change like
    any other. When the local text uses one newline style throughout, base and
    remote texts that consistently use the other style are converted to it
    first; a checkout that rewrites line endings is therefore not an edit, and
    the result keeps the local style. Texts with mixed endings compare exactly.

    Args:
        base: The common ancestor, such as the last accepted generated text.
        local: The workspace text.
        remote: The newly desired text.

    Returns:
        The merged text, or the conflicting regions.
    """
    newline = _newline(local)
    if newline is not None:
        base, remote = _restyle(base, newline), _restyle(remote, newline)
    if local in (base, remote):
        return TextMerge(remote)
    if remote == base:
        return TextMerge(local)
    base_lines, local_lines, remote_lines = (
        _split(text) for text in (base, local, remote)
    )
    merged: list[str] = []
    conflicts: list[TextConflict] = []
    for chunk in _diff3(base_lines, local_lines, remote_lines):
        if isinstance(chunk, TextConflict):
            conflicts.append(chunk)
        else:
            merged.extend(chunk)
    if conflicts:
        return TextMerge(None, tuple(conflicts))
    return TextMerge("".join(merged))


def _split(text: str) -> list[str]:
    """Splits on newlines only, keeping terminators, unlike ``str.splitlines``."""
    return _LINE.findall(text)


def _newline(text: str) -> str | None:
    """Returns the one newline style a text uses throughout, if any."""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    if crlf and not lf:
        return "\r\n"
    if lf and not crlf:
        return "\n"
    return None


def _restyle(text: str, newline: str) -> str:
    """Converts a text that consistently uses the other newline style."""
    style = _newline(text)
    if style is None or style == newline:
        return text
    return text.replace(style, newline)


# --- diff3 ------------------------------------------------------------------


def _diff3(
    base: _Lines, local: _Lines, remote: _Lines
) -> list[tuple[str, ...] | TextConflict]:
    """Splits three texts into stable runs and resolved or conflicting hunks.

    A stable run is a stretch of base lines that both sides kept, each aligned
    with the next line on both sides. Between stable runs, each side's hunk is
    resolved by which sides changed it.
    """
    to_local = dict(_matches(base, local))
    to_remote = dict(_matches(base, remote))
    # Base lines both sides kept, in order: the points hunks resynchronize at.
    anchors = sorted(to_local.keys() & to_remote.keys())
    chunks: list[tuple[str, ...] | TextConflict] = []
    o = a = b = 0
    while True:
        run = 0
        while (
            o + run < len(base)
            and to_local.get(o + run) == a + run
            and to_remote.get(o + run) == b + run
        ):
            run += 1
        if run:
            chunks.append(tuple(base[o : o + run]))
            o, a, b = o + run, a + run, b + run
            continue
        index = bisect_left(anchors, o)
        if index < len(anchors):
            j = anchors[index]
            a_end, b_end = to_local[j], to_remote[j]
        else:
            j, a_end, b_end = len(base), len(local), len(remote)
        if (o, a, b) != (j, a_end, b_end):
            chunks.extend(
                _resolve(
                    a, tuple(base[o:j]), tuple(local[a:a_end]), tuple(remote[b:b_end])
                )
            )
        if index == len(anchors):
            return chunks
        o, a, b = j, a_end, b_end


def _resolve(
    start: int,
    base: tuple[str, ...],
    local: tuple[str, ...],
    remote: tuple[str, ...],
) -> list[tuple[str, ...] | TextConflict]:
    """Takes the side that changed a hunk, or narrows a conflict to what differs.

    Lines both sides added identically at the edges of a conflict leave it, as
    in git's ``zdiff3`` style, so the conflict spans only disagreeing lines.
    """
    if local in (base, remote):
        return [remote]
    if remote == base:
        return [local]
    head = 0
    while head < min(len(local), len(remote)) and local[head] == remote[head]:
        head += 1
    tail = 0
    while (
        tail < min(len(local), len(remote)) - head
        and local[-1 - tail] == remote[-1 - tail]
    ):
        tail += 1
    return [
        local[:head],
        TextConflict(
            start + head,
            base,
            local[head : len(local) - tail],
            remote[head : len(remote) - tail],
        ),
        local[len(local) - tail :],
    ]


# --- patience diff ------------------------------------------------------------


def _matches(a: _Lines, b: _Lines) -> list[_Match]:
    """Aligns two texts, returning increasing pairs of equal line indexes.

    Patience diff: trim the common head and tail, anchor on the longest
    increasing run of lines that occur exactly once in both sides, and repeat
    between anchors. Stretches with no such line fall back to ``difflib``.
    """
    matches: list[_Match] = []
    pending = [(0, len(a), 0, len(b))]
    while pending:
        alo, ahi, blo, bhi = pending.pop()
        while alo < ahi and blo < bhi and a[alo] == b[blo]:
            matches.append((alo, blo))
            alo, blo = alo + 1, blo + 1
        while alo < ahi and blo < bhi and a[ahi - 1] == b[bhi - 1]:
            ahi, bhi = ahi - 1, bhi - 1
            matches.append((ahi, bhi))
        if alo == ahi or blo == bhi:
            continue
        anchors = _unique_anchors(a, b, alo, ahi, blo, bhi)
        if not anchors:
            matches.extend(_fallback(a, b, alo, ahi, blo, bhi))
            continue
        for ai, bi in anchors:
            pending.append((alo, ai, blo, bi))
            matches.append((ai, bi))
            alo, blo = ai + 1, bi + 1
        pending.append((alo, ahi, blo, bhi))
    matches.sort()
    return matches


def _unique_anchors(
    a: _Lines, b: _Lines, alo: int, ahi: int, blo: int, bhi: int
) -> list[_Match]:
    """Returns the longest increasing run of lines unique to both ranges."""
    # A line maps to its only index in the range, or to None once it repeats.
    in_a: dict[str, int | None] = {}
    for i in range(alo, ahi):
        in_a[a[i]] = None if a[i] in in_a else i
    in_b: dict[str, int | None] = {}
    for j in range(blo, bhi):
        if in_a.get(b[j]) is not None:
            in_b[b[j]] = None if b[j] in in_b else j
    pairs: list[_Match] = []
    for line, b_index in in_b.items():
        a_index = in_a[line]
        if a_index is not None and b_index is not None:
            pairs.append((a_index, b_index))
    pairs.sort(key=lambda pair: pair[1])
    return _longest_increasing(pairs)


def _longest_increasing(pairs: list[_Match]) -> list[_Match]:
    """Patience sorting: the longest run of pairs increasing in both indexes.

    ``pairs`` arrive ordered by their second index, which is unique, so only the
    first index needs to increase.
    """
    tops: list[int] = []
    top_pair: list[int] = []
    previous = [-1] * len(pairs)
    for index, (i, _) in enumerate(pairs):
        pile = bisect_left(tops, i)
        previous[index] = top_pair[pile - 1] if pile else -1
        if pile == len(tops):
            tops.append(i)
            top_pair.append(index)
        else:
            tops[pile], top_pair[pile] = i, index
    run: list[_Match] = []
    index = top_pair[-1] if top_pair else -1
    while index != -1:
        run.append(pairs[index])
        index = previous[index]
    return run[::-1]


def _fallback(
    a: _Lines, b: _Lines, alo: int, ahi: int, blo: int, bhi: int
) -> list[_Match]:
    """Aligns a stretch with no unique anchor, within a bounded cost."""
    if (ahi - alo) * (bhi - blo) > _FALLBACK_CELLS:
        return []
    matcher = difflib.SequenceMatcher(None, a[alo:ahi], b[blo:bhi], autojunk=False)
    return [
        (alo + i + k, blo + j + k)
        for i, j, size in matcher.get_matching_blocks()
        for k in range(size)
    ]
