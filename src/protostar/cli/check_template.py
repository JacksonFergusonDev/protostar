"""CLI presentation for checking a template before it is published."""

import argparse
import os
import sys
from enum import StrEnum
from pathlib import Path

from rich.text import Text

from protostar.cli import schema, ui
from protostar.errors import InvalidUsageError, ProtostarError
from protostar.template_check import Finding, Severity, TemplateCheck, check_template


class OutputFormat(StrEnum):
    """How findings are written for a human or a CI system."""

    TEXT = "text"
    GITHUB = "github"


def handle_check_template(args: argparse.Namespace) -> None:
    """Checks a template and exits 1 when it fails.

    A template that cannot be retrieved raises its usual error instead, so the
    exit code and output always say whether the template was checked at all.
    """
    source: str = args.source
    strict: bool = args.strict
    output_format: OutputFormat = args.output_format
    if ui.is_json_mode and output_format is OutputFormat.GITHUB:
        raise InvalidUsageError(
            "--output-format github cannot be combined with --json.",
            hint="Use --json for a machine-readable payload, or "
            "--output-format github for workflow annotations.",
        )
    try:
        check = check_template(source)
    except ProtostarError as error:
        if output_format is OutputFormat.GITHUB:
            message = f"Could not retrieve {source}, so nothing was checked.\n{error}"
            if error.hint:
                message += f"\nHint: {error.hint}"
            ui.console.out(
                _annotation(Severity.ERROR, message, title="Template not retrieved"),
                highlight=False,
            )
        elif not ui.is_json_mode:
            ui.console.print(
                Text(f"Could not retrieve {source}, so nothing was checked.")
            )
        raise

    passed = check.passed(strict=strict)
    if ui.is_json_mode:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "passed" if passed else "failed",
                "strict": strict,
                "check": check.to_dict(),
            }
        )
    elif output_format is OutputFormat.GITHUB:
        for finding in check.findings:
            ui.console.out(_finding_annotation(finding, source), highlight=False)
        _print_verdict(check, passed=passed)
    else:
        _print_check(check, passed=passed)
    if not passed:
        sys.exit(1)


def _print_check(check: TemplateCheck, *, passed: bool) -> None:
    """Prints each finding, then a one-line verdict."""
    for title, findings, style in (
        ("Errors", check.errors, "bold red"),
        ("Warnings", check.warnings, "bold yellow"),
    ):
        if not findings:
            continue
        ui.console.print()
        ui.console.print(ui.heading(title, style))
        for index, finding in enumerate(findings):
            if index:
                ui.console.print()
            ui.console.print(ui.indented(_finding(finding)))
    _print_verdict(check, passed=passed)


def _print_verdict(check: TemplateCheck, *, passed: bool) -> None:
    """Prints the one-line summary of a check."""
    counts = ", ".join(
        f"{count} {noun}{'' if count == 1 else 's'}"
        for count, noun in (
            (len(check.errors), "error"),
            (len(check.warnings), "warning"),
        )
        if count
    )
    ui.console.print()
    if passed:
        verdict = f"{ui.glyph('✓', '+')} Template check passed"
        ui.console.print(
            Text(f"{verdict} with {counts}." if counts else f"{verdict}.", "green")
        )
    else:
        ui.console.print(
            Text(f"{ui.glyph('✗', 'x')} Template check failed: {counts}.", "bold red")
        )


def _finding(finding: Finding) -> Text:
    """Renders one finding; its text comes from the template, so it is data."""
    location = finding.file
    if finding.line is not None:
        location += f":{finding.line}"
    if finding.key:
        location += f" {ui.glyph('→', '->')} {finding.key}"
    style = "red" if finding.severity is Severity.ERROR else "yellow"
    text = Text.assemble(
        (location, "bold"), "  ", (finding.rule.value, style), "\n", finding.message
    )
    if finding.hint:
        text.append(f"\nHint: {finding.hint}", "dim")
    return text


def _finding_annotation(finding: Finding, source: str) -> str:
    """Writes a finding as a GitHub Actions workflow command."""
    title = (
        f"{finding.rule.value}: {finding.key}" if finding.key else finding.rule.value
    )
    message = finding.message
    if finding.hint:
        message += f"\nHint: {finding.hint}"
    return _annotation(
        finding.severity,
        message,
        title=title,
        file=_workspace_path(source, finding.file),
        line=finding.line,
    )


def _annotation(
    severity: Severity,
    message: str,
    *,
    title: str,
    file: str | None = None,
    line: int | None = None,
) -> str:
    """Builds one ``::error`` or ``::warning`` workflow command.

    Everything in it may come from the template, so every part is escaped and
    no text can end the command early or start another one.
    """
    properties = [("title", title)]
    if file is not None:
        properties.insert(0, ("file", file))
        if line is not None:
            properties.insert(1, ("line", str(line)))
    rendered = ",".join(
        f"{name}={_escape_property(value)}" for name, value in properties
    )
    return f"::{severity.value} {rendered}::{_escape_data(message)}"


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def _workspace_path(source: str, file: str) -> str | None:
    """Returns a finding's file relative to the repository, if it is in it.

    Annotations name files relative to the workspace root, which differs from
    the working directory when a step sets one. A remote template has no file
    in the repository, so its findings annotate the run instead.
    """
    if source.startswith(("http://", "https://")):
        return None
    root = Path(source)
    if not root.is_dir():
        root = root.parent
    workspace = Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd())
    try:
        relative = Path(os.path.relpath((root / file).resolve(), workspace.resolve()))
    except ValueError:
        # Another drive on Windows.
        return None
    if relative.parts[:1] == ("..",):
        return None
    return relative.as_posix()
