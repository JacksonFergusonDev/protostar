"""Human and machine presentations of accepted project review decisions."""

import argparse
import difflib
import sys
from typing import Any, cast

from rich.text import Text

from protostar.cli import schema, ui
from protostar.cli.diff import format_diff, normalize_newlines
from protostar.cli.tui.launch import resolve_conflicts
from protostar.config import UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.init_draft import DraftTemplate, InitDraft
from protostar.lifecycle import (
    PreparedProject,
    TemplateUpstream,
    locate_project,
    prepare_project,
)
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    ResolutionChoice,
    describe_location,
)
from protostar.migrations import MigrationOutcome, MigrationStep
from protostar.preparation import (
    PreparedEdit,
    PreparedReview,
    deleted,
    select_resolutions,
)
from protostar.system import is_interactive

SETTLED = {
    ResolutionChoice.LOCAL: "kept local content",
    ResolutionChoice.DESIRED: "took the update",
    ResolutionChoice.BOTH: "kept both",
}


def _diff_lines(content: bytes | None) -> list[str]:
    if not content:
        return []
    return normalize_newlines(content.decode()).splitlines(keepends=True)


def unified_diff(edit: PreparedEdit) -> str:
    """Formats only accepted byte edits, including newly created files."""
    lines = difflib.unified_diff(
        _diff_lines(edit.before),
        _diff_lines(edit.after),
        fromfile=f"a/{edit.path}" if edit.before is not None else "/dev/null",
        tofile=f"b/{edit.path}" if edit.after is not None else "/dev/null",
    )
    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in lines
    )


def review_payload(
    review: PreparedReview, upstream: TemplateUpstream | None = None
) -> dict[str, Any]:
    """Builds the common deterministic envelope for status and diff."""
    return {
        "api_version": schema.CLI_API_VERSION,
        "status": "reviewed",
        "pending": review.pending,
        "template": upstream.to_dict() if upstream else None,
        "review": review.to_dict(),
        "diffs": [
            {"path": edit.path, "diff": unified_diff(edit)} for edit in review.edits
        ],
    }


def handle_review(args: argparse.Namespace) -> None:
    """Inspects the current project and renders one non-blocking review."""
    project = prepare_project()
    if ui.is_json_mode:
        ui.emit_json(review_payload(project.review, project.upstream))
        return
    render_upstream(project.upstream)
    render_review(project.review, show_diffs=args.command == "diff")


def render_upstream(upstream: TemplateUpstream | None) -> None:
    """Renders the template's ref, and what its repository offers beyond it."""
    if upstream is None:
        return
    line = Text.assemble(
        ("Template ", "dim"),
        (upstream.ref, "bold"),
        (f" @ {upstream.revision[:12]}", "dim"),
    )
    if not upstream.reachable:
        line.append("; its repository could not be checked for updates.", "dim")
    elif upstream.newer:
        line.append_text(
            Text.assemble(
                "; ",
                (f"{upstream.newer} available", "bold yellow"),
                f" (sync --to {upstream.newer}).",
            )
        )
    elif upstream.moved:
        line.append_text(
            Text.assemble(
                "; ",
                (f"{upstream.ref} moved to {upstream.moved[:12]}", "bold yellow"),
                f" (sync --to {upstream.ref}).",
            )
        )
    elif upstream.kind is None:
        line.append("; the repository no longer has this ref.", "yellow")
    else:
        line.append("; up to date.", "dim")
    ui.console.print(line, soft_wrap=True)


