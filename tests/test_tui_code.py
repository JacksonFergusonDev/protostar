"""All TUI source surfaces share literal, palette-based highlighting."""

import io

import pytest
from rich.console import Console
from rich.style import Style

from protostar.cli.diff import normalize_newlines
from protostar.cli.palette import CYAN, FAINT, GREEN, RED, SOFT
from protostar.cli.reviews import unified_diff
from protostar.cli.tui.code import CodeSource, diff_text, edit_text, source_text
from protostar.cli.tui.conflicts.sides import side_text, sides_diff
from protostar.merge import ConflictReason, ConflictSides, MergeConflict, MergeLocation
from protostar.preparation import PreparedEdit


def color_at(text, needle):
    return text.get_style_at_offset(Console(), text.plain.index(needle)).color


@pytest.mark.parametrize(
    ("path", "source", "key"),
    [
        ("pyproject.toml", '[tool]\nname = "café [bold]"\n', "name"),
        ("config.yaml", 'name: "value"\n', "name"),
        ("settings.jsonc", '{ // comment\n"name": true\n}', '"name"'),
        ("main.py", 'def run():\n\treturn "value"', "def"),
        (".envrc", 'if true; then\n echo "value"\nfi', "if"),
    ],
)
def test_supported_languages_preserve_literal_source(path, source, key):
    rendered = source_text(CodeSource(source, path))
    assert rendered.plain == source
    assert color_at(rendered, key) == Style(color=CYAN).color


@pytest.mark.parametrize("source", ["", "\n\n", "\tfoo  \r\nbar\r", "田中 = '[red]'\n"])
def test_highlighting_never_preprocesses_whitespace(source):
    assert source_text(CodeSource(source, "file.py")).plain == normalize_newlines(
        source
    )


def test_explicit_language_overrides_filename_and_unknowns_are_plain():
    content = '{"name": 12}'
    rendered = source_text(CodeSource(content, "file.toml", "json"))
    assert color_at(rendered, '"name"') == Style(color=CYAN).color
    for source in (
        CodeSource(content, "unknown.zzzz"),
        CodeSource(content, "file.py", "not-a-lexer"),
    ):
        rendered = source_text(source)
        assert rendered.plain == content
        assert not rendered.spans


def test_lexer_programming_errors_are_not_hidden(mocker):
    mocker.patch(
        "protostar.cli.tui.code.get_lexer_for_filename",
        side_effect=AssertionError("bug"),
    )
    with pytest.raises(AssertionError, match="bug"):
        source_text(CodeSource("value", "file.py"))


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (None, b"name = 1\n"),
        (b"", b"name = 1"),
        (b"old", b"new"),
        (b"old\n", b""),
        (b"same\n", b"same\n"),
        (b"a\r\nb\r", b"a\nbb\n"),
        (b"a\n\n", b"a\n"),
        (b"--- old\n", b"+++ new\n"),
        (
            b"old\n" + b"context\n" * 12 + b"end\n",
            b"new\n" + b"context\n" * 12 + b"last\n",
        ),
    ],
)
def test_styled_diff_agrees_with_plain_diff(before, after):
    edit = PreparedEdit("file.toml", before, after)
    assert edit_text(edit).plain == unified_diff(edit)


def test_diff_preserves_multiline_syntax_outside_the_hunk():
    before = 'value = """\n' + "context\n" * 8 + "old\n" + "context\n" * 8 + '"""\n'
    after = before.replace("old\n", "new\n")
    rendered = diff_text(
        CodeSource(before, "file.toml"), CodeSource(after, "file.toml")
    )
    assert "value = " not in rendered.plain
    assert color_at(rendered, "old") == Style(color=SOFT).color
    assert color_at(rendered, "new") == Style(color=SOFT).color
    assert color_at(rendered, "-old") == Style(color=RED).color
    assert color_at(rendered, "+new") == Style(color=GREEN).color
    old_style = rendered.get_style_at_offset(Console(), rendered.plain.index("old"))
    new_style = rendered.get_style_at_offset(Console(), rendered.plain.index("new"))
    assert old_style.bgcolor is not None
    assert new_style.bgcolor != old_style.bgcolor


def test_comments_remain_readable_in_diffs():
    rendered = edit_text(PreparedEdit("file.py", b"# old\n", b"# new\n"))
    assert color_at(rendered, "# new") == Style(color=FAINT).color


def test_json_fallback_uses_its_display_language(mocker):
    conflict = MergeConflict(
        MergeLocation("file.toml", ("name",)),
        ConflictReason.TYPE_MISMATCH,
        ConflictSides(1, 2, 3),
    )
    mocker.patch(
        "protostar.cli.tui.conflicts.sides.tomlkit.dumps", side_effect=TypeError
    )
    rendered = side_text(conflict, "local")
    assert rendered.plain == '{\n  "name": 2\n}'
    assert color_at(rendered, '"name"') == Style(color=CYAN).color
    assert color_at(sides_diff(conflict), '"name"') == Style(color=CYAN).color


def test_renderer_adds_only_cp1252_encodable_decoration():
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    Console(file=stream, force_terminal=True, color_system="truecolor").print(
        edit_text(PreparedEdit("file.toml", b"name = 1", b"name = 2"))
    )
    stream.flush()
    assert b"No newline at end of file" in stream.buffer.getvalue()
