"""Protostar's colors, the TUI's take on house-style's dark palette.

house-style (vendored in ``docs/house/``) is the look jacksonferguson.me and
its project sites share, so the CLI, the TUI, and the docs read as one
product. The cyan accent and the terminal window's panel colors are the
same values. Cyan is the only accent; green, amber, and red only report an
outcome.

Printed output names ANSI colors (``cyan``, ``bright_black``) rather than
these values, because it lands on the user's own terminal background, which
may be light. ``ANSI`` maps those names onto the palette wherever Protostar
draws its own background: the TUI and the docs' terminal screenshots.
"""

from rich.color import Color
from rich.terminal_theme import TerminalTheme

INK = "#0a0a0a"
"""The background the TUI and the docs' terminal screenshots paint."""
DECK = "#0d1318"
"""Panels."""
CONSOLE = "#151d24"
"""Raised controls: the masthead, fields, and buttons (the active install tab)."""
HAIRLINE = "#243138"
"""Panel rules (house-style's rule under the terminal window's title bar)."""
STRUT = "#2d3c43"
"""Unlit indicators and scrollbars (house-style's terminal window border)."""
CYAN = "#22d3ee"
"""The accent (house-style's ``--accent``): focus, keys, and the primary action."""
GLOW = "#0e2e33"
"""Cyan washed into the background, behind the focused row."""
TEXT = "#e2e8f0"
SOFT = "#a9b7d0"
"""Secondary text."""
FAINT = "#7a909c"
"""Tertiary text (house-style's terminal window title)."""
DIM = "#4b5b64"
"""Disabled text and tree guides, halfway from FAINT to the panels."""
GREEN = "#a6e3a1"
"""Success, and the prompt green of the docs' recordings."""
AMBER = "#fbbf24"
RED = "#f87171"
BLUE = "#61afef"
"""Directories, in the blue of the docs' recordings."""

MARK = "❊"
"""The glyph nearest Protostar's mark: thin spokes around an open centre."""


def _rgb(hex_color: str) -> tuple[int, int, int]:
    triplet = Color.parse(hex_color).get_truecolor()
    return triplet.red, triplet.green, triplet.blue


# black, red, green, yellow, blue, magenta, cyan, white
_NORMAL = (STRUT, RED, GREEN, AMBER, BLUE, SOFT, CYAN, TEXT)
_BRIGHT = (DIM, RED, GREEN, AMBER, BLUE, SOFT, CYAN, TEXT)

ANSI = TerminalTheme(
    background=_rgb(INK),
    foreground=_rgb(TEXT),
    normal=[_rgb(color) for color in _NORMAL],
    bright=[_rgb(color) for color in _BRIGHT],
)
"""The ANSI colors in Protostar's palette, for surfaces it paints itself."""
