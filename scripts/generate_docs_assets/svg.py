"""Terminal SVG rendering, ANSI styling, and column width measurement helpers."""

from __future__ import annotations

import io

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

    clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
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