def render_review(
    review: PreparedReview, *, show_diffs: bool = False, applied: bool = False
) -> None:
    """Renders shared decisions for inspection, checks, and application."""
    ui.console.print(
        Text.assemble(
            (
                f"{len(review.edits)} accepted file edits",
                ("green" if applied else "") if review.edits else "dim",
            ),
            ("; ", "dim"),
            (
                f"{len(review.conflicts)} conflicts",
                "bold red" if review.conflicts else "dim",
            ),
            ("; ", "dim"),
            (
                f"{len(review.resolved)} resolved",
                "" if review.resolved else "dim",
            ),
            ("; ", "dim"),
            (
                f"{len(review.proposals)} changes to your files",
                "" if review.proposals else "dim",
            ),
            ("; ", "dim"),
            (
                f"{len(review.preserved)} preserved local deviations.",
                "" if review.preserved else "dim",
            ),
        )
    )
    for step in review.migrations:
        ui.console.print(_migration_line(step, applied=applied), soft_wrap=True)
    for edit in review.edits:
        ui.console.print(
            Text.assemble(
                (
                    "Accepted: " if edit.after is not None else "Removed: ",
                    "green" if applied else "",
                ),
                (
                    edit.path,
                    ui.path_style(edit.path.rsplit("/", 1)[-1], directory=False),
                ),
            )
        )
        if show_diffs:
            ui.console.print(format_diff(unified_diff(edit)), end="")
    for path in review.directories:
        ui.console.print(
            Text.assemble(
                ("Accepted directory: ", "green" if applied else ""),
                (
                    path,
                    ui.path_style(path.rsplit("/", 1)[-1], directory=True),
                ),
            )
        )
    for conflict in review.conflicts:
        choices = ", ".join(choice.value for choice in conflict.choices)
        choice_text = f"resolve with {choices}." if choices else "resolve by hand."
        ui.console.print(
            Text.assemble(
                (f"Conflict {conflict.id}: ", "bold red"),
                (_where(conflict), "bold"),
                (f": {conflict.reason.value}; {choice_text}"),
            ),
            soft_wrap=True,
        )
    for conflict in review.resolved:
        settled = SETTLED[cast(ResolutionChoice, conflict.resolution)]
        ui.console.print(
            Text.assemble(
                (f"Resolved {conflict.id}: ", "bold green" if applied else "bold"),
                (_where(conflict), "bold"),
                (f": {settled}."),
            ),
            soft_wrap=True,
        )
    for proposal in review.proposals:
        declined = proposal.resolution is ResolutionChoice.LOCAL
        ui.console.print(
            Text.assemble(
                (f"Proposed {proposal.id}: ", "bold"),
                (_where(proposal), "bold"),
                (
                    ": declined; kept your content."
                    if declined
                    else f": {'applied' if applied else 'applies'}; decline with local."
                ),
            ),
            soft_wrap=True,
        )
    for item in review.preserved:
        action = "deletion" if deleted(item) else "local edit"
        ui.console.print(
            Text.assemble(
                f"Preserved {action} {item.id}: ",
                (_where(item), "bold"),
                (": take the update with desired.", "dim"),
            ),
            soft_wrap=True,
        )
    if review.state_changed:
        msg = (
            "Ownership/provenance state advanced."
            if applied
            else "Ownership/provenance state will advance (may require no content write)."
        )
        ui.console.print(Text(msg, "green" if applied else ""))
    if review.resolver.pending:
        for group, requirements in review.resolver.requirements:
            if requirements:
                ui.console.print(
                    Text(f"Resolver {group.value}: {', '.join(requirements)}")
                )
        ui.console.print(
            Text.assemble(
                f"Resolver footprint: {', '.join(review.resolver.footprint.paths)}; ",
                (
                    "executed." if applied else "output unknown.",
                    "green" if applied else "dim",
                ),
            )
        )
        if review.resolver.lock_required:
            msg = (
                "Lock refreshed after accepted metadata changes."
                if applied
                else "Lock refresh required after accepted metadata changes."
            )
            ui.console.print(Text(msg, "green" if applied else ""))
    if review.initialization_only or review.initialization_only_ide_probe:
        ui.console.print(
            Text("Initialization-only tasks and IDE probes are excluded.", "dim")
        )
    if not review.pending:
        ui.console.print(Text("No pending work.", "dim"))


_MIGRATED = {
    MigrationOutcome.MOVED: ("moved to {target}", "moves to {target}"),
    MigrationOutcome.TARGET_EXISTS: (
        "kept; {target} already exists",
        "stays; {target} already exists",
    ),
    MigrationOutcome.REMOVED: ("removed", "is removed"),
    MigrationOutcome.RETIRED: (
        "has your edits; keep it with local or delete it with desired",
        "has your edits; keep it with local or delete it with desired",
    ),
    MigrationOutcome.FORGOTTEN: ("already deleted", "already deleted"),
    MigrationOutcome.NOT_OWNED: (
        "not a Protostar seed; left alone",
        "not a Protostar seed; left alone",
    ),
}


def _migration_line(step: MigrationStep, *, applied: bool) -> Text:
    """Describes what one template migration did, or does, to one file."""
    done, pending = _MIGRATED[step.outcome]
    action = (done if applied else pending).format(target=step.target)
    return Text.assemble(
        (f"Migration {step.version}: ", "bold"),
        (step.path, "bold"),
        f" {action}.",
    )


