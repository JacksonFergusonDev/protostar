"""Literal source and diff presentation shared by all TUI code surfaces."""

import difflib
import re
from dataclasses import dataclass
from pathlib import PurePath

from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.token import Token
from pygments.util import ClassNotFound
from rich.style import Style
from rich.text import Text

from protostar.cli.diff import normalize_newlines
from protostar.cli.palette import CYAN, DECK, FAINT, GREEN, RED, SOFT, TEXT
from protostar.preparation import PreparedEdit

# Outcome colors belong to the diff, never to language tokens. Transparent
# token backgrounds inherit the panel, or a changed line's subtle wash.
_TOKEN_STYLES = {
    Token: Style(color=TEXT),
    Token.Comment: Style(color=FAINT, italic=True),
    Token.Keyword: Style(color=CYAN),
    Token.Name: Style(color=CYAN),
    Token.Name.Function: Style(color=TEXT),
    Token.Name.Class: Style(color=TEXT),
    Token.Name.Tag: Style(color=CYAN),
    Token.Name.Attribute: Style(color=CYAN),
    Token.Literal.String: Style(color=SOFT),
    Token.Literal.Number: Style(color=SOFT, bold=True),
    Token.Operator: Style(color=SOFT),
    Token.Punctuation: Style(color=FAINT),
}


# Blend outcome colors with the existing panel color; no independent palette.
def _wash(color: str) -> str:
    return "#" + "".join(
        f"{round(int(DECK[i : i + 2], 16) * 0.9 + int(color[i : i + 2], 16) * 0.1):02x}"
        for i in (1, 3, 5)
    )


_ADDED = Style(bgcolor=_wash(GREEN))
_REMOVED = Style(bgcolor=_wash(RED))
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class CodeSource:
    """Display content, its filename, and an optional Pygments lexer alias.

    Language aliases are an open vocabulary supplied by Pygments. An explicit
    alias describes the displayed serialization, even when the path disagrees.
    """

    text: str
    path: str
    language: str | None = None


@dataclass(frozen=True)
class DiffLabels:
    """The two literal filenames or side names shown above a diff."""

    before: str
    after: str


def source_text(source: CodeSource) -> Text:
    """Highlight literal source without parsing markup or reading files.

    CRLF and CR become LF for display; other whitespace remains intact.
    Unknown filenames and lexer aliases remain plain text. Only unsupported
    lexer lookup is caught; programming errors must remain visible.
    """
    result = Text(normalize_newlines(source.text), style=TEXT)
    try:
        name = PurePath(source.path).name.lower()
        language = source.language
        if language is None:
            if name.endswith(".jsonc"):
                language = "json"
            elif name in (".envrc", ".bashrc", ".zshrc", ".profile"):
                language = "bash"
        lexer = (
            get_lexer_by_name(language)
            if language is not None
            else get_lexer_for_filename(source.path)
        )
    except ClassNotFound:
        return result
    # get_tokens() normalizes newlines and may add a final newline. Apply raw
    # offsets to the original Text instead, preserving every displayed character.
    for start, token, value in lexer.get_tokens_unprocessed(result.plain):
        while token not in _TOKEN_STYLES and token.parent is not None:
            token = token.parent
        result.stylize(_TOKEN_STYLES[token], start, start + len(value))
    return result


def _source_lines(source: CodeSource) -> list[Text]:
    styled = source_text(source)
    offsets = []
    end = 0
    for line in source.text.splitlines(keepends=True):
        end += len(line)
        offsets.append(end)
    lines = list(styled.divide(offsets))[: len(offsets)]
    for styled_line in lines:
        if styled_line.plain.endswith("\n"):
            styled_line.right_crop(1)
    return lines


def diff_text(
    before: CodeSource | None,
    after: CodeSource,
    *,
    labels: DiffLabels | None = None,
) -> Text:
    """Render a unified diff using syntax from each complete source document.

    Change markers and background washes carry the diff semantics; foregrounds
    retain syntax colors. Normalize line endings like the plain CLI diff.
    """
    old = normalize_newlines(before.text) if before is not None else ""
    new = normalize_newlines(after.text)
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    old_styled = (
        _source_lines(CodeSource(old, before.path, before.language)) if before else []
    )
    new_styled = _source_lines(CodeSource(new, after.path, after.language))
    names = labels or DiffLabels(
        f"a/{before.path}" if before else "/dev/null", f"b/{after.path}"
    )
    result = Text(style=TEXT)
    old_index = new_index = 0
    for index, line in enumerate(
        difflib.unified_diff(old_lines, new_lines, names.before, names.after)
    ):
        if index < 2:
            result.append(line, Style(color=SOFT, bold=True))
            continue
        if match := _HUNK.match(line):
            old_index, new_index = (int(value) - 1 for value in match.groups())
            result.append(line, CYAN)
            continue
        marker = line[0]
        if marker == "-":
            content = old_styled[old_index].copy()
            old_index += 1
            background, foreground = _REMOVED, RED
        else:
            content = new_styled[new_index].copy()
            new_index += 1
            if marker == " ":
                old_index += 1
            background = _ADDED if marker == "+" else Style()
            foreground = GREEN if marker == "+" else TEXT
        content.stylize(background)
        result.append(marker, background + Style(color=foreground))
        result.append_text(content)
        result.append("\n")
        if not line.endswith("\n"):
            result.append("\\ No newline at end of file\n", FAINT)
    return result


def edit_text(edit: PreparedEdit) -> Text:
    """Render an accepted edit with the same policy as conflict diffs."""
    return diff_text(
        CodeSource(edit.before.decode(), edit.path)
        if edit.before is not None
        else None,
        CodeSource(edit.after.decode(), edit.path),
    )
