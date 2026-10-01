"""Terminal SVG rendering, ANSI styling, and column width measurement helpers."""

from __future__ import annotations

import io
import re
from html import escape

from rich.cells import cell_len
from rich.console import Console
from rich.segment import Segment
from rich.text import Text

from protostar.cli.palette import ANSI
from protostar.fs import atomic_write_text
from scripts.generate_docs_assets.common import DOCS_TERMINALS_DIR


def _calculate_content_width(console: Console, min_width: int = 1) -> int:
    """Calculates the maximum visible column width across all lines in the console buffer."""
    segments = list(Segment.filter_control(console._record_buffer))
    lines = list(Segment.split_and_crop_lines(segments, length=10000, pad=False))
    max_col = 0
    for line in lines:
        current_col = 0
        line_max_col = 0
        for seg in line:
            text = seg.text
            if text == "\n":
                continue
            style = seg.style
            has_bg = False
            if style is not None:
                has_bg = bool(
                    style.reverse
                    or (style.bgcolor is not None and not style.bgcolor.is_default)
                )

            if has_bg:
                current_col += cell_len(text)
                line_max_col = current_col
            else:
                rstripped = text.rstrip()
                # A heading's rule fills whatever width it is given; the export
                # crops it to the widest content instead.
                if rstripped and set(rstripped) != {"─"}:
                    line_max_col = current_col + cell_len(rstripped)
                current_col += cell_len(text)
        if line_max_col > max_col:
            max_col = line_max_col

    return max(max_col, min_width)


_RICH_CHROME = re.compile(
    r'<rect fill="#[0-9a-f]{6}" stroke="rgba\(255,255,255,0\.35\)".*?</g>', re.DOTALL
)
_VIEWBOX = re.compile(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"')

# Rich draws the first terminal row 41 units down; the title bar ends above it.
_BAR_HEIGHT = 32

# house-style's terminal window (docs/house/css/terminal.css), which frames the
# docs' recordings too, so screenshots and recordings read as one terminal.
_WINDOW = "#090e11"
_WINDOW_BORDER = "#2d3c43"
_BAR = "#11171c"
_BAR_RULE = "#243138"
_TITLE = "#7a909c"
_DOTS = (("#ff5f56", "#e0443e"), ("#ffbd2e", "#dea123"), ("#27c93f", "#1aab29"))


def _window_chrome(width: float, height: float, title: str) -> str:
    """Draws house-style's terminal window around a Rich export."""
    radius = 8
    inner = width - 1
    bar = (
        f"M0.5 {_BAR_HEIGHT}V{radius + 0.5}a{radius} {radius} 0 0 1 {radius} -{radius}"
        f"H{inner - radius:g}a{radius} {radius} 0 0 1 {radius} {radius}V{_BAR_HEIGHT}Z"
    )
    dots = "".join(
        f'<circle cx="{20 + 18 * index}" cy="16.5" r="5.5" fill="{fill}" stroke="{stroke}"/>'
        for index, (fill, stroke) in enumerate(_DOTS)
    )
    return (
        f'<rect fill="{_WINDOW}" x="0.5" y="0.5" width="{inner:g}" height="{height - 1:g}" '
        f'rx="{radius}"/>'
        f'<path fill="{_BAR}" d="{bar}"/>'
        f'<path stroke="{_BAR_RULE}" d="M0.5 {_BAR_HEIGHT}.5H{inner:g}"/>'
        f"{dots}"
        f'<text fill="{_TITLE}" x="{width / 2:g}" y="21" text-anchor="middle" '
        f'font-family="JetBrains Mono, Fira Code, monospace" font-size="11" '
        f'letter-spacing="0.6">{escape(title)}</text>'
        f'<rect fill="none" stroke="{_WINDOW_BORDER}" x="0.5" y="0.5" width="{inner:g}" '
        f'height="{height - 1:g}" rx="{radius}"/>'
    )


def frame_terminal_svg(svg: str, title: str) -> str:
    """Replaces Rich's window chrome with house-style's terminal window.

    Args:
        svg: An SVG exported by Rich, directly or through Textual.
        title: The text centred in the title bar.

    Returns:
        The SVG with Protostar's chrome and trailing whitespace stripped.
    """
    viewbox = _VIEWBOX.search(svg)
    if viewbox is None or _RICH_CHROME.search(svg) is None:
        raise SystemExit("Rich's SVG export changed shape; update frame_terminal_svg")
    chrome = _window_chrome(float(viewbox[1]), float(viewbox[2]), title)
    framed = _RICH_CHROME.sub(lambda _: chrome, svg, count=1)
    return "\n".join(line.rstrip() for line in framed.splitlines()) + "\n"


def _render_and_write_svg(
    console: Console,
    title: str,
    filename: str,
    unique_id: str | None = None,
) -> None:
    """Shrinkwraps recorded console output and writes a clean deterministic SVG to DOCS_TERMINALS_DIR."""
    content_width = _calculate_content_width(console)
    if content_width > 0:
        console.width = content_width

    svg_content = console.export_svg(
        title=title,
        theme=ANSI,
        unique_id=unique_id or filename.replace(".svg", ""),
    )

    clean_svg = frame_terminal_svg(svg_content, title)
    output_path = DOCS_TERMINALS_DIR / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, clean_svg)


def _recording_console(*, terminal: bool = True) -> Console:
    """Builds a byte-stable recording console for terminal SVG capture."""
    return Console(
        record=True,
        width=100,
        force_terminal=terminal,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
        _environ={},
    )


def _print_prompt(console: Console, arguments: str) -> None:
    """Prints a shell prompt invoking protostar with the given arguments."""
    console.print(
        Text.assemble(
            ("❯ ", "bright_black"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{arguments}\n", "white"),
        )
    )
