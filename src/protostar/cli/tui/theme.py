"""The TUI's colors: its only theme, and the styles its code writes inline.

The stylesheet colors widgets through the theme's variables (``$accent``,
``$text-faint``). Text a widget renders styles its spans with the constants
below, each named for the variable it equals, so a role reads the same in
both. They are palette values because Rich Text and Textual Content read a
color value alike, while Content reads an ANSI name such as ``cyan`` as the
CSS color, off the palette.

Printed output's renderers, which the TUI shows too, style with ANSI names
and ``dim``. ``PaletteColors`` lands both on the same colors.

There is no light mode.
"""

from functools import lru_cache

from rich.color import Color as RichColor
from rich.segment import Segment
from rich.style import Style
from textual.color import Color
from textual.filter import ANSIToTruecolor, dim_color
from textual.theme import Theme

from protostar.cli.palette import (
    AMBER,
    ANSI,
    CONSOLE,
    CYAN,
    DECK,
    DIM,
    FAINT,
    GLOW,
    GREEN,
    HAIRLINE,
    INK,
    RED,
    SOFT,
    STRUT,
    TEXT,
)

FOREGROUND = TEXT
"""``$foreground``: text that is lit, such as the shown tab."""
TEXT_FAINT = FAINT
"""``$text-faint``: notes, hints, and what happens unless chosen otherwise."""
ACCENT = CYAN
"""``$accent``: commands and paths in prose, and the side the user keeps."""
TITLE = f"bold {ACCENT}"
"""A heading's title, and each key in a legend, as the footer shows keys."""
SUCCESS = GREEN
"""``$success``: what an update adds."""
WARNING = AMBER
"""``$warning``: what waits on something else."""
ERROR = RED
"""``$error``: what stays open or failed."""
RULE = HAIRLINE
"""``$hairline``: rules and separators drawn in text."""
KEY = "dim not bold"
"""The key after a control's label: its label's color, faded into its background.

A key sits on plain, focused, and colored buttons alike, so it fades
relative to each rather than taking one color.
"""

PROTOSTAR = Theme(
    name="protostar",
    primary=ACCENT,
    secondary=ACCENT,
    accent=ACCENT,
    warning=WARNING,
    error=ERROR,
    success=SUCCESS,
    foreground=FOREGROUND,
    background=INK,
    surface=DECK,
    panel=CONSOLE,
    dark=True,
    variables={
        "hairline": RULE,
        "strut": STRUT,
        "glow": GLOW,
        # Textual derives these from contrast or tints, off the palette.
        "text": FOREGROUND,
        "text-muted": SOFT,
        "text-faint": TEXT_FAINT,
        "text-disabled": DIM,
        "text-primary": ACCENT,
        "text-secondary": ACCENT,
        "text-accent": ACCENT,
        "text-success": SUCCESS,
        "text-warning": WARNING,
        "text-error": ERROR,
        "foreground-muted": SOFT,
        "foreground-disabled": DIM,
        "border": ACCENT,
        "border-blurred": RULE,
        "block-cursor-background": GLOW,
        "block-cursor-foreground": ACCENT,
        "block-cursor-text-style": "bold",
        "block-cursor-blurred-background": CONSOLE,
        "block-cursor-blurred-foreground": FOREGROUND,
        "block-cursor-blurred-text-style": "none",
        "block-hover-background": CONSOLE,
        "input-cursor-background": ACCENT,
        "input-cursor-foreground": INK,
        "input-selection-background": f"{ACCENT} 25%",
        "scrollbar": STRUT,
        "scrollbar-hover": FAINT,
        "scrollbar-active": ACCENT,
        "scrollbar-background": DECK,
        "scrollbar-background-hover": DECK,
        "scrollbar-background-active": DECK,
        "scrollbar-corner-color": DECK,
        "footer-background": CONSOLE,
        "footer-foreground": SOFT,
        "footer-key-foreground": ACCENT,
        "footer-key-background": CONSOLE,
        "footer-description-foreground": SOFT,
        "footer-description-background": CONSOLE,
        "footer-item-background": CONSOLE,
        "button-foreground": FOREGROUND,
        "button-color-foreground": INK,
        "button-focus-text-style": "bold",
    },
)
"""The app's only theme."""

_PLAIN = frozenset(RichColor.parse(color).triplet for color in (TEXT, SOFT))
_FAINT = Style(color=TEXT_FAINT)
_UNDIM = Style(dim=False)


class PaletteColors(ANSIToTruecolor):
    """Lands ANSI names and ``dim`` on the palette.

    Textual dims a color by blending it toward the background, which lands
    between palette colors. Here dim plain text is ``$text-faint`` instead,
    and dim colored text, such as a key on a primary button, fades halfway
    into its background, as the palette's own steps do.
    """

    def __init__(self) -> None:
        super().__init__(ANSI)

    def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
        """Converts a line's colors to truecolor, drawing its dim in the palette.

        Args:
            segments: The line's segments.
            background: The widget's background.

        Returns:
            The segments in truecolor, none of them dim.
        """
        under = background.rich_color
        undimmed = [
            Segment(text, _undim(self.truecolor_style(style + _UNDIM, under), under))
            if style is not None and style.dim
            else Segment(text, style)
            for text, style, _ in segments
        ]
        return super().apply(undimmed, background)


@lru_cache(1024)
def _undim(style: Style, background: RichColor) -> Style:
    color = style.color
    if color is None or color.triplet in _PLAIN:
        return style + _FAINT
    faded = dim_color(style.bgcolor or background, color, 0.5)
    return style + Style(color=faded)
