"""Every color the TUI draws comes from the palette, through the theme."""

import ast
import re
from pathlib import Path

import pytest
from rich.color import Color as RichColor
from rich.segment import Segment
from rich.style import Style
from textual.color import Color

from protostar.cli.palette import CONSOLE, CYAN, DECK, FAINT, INK, SOFT, TEXT
from protostar.cli.tui import theme
from protostar.cli.tui.theme import PaletteColors

TUI = Path(theme.__file__).parent

# Rich's ANSI color names, which Textual Content reads as CSS colors instead.
_ANSI = {
    f"{bright}{name}"
    for bright in ("", "bright_")
    for name in ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
}
_ATTRIBUTES = {"bold", "not", "italic", "underline", "reverse", "strike", "dim"}
_VARIABLE = re.compile(r"\$[a-z][a-z-]*")
"""A theme variable, such as ``$accent``; prose's ``$EDITOR`` is not one."""


def _drawn(style: Style, background: str = DECK) -> RichColor | None:
    (segment,) = PaletteColors().apply([Segment("x", style)], Color.parse(background))
    assert segment.style is not None
    assert not segment.style.dim
    return segment.style.color


def _hex(color: RichColor | None) -> str:
    assert color is not None
    return color.get_truecolor().hex


@pytest.mark.parametrize("color", [TEXT, SOFT, None])
@pytest.mark.parametrize("background", [INK, DECK, CONSOLE])
def test_dim_plain_text_is_the_faint_text_color(color, background):
    assert _hex(_drawn(Style(color=color, dim=True), background)) == FAINT


def test_dim_colored_text_fades_halfway_into_its_background():
    # A key on a primary button: the label's ink, halfway to the button's cyan.
    drawn = _hex(_drawn(Style(color=INK, bgcolor=CYAN, dim=True)))
    expected = Color.parse(INK).blend(Color.parse(CYAN), 0.5)
    assert Color.parse(drawn) == expected.clamped


def test_ansi_names_land_on_the_palette():
    assert _hex(_drawn(Style(color="cyan"))) == CYAN
    assert _hex(_drawn(Style(color="cyan", dim=True))) != CYAN


def _style_literals(path: Path) -> list[str]:
    """Returns string constants in a module that read as a style naming a color."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        words = set(node.value.split())
        if any(_VARIABLE.fullmatch(word) for word in words) or (
            words and words <= _ANSI | _ATTRIBUTES and words & (_ANSI | {"dim"})
        ):
            found.append(node.value)
    return found


@pytest.mark.parametrize(
    "path",
    [path for path in sorted(TUI.rglob("*.py")) if path.name != "theme.py"],
    ids=lambda path: path.relative_to(TUI).as_posix(),
)
def test_tui_code_styles_text_only_through_the_theme(path):
    # Content reads "cyan" as #00ffff, and "dim" or a "$variable" bypasses the
    # role the theme names. Printed output's renderers keep ANSI names.
    assert _style_literals(path) == []
