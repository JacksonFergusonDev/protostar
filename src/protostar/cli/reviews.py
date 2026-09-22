"""Human and machine presentations of accepted project review decisions."""

import argparse
import difflib
import sys
from typing import Any

from protostar.cli import schema, ui
from protostar.lifecycle import inspect_project, prepare_project
from protostar.preparation import PreparedEdit, PreparedReview


def unified_diff(edit: PreparedEdit) -> str:
    """Formats only accepted byte edits, including newly created files."""
    lines = difflib.unified_diff(
        (edit.before or b"").decode().splitlines(keepends=True),
        edit.after.decode().splitlines(keepends=True),
        fromfile=f"a/{edit.path}" if edit.before is not None else "/dev/null",
        tofile=f"b/{edit.path}",
    )
    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in lines
    )


def review_payload(review: PreparedReview) -> dict[str, Any]:
    """Builds the common deterministic envelope for status and diff."""
    return {
        "api_version": schema.CLI_API_VERSION,
        "status": "reviewed",
        "pending": review.pending,
        "review": review.to_dict(),
        "diffs": [
            {"path": edit.path, "diff": unified_diff(edit)} for edit in review.edits
        ],
    }


def handle_review(args: argparse.Namespace) -> None:
    """Inspects the current project and renders one non-blocking review."""
    review = inspect_project()
    if ui.is_json_mode:
        ui.emit_json(review_payload(review))
        return
    render_review(review, show_diffs=args.command == "diff")


def render_review(
    review: PreparedReview, *, show_diffs: bool = False, applied: bool = False
) -> None:
    """Renders shared decisions for inspection, checks, and application."""
    ui.console.print(
        f"{len(review.edits)} accepted file edits; {len(review.conflicts)} conflicts; "
        f"{len(review.preserved)} preserved local deviations.",
        markup=False,
    )
    for edit in review.edits:
        ui.console.print(f"Accepted: {edit.path}", markup=False)
        if show_diffs:
            ui.console.print(unified_diff(edit), markup=False, highlight=False, end="")
    for path in review.directories:
        ui.console.print(f"Accepted directory: {path}", markup=False)
    for conflict in review.conflicts:
        location = ".".join(conflict.location.keys)
        identity = conflict.location.identity or ""
        ui.console.print(
            f"Conflict: {conflict.location.file} {location} {identity}: {conflict.reason.value}",
            markup=False,
        )
    for item in review.preserved:
        ui.console.print(
            f"Preserved {'deletion' if item.deleted else 'local edit'}: {item.location.file} "
            f"{'.'.join(item.location.keys)} {item.location.identity or ''}",
            markup=False,
        )
    if review.state_changed:
        ui.console.print(
            (
                "Ownership/provenance state advanced."
                if applied
                else "Ownership/provenance state will advance (may require no content write)."
            ),
            markup=False,
        )
    if review.resolver.pending:
        for group, requirements in review.resolver.requirements:
            if requirements:
                ui.console.print(
                    f"Resolver {group.value}: {', '.join(requirements)}", markup=False
                )
        ui.console.print(
            f"Resolver footprint: {', '.join(review.resolver.footprint.paths)}; "
            + ("executed." if applied else "output unknown."),
            markup=False,
        )
        if review.resolver.lock_required:
            ui.console.print(
                (
                    "Lock refreshed after accepted metadata changes."
                    if applied
                    else "Lock refresh required after accepted metadata changes."
                ),
                markup=False,
            )
    if review.initialization_only or review.initialization_only_ide_probe:
        ui.console.print(
            "Initialization-only tasks and IDE probes are excluded.", markup=False
        )
    if not review.pending:
        ui.console.print("No pending work.", markup=False)


def handle_sync(args: argparse.Namespace) -> None:
    """Reviews or applies the current recipe without prompts or task replay."""
    project = prepare_project()
    review = project.review
    if args.dry_run or args.check:
        payload = review_payload(review)
        if args.check:
            payload["check_passed"] = not review.pending
        if ui.is_json_mode:
            ui.emit_json(payload)
        else:
            render_review(review, show_diffs=args.dry_run)
            if args.check:
                ui.console.print(
                    "Check passed."
                    if not review.pending
                    else "Check failed: pending work."
                )
        if args.check and review.pending:
            sys.exit(1)
        return
    if ui.is_json_mode:
        result = project.apply()
    else:
        with ui.progress_trail("Applying changes") as progress:
            result = project.apply(progress=progress)
    partial = bool(review.conflicts)
    if ui.is_json_mode:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "partial" if partial else "success",
                "review": review.to_dict(),
                "result": result.to_dict(),
            }
        )
    else:
        render_review(review, applied=True)
        ui.console.print(
            f"Applied changes to {len(result.touched_paths)} paths; "
            f"{len(review.conflicts)} conflicts retained.",
            markup=False,
        )
    if partial:
        sys.exit(1)
