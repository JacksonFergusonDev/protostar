"""CLI presentation and confirmation for project ejection."""

import argparse
import difflib
from pathlib import Path

from rich.prompt import Confirm
from rich.text import Text

from protostar.cli import schema, ui
from protostar.cli.diff import format_diff
from protostar.eject import PreparedEjection, prepare_ejection
from protostar.errors import ExecutionAbortedError, InvalidUsageError
from protostar.system import is_interactive


def _diff(prepared: PreparedEjection) -> str:
    """Returns the exact pyproject edit as a unified diff."""
    if prepared.pyproject_after is None:
        return ""
    before = (prepared.pyproject.original.file_content or b"").decode("utf-8")
    after = prepared.pyproject_after.decode("utf-8")
    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="a/pyproject.toml",
        tofile="b/pyproject.toml",
    )
    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in lines
    )


def handle_eject(args: argparse.Namespace) -> None:
    """Shows the prepared changes and ejects only after explicit confirmation."""
    prepared = prepare_ejection(Path.cwd())
    paths = prepared.changed_paths
    if getattr(args, "dry_run", False):
        if ui.is_json_mode:
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "planned",
                    "changed_paths": list(paths),
                    "pyproject_diff": _diff(prepared),
                }
            )
            return
        if not paths:
            ui.console.print(Text("Nothing to eject."))
            return
        _print_summary(prepared)
        if diff := _diff(prepared):
            ui.console.print(format_diff(diff), end="")
        return

    if not paths:
        if ui.is_json_mode:
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "success",
                    "changed_paths": [],
                }
            )
        else:
            ui.console.print(Text("Nothing to eject."))
        return

    if not getattr(args, "yes", False):
        if ui.is_json_mode or not is_interactive():
            raise InvalidUsageError(
                "Ejection requires confirmation.",
                hint="Pass --yes to confirm, or --dry-run to preview the changes.",
            )
        _print_summary(prepared)
        try:
            confirmed = Confirm.ask(
                "Proceed with ejection?", default=False, console=ui.console
            )
        except (KeyboardInterrupt, EOFError) as error:
            raise ExecutionAbortedError("Ejection cancelled.") from error
        if not confirmed:
            ui.console.print(Text("Ejection cancelled."))
            return
    elif not ui.is_json_mode:
        _print_summary(prepared)

    prepared.apply()
    if ui.is_json_mode:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "changed_paths": list(paths),
            }
        )
    else:
        ui.console.print(Text("Protostar tracking removed from this project."))


def _print_summary(prepared: PreparedEjection) -> None:
    """Shows exactly which files the pending ejection changes."""
    ui.console.print(Text("Eject Protostar from this project?", style="bold"))
    if prepared.lock.path in prepared.changed_paths:
        ui.console.print(Text("  Delete protostar.lock"))
    if prepared.pyproject.path in prepared.changed_paths:
        ui.console.print(Text("  Remove [tool.protostar] from pyproject.toml"))
    ui.console.print(Text("Other project files, including uv.lock, will remain."))
    ui.console.print(
        Text("Protostar status, diff, and sync will no longer work for this project.")
    )
