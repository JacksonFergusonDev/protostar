"""Pygments adapter and token palette, loaded only when a code pane renders."""

from pathlib import PurePath
from typing import TYPE_CHECKING

from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.token import Token
from pygments.util import ClassNotFound
from rich.style import Style
from rich.text import Text

from protostar.cli.diff import normalize_newlines
from protostar.cli.palette import CYAN, FAINT, SOFT, TEXT

if TYPE_CHECKING:
    from .code import CodeSource

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


def highlight(source: "CodeSource") -> Text:
    """Apply token styles to literal source without lexer preprocessing."""
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