def _where(conflict: MergeConflict) -> str:
    """Returns the file, position, and identity of a conflict on one line."""
    parts = (
        conflict.location.file,
        describe_location(conflict.location),
        conflict.location.identity or "",
    )
    return " ".join(part for part in parts if part)


def _asks(args: argparse.Namespace, review: PreparedReview) -> bool:
    """Returns whether to ask how conflicts and proposals are settled first.

    Preserved deviations alone never open the screen: they are no pending
    work, and ``status`` lists how to take each one's update.
    """
    return (
        not (args.dry_run or args.check or args.resolve or ui.is_json_mode)
        and is_interactive()
        and (
            any(conflict.choices for conflict in review.conflicts)
            or bool(review.proposals)
        )
    )


def _prepare_sync(args: argparse.Namespace) -> PreparedProject:
    """Locates the project at the requested ref and prepares its review.

    Variables the template needs and nobody supplied are asked for on the
    variables screen in an interactive terminal; elsewhere rendering raises
    ``MissingTemplateVariablesError`` listing them all.
    """
    from protostar.cli.main import (
        _check_allowed_secrets,
        _edit_variables,
        _parse_var_flags,
        _resolve_template_variables,
    )

    located = locate_project(args.to)
    template = located.template
    values = _resolve_template_variables(
        template, dict(located.recipe.variables), _parse_var_flags(args.variables)
    )
    allowed = _check_allowed_secrets(template, args.allowed_secrets)
    if (
        template is not None
        and template.variables - values.keys()
        and is_interactive()
        and not (ui.is_json_mode or args.check)
    ):
        draft = _edit_variables(
            InitDraft(
                template=DraftTemplate(template, is_external=True),
                variables=tuple(sorted(values.items())),
                allowed_secrets=allowed,
                existing_recipe=located.recipe,
            ),
            UserConfig(python_version=located.recipe.python, ide=located.recipe.ide),
            command="sync",
        )
        values, allowed = dict(draft.variables), draft.allowed_secrets
    return prepare_project(located, variables=values, allowed_secrets=allowed)


def handle_sync(args: argparse.Namespace) -> None:
    """Reviews or applies the current recipe without task replay.

    In an interactive terminal, conflicts that can be settled open the
    conflict screen first; its choices are applied like ``--resolve``.
    """
    project = _prepare_sync(args)
    if args.resolve:
        project = project.resolve(
            select_resolutions(project.review.decisions, args.resolve)
        )
    elif _asks(args, project.review):
        choices = resolve_conflicts(project)
        if choices is None:
            raise ExecutionAbortedError("Sync cancelled by user.")
        if choices:
            project = project.resolve(choices)
    review = project.review
    if args.dry_run or args.check:
        payload = review_payload(review, project.upstream)
        if args.check:
            payload["check_passed"] = not review.pending
        if ui.is_json_mode:
            ui.emit_json(payload)
        else:
            render_upstream(project.upstream)
            render_review(review, show_diffs=args.dry_run)
            if args.check:
                if not review.pending:
                    ui.console.print(
                        Text.assemble(
                            (f"{ui.glyph('✔', '+')} ", "green"),
                            ("Check passed.", "bold green"),
                        )
                    )
                else:
                    ui.console.print(
                        Text.assemble(
                            (f"{ui.glyph('✖', 'x')} ", "bold red"),
                            ("Check failed: pending work.", "bold red"),
                        )
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
                "template": project.upstream.to_dict() if project.upstream else None,
                "review": review.to_dict(),
                "result": result.to_dict(),
            }
        )
    else:
        render_upstream(project.upstream)
        render_review(review, applied=True)
        settled = [
            c for c in review.resolved if c.reason is not ConflictReason.PRESERVED
        ]
        updated = len(review.resolved) - len(settled)
        ui.console.print(
            Text.assemble(
                (
                    f"Applied changes to {len(result.touched_paths)} paths; ",
                    "bold green" if result.touched_paths else "dim",
                ),
                (
                    f"{len(settled)} conflicts resolved",
                    "" if settled else "dim",
                ),
                (f"; {updated} kept edits updated" if updated else "", ""),
                ("; ", "dim"),
                (
                    f"{len(review.conflicts)} conflicts retained.",
                    "bold red" if review.conflicts else "dim",
                ),
            )
        )
    if partial:
        sys.exit(1)
