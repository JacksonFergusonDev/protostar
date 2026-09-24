"""CLI presentation for checking a template before it is published."""

import argparse
import sys

from rich.text import Text

from protostar.cli import schema, ui
from protostar.errors import ProtostarError
from protostar.template_check import Finding, Severity, TemplateCheck, check_template


def handle_check_template(args: argparse.Namespace) -> None:
    """Checks a template and exits 1 when it fails.

    A template that cannot be retrieved raises its usual error instead, so the
    exit code and output always say whether the template was checked at all.
    """
    source: str = args.source
    strict: bool = args.strict
    try:
        check = check_template(source)
    except ProtostarError:
        if not ui.is_json_mode:
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
    if finding.key:
        location += f" {ui.glyph('→', '->')} {finding.key}"
    style = "red" if finding.severity is Severity.ERROR else "yellow"
    text = Text.assemble(
        (location, "bold"), "  ", (finding.rule.value, style), "\n", finding.message
    )
    if finding.hint:
        text.append(f"\nHint: {finding.hint}", "dim")
    return text
