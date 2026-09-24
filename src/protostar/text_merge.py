"""Pure line-based three-way text merge and the ownership gate for owned text.

The merge is diff3 (Khanna, Kunal & Pierce, "A Formal Investigation of Diff3",
2007) over patience-diff alignments (Bram Cohen), with ``difflib`` aligning the
stretches between unique anchor lines. It runs in-process with no subprocess,
filesystem access, or terminal output, so planning and review can call it.
``reconcile_text`` applies Protostar's ownership rules around the merge.
"""

from __future__ import annotations

import difflib
import re
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from .merge import (
    MISSING,
    NO_RESOLUTIONS,
    ConflictReason,
    ConflictSides,
    LineSpan,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
    Resolutions,
)

__all__ = [
    "TextConflict",
    "TextMerge",
    "TextReconciliation",
    "is_edited",
    "merge_text",
    "reconcile_text",
]

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
        resolution: The choice that settled it, or ``None`` while open.
    """

    start: int
    base: tuple[str, ...]
    local: tuple[str, ...]
    remote: tuple[str, ...]
    resolution: ResolutionChoice | None = None

    @property
    def stop(self) -> int:
        """Returns the zero-based index just past the region in the local text."""
        return self.start + len(self.local)

    @property
    def lines(self) -> LineSpan:
        """Returns the region's one-based line span in the local text."""
        count = len(self.local)
        return LineSpan(self.start + 1 if count else self.start, count)


# Picks the resolution of one conflicting hunk, or ``None`` to leave it open.
type HunkChooser = Callable[[TextConflict], ResolutionChoice | None]


@dataclass(frozen=True)
class TextMerge:
    """The merged text, or every conflict that prevented one.

    Attributes:
        content: The merged text in the local newline style, or ``None`` when
            any region conflicts. No partially merged text is offered: two
            hunks of one change can depend on each other, so the caller keeps
            the local text whole or accepts the merge whole. A hunk counts as
            open until every hunk is resolved, since its resolution is applied
            only with the others.
        conflicts: Open conflicting regions in local line order.
        resolved: Conflicting regions settled by a resolution, in local line
            order, when every region was.
    """

    content: str | None
    conflicts: tuple[TextConflict, ...] = ()
    resolved: tuple[TextConflict, ...] = ()

    @property
    def clean(self) -> bool:
        """Returns whether the merge produced text."""
        return self.content is not None


@dataclass(frozen=True)
class TextReconciliation:
    """An ownership decision for one owned text file or region.

    Attributes:
        content: Text to write, or ``None`` to leave the local text untouched.
        baseline: Ownership to record: the accepted desired text, the previous
            baseline when an update is refused, or ``None`` while unowned.
        conflicts: Why a pending desired change was refused: one conflict per
            overlapping hunk, or one for the whole text.
        resolved: Conflicts settled by a resolution, and a restored local edit.
        preserved: The local edit or deletion kept under an unchanged update.
    """

    content: str | None
    baseline: str | None
    conflicts: tuple[MergeConflict, ...] = ()
    resolved: tuple[MergeConflict, ...] = ()
    preserved: tuple[MergeConflict, ...] = ()


def preserved_text(
    location: MergeLocation, local: bytes | None, baseline: str
) -> MergeConflict | None:
    """Returns the local edit or deletion of an owned text, or ``None`` if unedited.

    Args:
        location: The file, and region identity.
        local: The workspace bytes, or ``None`` when deleted.
        baseline: The last accepted text, which the update still matches.

    Returns:
        A ``preserved`` decision whose sides show both texts; local bytes that
        are not UTF-8 cannot be shown, so their decision has no sides.
    """
    if local is not None and not is_edited(local, baseline):
        return None
    try:
        text = local.decode("utf-8") if local is not None else None
    except UnicodeDecodeError:
        return MergeConflict(location, ConflictReason.PRESERVED)
    return MergeConflict(
        location,
        ConflictReason.PRESERVED,
        ConflictSides(baseline, MISSING if text is None else text, baseline, line=0),
    )


