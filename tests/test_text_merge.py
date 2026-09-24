from itertools import pairwise

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from protostar import text_merge
from protostar.merge import (
    ConflictReason,
    ConflictSides,
    LineSpan,
    MergeLocation,
    ResolutionChoice,
)
from protostar.text_merge import (
    TextConflict,
    TextMerge,
    TextReconciliation,
    is_edited,
    merge_text,
    reconcile_text,
)

# A few distinct lines, so generated texts repeat lines the way real files do.
LINE = st.sampled_from(["a\n", "b\n", "c\n", "\n", "}\n", "    pass\n", "x"])
TEXT = st.lists(LINE, max_size=16).map("".join)
PROPERTY = settings(max_examples=300, deadline=None)


def lf_text(lines: list[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


@pytest.mark.parametrize(
    ("base", "local", "remote", "merged"),
    [
        pytest.param("a\nb\n", "a\nb\n", "a\nb\n", "a\nb\n", id="unchanged"),
        pytest.param("a\nb\n", "a\nX\n", "a\nb\n", "a\nX\n", id="local-only"),
        pytest.param("a\nb\n", "a\nb\n", "a\nY\n", "a\nY\n", id="remote-only"),
        pytest.param("a\nb\n", "a\nZ\n", "a\nZ\n", "a\nZ\n", id="same-change"),
        pytest.param(
            "a\nb\nc\nd\ne\n",
            "A\nb\nc\nd\ne\n",
            "a\nb\nc\nd\nE\n",
            "A\nb\nc\nd\nE\n",
            id="separate-hunks",
        ),
        pytest.param(
            "a\nb\nc\n",
            "a\nb\nc\nlocal\n",
            "remote\na\nb\nc\n",
            "remote\na\nb\nc\nlocal\n",
            id="insertions-at-both-ends",
        ),
        pytest.param("a\nb\nc\n", "a\nc\n", "a\nc\n", "a\nc\n", id="same-deletion"),
        pytest.param("a\nb\n", "a\nb", "a\nb\nc\n", None, id="final-newline-edit"),
        pytest.param("", "x\n", "x\n", "x\n", id="same-addition"),
        pytest.param("a\n", "", "a\n", "", id="local-emptied"),
    ],
)
def test_merges_line_edits(
    base: str, local: str, remote: str, merged: str | None
) -> None:
    assert merge_text(base, local, remote).content == merged


@pytest.mark.parametrize(
    ("base", "local", "remote"),
    [
        pytest.param("a\nb\nc\n", "a\nX\nc\n", "a\nY\nc\n", id="same-line"),
        pytest.param("a\nb\nc\n", "A\nb\nc\n", "a\nB\nc\n", id="adjacent-lines"),
        pytest.param("a\nb\n", "a\nX\nb\n", "a\nY\nb\n", id="same-insertion-point"),
        pytest.param("a\nb\nc\n", "a\nc\n", "a\nB\nc\n", id="delete-versus-edit"),
        pytest.param("", "x\n", "y\n", id="different-additions"),
    ],
)
def test_overlapping_edits_conflict(base: str, local: str, remote: str) -> None:
    result = merge_text(base, local, remote)

    assert result == TextMerge(None, result.conflicts)
    assert not result.clean
    assert result.conflicts


def test_conflict_locates_the_disagreeing_local_lines() -> None:
    result = merge_text(
        "keep\nold\nkeep\n",
        "keep\nshared\nmine\nshared tail\nkeep\n",
        "keep\nshared\ntheirs\nshared tail\nkeep\n",
    )

    # Lines both sides added identically leave the conflict, as in zdiff3.
    assert result.conflicts == (
        TextConflict(2, ("old\n",), ("mine\n",), ("theirs\n",)),
    )
    assert result.conflicts[0].stop == 3


def test_reports_every_conflict_in_local_order() -> None:
    result = merge_text(
        lf_text(["a", "b", "c", "d", "e"]),
        lf_text(["A", "b", "c", "d", "E"]),
        lf_text(["1", "b", "c", "d", "5"]),
    )

    assert [(c.start, c.local, c.remote) for c in result.conflicts] == [
        (0, ("A\n",), ("1\n",)),
        (4, ("E\n",), ("5\n",)),
    ]


def test_an_empty_local_side_marks_an_insertion_point() -> None:
    (conflict,) = merge_text("a\nb\nc\n", "a\nc\n", "a\nB\nc\n").conflicts

    assert conflict == TextConflict(1, ("b\n",), (), ("B\n",))
    assert conflict.stop == conflict.start


@pytest.mark.parametrize("separator", ["\x0c", "\x85", "\u2028", "\r"])
def test_splits_lines_on_newlines_only(separator: str) -> None:
    # str.splitlines would split here too, turning these edits into two lines.
    result = merge_text(f"a{separator}b\n", f"A{separator}b\n", f"a{separator}B\n")

    assert result.conflicts == (
        TextConflict(
            0, (f"a{separator}b\n",), (f"A{separator}b\n",), (f"a{separator}B\n",)
        ),
    )


class TestNewlineStyle:
    def test_keeps_a_crlf_checkout_of_an_unchanged_file(self) -> None:
        result = merge_text("a\nb\n", "a\r\nb\r\n", "a\nB\n")

        assert result.content == "a\r\nB\r\n"

    def test_merges_local_edits_made_in_crlf(self) -> None:
        result = merge_text("a\nb\nc\n", "A\r\nb\r\nc\r\n", "a\nb\nC\n")

        assert result.content == "A\r\nb\r\nC\r\n"

    def test_converts_a_crlf_base_for_an_lf_local(self) -> None:
        result = merge_text("a\r\nb\r\n", "a\nb\n", "a\r\nB\r\n")

        assert result.content == "a\nB\n"

    def test_an_unedited_text_takes_the_remote_style(self) -> None:
        # The old CRLF style came from the base, not from a local checkout.
        assert merge_text("a\r\nb\r\n", "a\r\nb\r\n", "a\nB\n").content == "a\nB\n"

    def test_compares_mixed_endings_exactly(self) -> None:
        # One CRLF line makes the local style ambiguous, so nothing is converted
        # and the rewritten line counts as a local edit.
        result = merge_text("a\nb\n", "a\r\nb\n", "a\nb\nc\n")

        assert result.content == "a\r\nb\nc\n"


def test_aligns_repeated_lines_within_a_bounded_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No line is unique, so only the difflib fallback can align these edits.
    case = ("x\ny\nx\n", "x\nx\ny\nx\n", "y\nx\ny\nx\ny\n")

    assert merge_text(*case).content == "y\nx\nx\ny\nx\ny\n"
    # Past the cost bound nothing aligns: both sides rewrote the whole text.
    monkeypatch.setattr(text_merge, "_FALLBACK_CELLS", 0)
    assert not merge_text(*case).clean


FILE = MergeLocation("justfile")
DIVERGED, UNOWNED, DELETED = (
    ConflictReason.DIVERGED,
    ConflictReason.UNOWNED,
    ConflictReason.DELETED_ANCESTOR,
)


@pytest.mark.parametrize(
    ("local", "baseline", "desired", "expected"),
    [
        pytest.param(None, None, "a\n", ("a\n", "a\n", None), id="create"),
        pytest.param(b"a\n", None, "a\n", (None, None, None), id="equal-unowned"),
        pytest.param(b"b\n", None, "a\n", (None, None, UNOWNED), id="unowned"),
        pytest.param(None, "a\n", "a\n", (None, "a\n", None), id="kept-deletion"),
        pytest.param(None, "a\n", "b\n", (None, "a\n", DELETED), id="deleted"),
        pytest.param(b"a\n", "a\n", "b\n", ("b\n", "b\n", None), id="update"),
        pytest.param(b"b\n", "a\n", "b\n", (None, "b\n", None), id="converged"),
        pytest.param(b"\xff\n", "a\n", "b\n", (None, "a\n", DIVERGED), id="binary"),
        pytest.param(b"\xff\n", "a\n", "a\n", (None, "a\n", None), id="binary-kept"),
        pytest.param(
            b"\xff\n", None, "a\n", (None, None, UNOWNED), id="binary-unowned"
        ),
    ],
)
def test_ownership_gate(
    local: bytes | None,
    baseline: str | None,
    desired: str,
    expected: tuple[str | None, str | None, ConflictReason | None],
) -> None:
    result = reconcile_text(local, desired, baseline, FILE)

    content, owned, reason = expected
    assert (result.content, result.baseline) == (content, owned)
    assert [c.reason for c in result.conflicts] == ([reason] if reason else [])
    assert all(c.location == FILE for c in result.conflicts)
    assert not result.resolved


def test_ownership_gate_reports_overlaps_and_overwrite_wins() -> None:
    refused = reconcile_text(b"x\n", "b\n", "a\n", FILE)

    assert (refused.content, refused.baseline) == (None, "a\n")
    (conflict,) = refused.conflicts
    assert conflict.location == MergeLocation("justfile", lines=LineSpan(1, 1))
    assert conflict.sides == ConflictSides("a\n", "x\n", "b\n", line=0)
    assert conflict.choices == tuple(ResolutionChoice)
    assert reconcile_text(b"x\n", "b\n", "a\n", FILE, overwrite=True) == (
        TextReconciliation("b\n", "b\n")
    )
    assert reconcile_text(b"b\n", "b\n", None, FILE, overwrite=True) == (
        TextReconciliation(None, "b\n")
    )


@pytest.mark.parametrize(
    ("local", "edited"),
    [(b"a\nb\n", False), (b"a\r\nb\r\n", False), (b"a\nB\n", True), (b"\xff", True)],
)
def test_is_edited_ignores_newline_style(local: bytes, edited: bool) -> None:
    assert is_edited(local, "a\nb\n") is edited


# --- properties -------------------------------------------------------------


@PROPERTY
@given(TEXT, TEXT)
def test_one_sided_edits_apply_whole(base: str, edited: str) -> None:
    assert merge_text(base, edited, base).content == edited
    assert merge_text(base, base, edited).content == edited
    assert merge_text(base, edited, edited).content == edited


@PROPERTY
@given(TEXT, TEXT, TEXT)
def test_merge_is_symmetric(base: str, local: str, remote: str) -> None:
    forward = merge_text(base, local, remote)
    backward = merge_text(base, remote, local)

    assert forward.content == backward.content
    assert [c.base for c in forward.conflicts] == [c.base for c in backward.conflicts]


@PROPERTY
@given(TEXT, TEXT, TEXT)
def test_conflicts_quote_the_local_text(base: str, local: str, remote: str) -> None:
    lines = text_merge._split(local)
    stop = 0
    for conflict in merge_text(base, local, remote).conflicts:
        assert conflict.start >= stop
        assert tuple(lines[conflict.start : conflict.stop]) == conflict.local
        assert conflict.local != conflict.remote
        stop = conflict.stop


@PROPERTY
@given(TEXT, TEXT, TEXT)
def test_crlf_checkout_merges_like_lf(base: str, local: str, remote: str) -> None:
    result = merge_text(base, local, remote)
    crlf = merge_text(base, local.replace("\n", "\r\n"), remote)

    if "\n" in local:
        assert crlf.clean == result.clean
        if result.content is not None:
            assert crlf.content == result.content.replace("\n", "\r\n")


@st.composite
def separated_edits(draw: st.DrawFn) -> tuple[str, str, str, str]:
    """A base of blocks between unique marker lines, and edits to disjoint blocks.

    Each block draws lines from its own vocabulary, so no line can align across
    a marker and every marker is a unique anchor on all three sides.
    """
    count = draw(st.integers(1, 6))

    def block(index: int) -> list[str]:
        words = st.sampled_from([f"{index}a\n", f"{index}b\n", f"{index}c\n"])
        return draw(st.lists(words, max_size=5))

    blocks = [block(i) for i in range(count)]
    owner = [draw(st.sampled_from(["base", "local", "remote"])) for _ in range(count)]
    edits = {
        side: [block(i) if owner[i] == side else blocks[i] for i in range(count)]
        for side in ("local", "remote")
    }
    expected = [
        edits[owner[i]][i] if owner[i] != "base" else blocks[i] for i in range(count)
    ]

    def join(parts: list[list[str]]) -> str:
        return "".join(f"--- {i} ---\n" + "".join(p) for i, p in enumerate(parts))

    return join(blocks), join(edits["local"]), join(edits["remote"]), join(expected)


@PROPERTY
@given(separated_edits())
def test_edits_separated_by_an_unchanged_line_never_conflict(
    case: tuple[str, str, str, str],
) -> None:
    base, local, remote, expected = case

    assert merge_text(base, local, remote).content == expected


@PROPERTY
@given(st.lists(LINE, max_size=30), st.lists(LINE, max_size=30))
def test_alignment_pairs_equal_lines_in_order(a: list[str], b: list[str]) -> None:
    matches = text_merge._matches(a, b)

    assert all(a[i] == b[j] for i, j in matches)
    assert all(i1 < i2 and j1 < j2 for (i1, j1), (i2, j2) in pairwise(matches))


# --- resolutions --------------------------------------------------------------

LOCAL, DESIRED, BOTH = ResolutionChoice


def always(choice: ResolutionChoice) -> text_merge.HunkChooser:
    return lambda _: choice


@pytest.mark.parametrize(
    ("choice", "merged"),
    [
        (LOCAL, "A\nb\nc\nd\nE\n"),
        (DESIRED, "a2\nb\nc\nd\ne2\n"),
        (BOTH, "A\na2\nb\nc\nd\nE\ne2\n"),
    ],
)
def test_every_hunk_takes_its_chosen_side(
    choice: ResolutionChoice, merged: str
) -> None:
    base = lf_text(["a", "b", "c", "d", "e"])
    local = lf_text(["A", "b", "c", "d", "E"])
    remote = lf_text(["a2", "b", "c", "d", "e2"])

    result = merge_text(base, local, remote, always(choice))

    assert result.content == merged
    assert not result.conflicts
    assert [(c.start, c.resolution) for c in result.resolved] == [
        (0, choice),
        (4, choice),
    ]


def test_one_open_hunk_keeps_every_hunk_open() -> None:
    base = lf_text(["a", "b", "c", "d", "e"])
    local = lf_text(["A", "b", "c", "d", "E"])
    remote = lf_text(["a2", "b", "c", "d", "e2"])

    result = merge_text(
        base, local, remote, lambda hunk: LOCAL if hunk.start == 0 else None
    )

    assert result == TextMerge(None, merge_text(base, local, remote).conflicts)
    assert all(c.resolution is None for c in result.conflicts)


def test_hunk_resolutions_apply_only_all_together() -> None:
    base, local, desired = "a\nb\nc\nd\ne\n", "A\nb\nc\nd\nE\n", "a2\nb\nc\nd\ne2\n"
    (first, last) = reconcile_text(local.encode(), desired, base, FILE).conflicts

    partial = reconcile_text(
        local.encode(), desired, base, FILE, resolutions={first.id: LOCAL}
    )
    assert (partial.content, partial.baseline) == (None, base)
    assert partial.conflicts == (first, last)

    settled = reconcile_text(
        local.encode(),
        desired,
        base,
        FILE,
        resolutions={first.id: LOCAL, last.id: BOTH},
    )
    assert (settled.content, settled.baseline) == ("A\nb\nc\nd\nE\ne2\n", desired)
    assert [(c.id, c.resolution) for c in settled.resolved] == [
        (first.id, LOCAL),
        (last.id, BOTH),
    ]


@pytest.mark.parametrize(
    ("local", "baseline", "choice", "content"),
    [
        pytest.param(b"mine\n", None, LOCAL, None, id="adopt-unowned"),
        pytest.param(b"mine\n", None, DESIRED, "new\n", id="overwrite-unowned"),
        pytest.param(None, "old\n", LOCAL, None, id="keep-deleted"),
        pytest.param(None, "old\n", DESIRED, "new\n", id="recreate-deleted"),
    ],
)
def test_whole_text_resolutions_own_the_update(
    local: bytes | None,
    baseline: str | None,
    choice: ResolutionChoice,
    content: str | None,
) -> None:
    (conflict,) = reconcile_text(local, "new\n", baseline, FILE).conflicts
    assert conflict.location == FILE
    assert conflict.choices == (LOCAL, DESIRED)

    result = reconcile_text(
        local, "new\n", baseline, FILE, resolutions={conflict.id: choice}
    )

    assert (result.content, result.baseline) == (content, "new\n")
    assert not result.conflicts
    # The next update of an adopted text merges like any owned text.
    if local is not None and choice is LOCAL:
        again = reconcile_text(local, "newer\n", result.baseline, FILE)
        assert [c.reason for c in again.conflicts] == [ConflictReason.DIVERGED]


def test_whole_text_conflicts_cannot_keep_both() -> None:
    (conflict,) = reconcile_text(b"mine\n", "new\n", None, FILE).conflicts

    result = reconcile_text(
        b"mine\n", "new\n", None, FILE, resolutions={conflict.id: BOTH}
    )

    assert result.conflicts == (conflict,)


@PROPERTY
@given(TEXT, TEXT, TEXT, st.sampled_from(list(ResolutionChoice)))
def test_resolving_every_hunk_always_merges(
    base: str, local: str, remote: str, choice: ResolutionChoice
) -> None:
    conflicts = merge_text(base, local, remote).conflicts
    result = merge_text(base, local, remote, always(choice))

    assert result.clean
    assert [c.start for c in result.resolved] == [c.start for c in conflicts]


@PROPERTY
@given(TEXT, TEXT, TEXT)
def test_keeping_local_mirrors_taking_the_update(
    base: str, local: str, remote: str
) -> None:
    forward = merge_text(base, local, remote, always(LOCAL))
    backward = merge_text(base, remote, local, always(DESIRED))

    assert forward.content == backward.content
