"""Shared constants and filesystem helpers for documentation asset generation."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

from protostar.fs import atomic_write_text
from scripts._common import (
    DOCS_GENERATED_DIR,
    DOCS_TERMINALS_DIR,
    REPO_ROOT,
    SNAPSHOTS_DIR,
)

__all__ = ["DOCS_GENERATED_DIR", "DOCS_TERMINALS_DIR", "REPO_ROOT", "SNAPSHOTS_DIR"]


def _write_generated_doc(filepath: str | Path, content: str) -> None:
    """Writes raw unformatted content to a generated documentation file.

    Args:
        filepath: Target filename or Path relative to DOCS_GENERATED_DIR or absolute.
        content: Raw string data to write to disk.
    """
    output_path = (
        DOCS_GENERATED_DIR / filepath if isinstance(filepath, str) else filepath
    )
    content = content.rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, content)


def _format_markdown_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> str:
    """Constructs a Markdown-formatted table from headers and row values."""
    header_row = f"| {' | '.join(headers)} |"
    separator_row = f"| {' | '.join([':---'] * len(headers))} |"
    table = [header_row, separator_row]
    for row in rows:
        table.append(f"| {' | '.join(row)} |")
    return "\n".join(table)


@contextlib.contextmanager
def demo_project() -> Iterator[None]:
    """Runs the body inside a fresh, fixed-name project directory.

    Paths render with the directory's name, so it is fixed for byte-stable output;
    the regression snapshots use the same name.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_cwd = os.getcwd()
        project_dir = Path(tmpdir) / "demo_project"
        project_dir.mkdir()
        os.chdir(project_dir)
        try:
            yield
        finally:
            os.chdir(orig_cwd)


def stub_which(name: str) -> str | None:
    """Reports every required binary present and no IDE CLI to probe."""
    return None if name in ("code", "cursor") else f"/usr/bin/{name}"


@contextlib.contextmanager
def stable_host(
    which: Callable[[str], str | None] = stub_which,
) -> Iterator[None]:
    """Makes a run read the same on every machine.

    The hook registry is offline (fallback pins), Git reports no identity, and
    the binaries ``which`` names are the ones installed.
    """
    with (
        mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
        mock.patch("protostar.metadata.get_git_config", return_value=None),
        mock.patch("shutil.which", which),
    ):
        yield


def cli_json(*args: str, allow_error: bool = False) -> dict[str, Any]:
    """Runs ``protostar <args> --json --no-config`` in-process and returns its payload.

    Run inside ``demo_project()`` and ``stable_host()``: the command is the
    one a reader types, so a fixture can't drift from what it prints.

    Args:
        *args: The command line after ``protostar``.
        allow_error: Whether an error payload is the fixture, not a failure.
    """
    import protostar.cli.ui as ui
    from protostar.cli.main import main

    output = io.StringIO()
    json_mode = ui.is_json_mode
    try:
        with (
            mock.patch.object(
                sys, "argv", ["protostar", *args, "--json", "--no-config"]
            ),
            contextlib.redirect_stdout(output),
            contextlib.suppress(SystemExit),
        ):
            main()
    finally:
        ui.is_json_mode = json_mode
    payload: dict[str, Any] = json.loads(output.getvalue())
    if payload.get("status") == "error" and not allow_error:
        raise SystemExit(f"`protostar {' '.join(args)}` failed: {payload['error']}")
    return payload


def run_cli(*args: str, failing: bool = False) -> None:
    """Runs ``protostar <args> --no-config`` in-process, as a headless terminal would.

    Output goes wherever ``protostar.cli.ui.console`` points. Standard input is
    not a terminal, so no screen opens.

    Args:
        *args: The command line after ``protostar``.
        failing: Whether the command is expected to fail; otherwise a failure
            stops generation instead of being recorded.
    """
    from protostar.cli.main import main

    code: object = 0
    with (
        mock.patch.object(sys, "argv", ["protostar", *args, "--no-config"]),
        mock.patch.object(sys, "stdin", io.StringIO()),
    ):
        try:
            main()
        except SystemExit as exit_:
            code = exit_.code
    if bool(code) != failing:
        raise SystemExit(f"`protostar {' '.join(args)}` exited {code}")