def reconcile_text(
    local: bytes | None,
    desired: str,
    baseline: str | None,
    location: MergeLocation,
    *,
    overwrite: bool = False,
    resolutions: Resolutions = NO_RESOLUTIONS,
) -> TextReconciliation:
    """Decides an owned text update, merging local edits with desired changes.

    An absent never-owned target is created and owned. Existing unowned text is
    never adopted, even when it equals the desired text. An owned target the
    user deleted stays deleted. An owned target the user edited is merged three
    ways against its baseline; overlapping edits keep the local text whole and
    the previous baseline, so the change stays pending. Local bytes that are not
    UTF-8 cannot be merged and are treated as edited. Explicit overwrite writes
    and owns the desired text.

    A resolution owns the desired text whichever side it keeps: unowned text
    kept is adopted as an edit of the update, and a deleted text kept stays
    deleted until the update changes again. While the update matches the
    baseline, a local edit or deletion is reported as preserved, and a
    resolution that takes the update restores the desired text.

    Args:
        local: The workspace bytes, or ``None`` when the file is absent.
        desired: The newly generated text.
        baseline: The last accepted generated text, or ``None`` if unowned.
        location: The file, and region identity, carried into conflicts.
        overwrite: Whether the collision strategy replaces local content.
        resolutions: Choices settling conflicts, keyed by conflict identity.

    Returns:
        What to write, what to own, and any refused or settled change.
    """
    target = desired.encode("utf-8")
    if overwrite or (baseline is None and local is None):
        return TextReconciliation(None if local == target else desired, desired)
    if baseline is not None and desired == baseline:
        found = preserved_text(location, local, baseline)
        settled = found.settle(resolutions) if found is not None else None
        if found is None:
            return TextReconciliation(None, baseline)
        if settled is None:
            return TextReconciliation(None, baseline, preserved=(found,))
        restore = settled.resolution is ResolutionChoice.DESIRED
        return TextReconciliation(
            desired if restore else None, baseline, resolved=(settled,)
        )
    try:
        text = local.decode("utf-8") if local is not None else None
    except UnicodeDecodeError:
        reason = ConflictReason.UNOWNED if baseline is None else ConflictReason.DIVERGED
        return TextReconciliation(None, baseline, (MergeConflict(location, reason),))
    if baseline is None or text is None:
        if (baseline is None and local == target) or desired == baseline:
            return TextReconciliation(None, baseline)
        found = MergeConflict(
            location,
            ConflictReason.UNOWNED
            if baseline is None
            else ConflictReason.DELETED_ANCESTOR,
            ConflictSides(
                MISSING if baseline is None else baseline,
                MISSING if text is None else text,
                desired,
                line=0,
            ),
        )
        settled = found.settle(resolutions)
        if settled is None:
            return TextReconciliation(None, baseline, (found,))
        keep = settled.resolution is ResolutionChoice.LOCAL
        return TextReconciliation(None if keep else desired, desired, (), (settled,))

    def hunk(overlap: TextConflict) -> MergeConflict:
        return MergeConflict(
            replace(location, lines=overlap.lines),
            ConflictReason.DIVERGED,
            ConflictSides(
                "".join(overlap.base),
                "".join(overlap.local),
                "".join(overlap.remote),
                line=overlap.start,
            ),
        )

    def choose(overlap: TextConflict) -> ResolutionChoice | None:
        settled = hunk(overlap).settle(resolutions)
        return settled.resolution if settled else None

    merged = merge_text(baseline, text, desired, choose)
    if merged.content is None:
        return TextReconciliation(
            None, baseline, tuple(hunk(overlap) for overlap in merged.conflicts)
        )
    return TextReconciliation(
        None if merged.content == text else merged.content,
        desired,
        (),
        tuple(
            replace(hunk(overlap), resolution=overlap.resolution)
            for overlap in merged.resolved
        ),
    )


def merge_text(
    base: str, local: str, remote: str, choose: HunkChooser | None = None
) -> TextMerge:
    """Merges the local and remote edits of a common ancestor, line by line.

    Lines keep their terminators, so a missing final newline is a change like
    any other. An unedited local text takes the remote text exactly. Otherwise,
    when the local text uses one newline style throughout, base and remote texts
    that consistently use the other style are converted to it first; a checkout
    that rewrites line endings is therefore not an edit, and the result keeps
    the local style. Texts with mixed endings compare exactly.

    Args:
        base: The common ancestor, such as the last accepted generated text.
        local: The workspace text.
        remote: The newly desired text.
        choose: Picks each conflicting region's resolution, or leaves it open.

    Returns:
        The merged text, or the conflicting regions.
    """
    if local == base:
        return TextMerge(remote)
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
    resolved: list[TextConflict] = []
    for chunk in _diff3(base_lines, local_lines, remote_lines):
        if not isinstance(chunk, TextConflict):
            merged.extend(chunk)
            continue
        choice = choose(chunk) if choose is not None else None
        if choice is None:
            conflicts.append(chunk)
            continue
        resolved.append(replace(chunk, resolution=choice))
        if choice is not ResolutionChoice.DESIRED:
            merged.extend(chunk.local)
        if choice is not ResolutionChoice.LOCAL:
            merged.extend(chunk.remote)
    if conflicts:
        # Resolutions apply only together, so every hunk stays open.
        opened = [replace(chunk, resolution=None) for chunk in resolved]
        return TextMerge(None, tuple(sorted([*conflicts, *opened], key=_start)))
    return TextMerge("".join(merged), (), tuple(resolved))


def _start(conflict: TextConflict) -> int:
    return conflict.start


def is_edited(local: bytes, baseline: str) -> bool:
    """Returns whether local bytes differ from a baseline beyond newline style.

    Args:
        local: The workspace bytes.
        baseline: The last accepted text.

    Returns:
        Whether the merge would treat the local text as edited.
    """
    try:
        text = local.decode("utf-8")
    except UnicodeDecodeError:
        return True
    newline = _newline(text)
    return text != (baseline if newline is None else _restyle(baseline, newline))


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
