from itertools import pairwise

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from protostar import text_merge
from protostar.text_merge import TextConflict, TextMerge, merge_text

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
