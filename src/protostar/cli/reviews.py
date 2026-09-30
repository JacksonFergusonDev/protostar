"""Human and machine presentations of accepted project review decisions."""

import argparse
import difflib
import shlex
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from protostar.cli import schema, ui
from protostar.cli.changes import (
    Change,
    Entry,
    changes_to_your_files,
    classify,
    count,
    entry_tree,
    pending_entries,
)
from protostar.cli.decisions import (
    conflict_lines,
    preserved_lines,
    proposal_lines,
    resolved_line,
)
from protostar.cli.diff import format_diff, normalize_newlines
from protostar.cli.tui.launch import confirm_commands, resolve_conflicts
from protostar.config import UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.init_draft import DraftTemplate, InitDraft
from protostar.intent import DependencyGroup
from protostar.lifecycle import (
    PreparedProject,
    TemplateUpstream,
    locate_project,
    prepare_project,
)
from protostar.manifest import EnvironmentManifest
from protostar.merge import ConflictReason
from protostar.migrations import MigrationOutcome, MigrationStep
from protostar.preparation import (
    PreparedEdit,
    PreparedReview,
    deleted,
    select_resolutions,
)
from protostar.system import is_interactive
from protostar.system_deps import check_required_executables


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
    project = prepare_project(check_executables=False)
    if ui.is_json_mode:
        ui.emit_json(review_payload(project.review, project.upstream))
        return
    render_upstream(project.upstream)
    render_review(project.manifest, project.review, show_diffs=args.command == "diff")


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


def _summary(entries: Sequence[Entry], review: PreparedReview) -> Text:
    """Counts the pending paths by change, then every decision by kind."""
    counts = Counter(entry.change for entry in entries)
    parts = [
        f"{counts[change]} {change.label}"
        for change in (Change.NEW, Change.MODIFIED, Change.REMOVED)
        if counts[change]
    ]
    if review.conflicts:
        parts.append(count(len(review.conflicts), "conflict"))
    if review.resolved:
        parts.append(f"{len(review.resolved)} resolved")
    if review.proposals:
        parts.append(changes_to_your_files(review.proposals))
    if review.preserved:
        parts.append(count(len(review.preserved), "kept edit"))
    return Text(" · ".join(parts))


def render_review(
    manifest: EnvironmentManifest,
    review: PreparedReview,
    *,
    show_diffs: bool = False,
    applied: bool = False,
) -> None:
    """Renders shared decisions for inspection, checks, and application.

    The paths a sync changes or asks about show as init's labelled tree; the
    lines below it name each decision by id and the work beyond the files.

    Args:
        manifest: The manifest the review was prepared from.
        review: The prepared review.
        show_diffs: Whether to print each edit's unified diff after the tree.
        applied: Whether the review was just applied, which words the
            follow-up work as done.
    """
    entries = pending_entries(classify(manifest, review))
    if entries:
        ui.console.print(_summary(entries, review))
        ui.console.print(entry_tree(entries))
        ui.console.print()
    if show_diffs:
        for edit in review.edits:
            ui.console.print(format_diff(unified_diff(edit)), end="")
    resolve = "protostar sync --resolve"
    blocks: list[RenderableType] = [
        *(_migration_line(step, applied=applied) for step in review.migrations),
        *(conflict_lines(conflict, resolve) for conflict in review.conflicts),
        *(resolved_line(conflict) for conflict in review.resolved),
        *(
            proposal_lines(proposal, None if applied else resolve, applied=applied)
            for proposal in review.proposals
        ),
        *(
            preserved_lines(item, resolve, deletion=deleted(item))
            for item in review.preserved
        ),
    ]
    # A decision spans lines, so a blank line tells one from the next.
    for block in blocks:
        ui.console.print(block, soft_wrap=isinstance(block, Text))
        ui.console.print()
    if review.state_changed:
        msg = (
            "protostar.lock recorded the update."
            if applied
            else "protostar.lock will record the update."
        )
        ui.console.print(Text(msg, "dim"))
    if review.resolver.pending:
        _render_resolver(review, applied=applied)
    if review.hooks.install is not None:
        command = shlex.join(review.hooks.install.command)
        msg = "Installed" if applied else "Will install"
        ui.console.print(Text(f"{msg} git hooks with {command}."))
    for path in review.hooks.remove:
        msg = "Removed" if applied else "Will remove"
        ui.console.print(
            Text(f"{msg} the git hook {path}: its hook manager is no longer set up.")
        )
    if review.initialization_only or review.initialization_only_ide_probe:
        ui.console.print(
            Text("Setup that only init does, like git init, doesn't run again.", "dim")
        )
    if not review.pending and not review.hooks.pending:
        ui.console.print(Text("No pending work.", "dim"))


def _render_resolver(review: PreparedReview, *, applied: bool) -> None:
    """Says which packages uv adds, and whether it refreshes the lock."""
    groups = [
        ", ".join(requirements)
        if group is DependencyGroup.MAIN
        else f"{group.value}: {', '.join(requirements)}"
        for group, requirements in review.resolver.requirements
        if requirements
    ]
    if groups:
        verb = "uv added" if applied else "uv will add"
        ui.console.print(Text(f"{verb} packages: {'; '.join(groups)}."))
    if review.resolver.lock_required:
        verb = "uv refreshed" if applied else "uv will refresh"
        ui.console.print(Text(f"{verb} uv.lock, since the project's metadata changed."))
    if not applied:
        paths = " and ".join(review.resolver.footprint.paths)
        ui.console.print(
            Text(f"What uv changes in {paths} shows only once it runs.", "dim")
        )


_MIGRATED = {
    MigrationOutcome.MOVED: ("moved to {target}", "moves to {target}"),
    MigrationOutcome.TARGET_EXISTS: (
        "kept; {target} already exists",
        "stays; {target} already exists",
    ),
    MigrationOutcome.REMOVED: ("removed", "is removed"),
    MigrationOutcome.RETIRED: (
        "has your edits, so it stays until you choose; see its conflict below",
        "has your edits, so it stays until you choose; see its conflict below",
    ),
    MigrationOutcome.FORGOTTEN: ("already deleted", "already deleted"),
    MigrationOutcome.NOT_OWNED: (
        "wasn't created by Protostar, so it's left alone",
        "wasn't created by Protostar, so it's left alone",
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
        _check_tier_flag,
        _edit_variables,
        _parse_option_flags,
        _parse_var_flags,
        _resolve_template_variables,
    )

    located = locate_project(args.to)
    template = located.template
    values = _resolve_template_variables(
        template, dict(located.recipe.variables), _parse_var_flags(args.variables)
    )
    allowed = _check_allowed_secrets(template, args.allowed_secrets)
    options = _parse_option_flags(template, args.options)
    tier = _check_tier_flag(template, args.tier)
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
    return prepare_project(
        located, variables=values, allowed_secrets=allowed, options=options, tier=tier
    )


def _trusts(project: PreparedProject) -> bool:
    """Returns whether the project's template may run commands without asking."""
    recipe = project.manifest.recipe
    source = recipe.source if recipe is not None else None
    if source is None:
        # Tooling-only projects run only Protostar's own modules.
        return True
    return source.trusted_by(UserConfig.load(), Path.cwd())


def _confirm_trust(args: argparse.Namespace, project: PreparedProject) -> None:
    """Settles trust for the commands a sync of an untrusted template runs.

    The template's files decide what ``uv add`` builds and what a hook install
    runs, so an update from a template the user hasn't trusted runs them only
    once confirmed: on a screen in an interactive terminal, by ``--trust``
    anywhere, and never otherwise.

    Raises:
        ExecutionAbortedError: If the user cancels the confirmation.
        SecurityViolationError: If no confirmation is possible.
    """
    commands = project.review.commands
    if not commands:
        return
    if args.trust:
        ui.print_trusted_commands(commands)
        return
    if _trusts(project):
        return
    if ui.is_json_mode or not is_interactive():
        raise ui.untrusted_refusal("sync")
    if confirm_commands(commands) is None:
        raise ExecutionAbortedError("Sync cancelled by user.")


def handle_sync(args: argparse.Namespace) -> None:
    """Reviews or applies the current recipe without task replay.

    In an interactive terminal, conflicts that can be settled open the
    conflict screen first; its choices are applied like ``--resolve``.
    """
    # Nothing can be applied without these, so fail before asking anything.
    check_required_executables()
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
            render_review(project.manifest, review, show_diffs=args.dry_run)
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
    _confirm_trust(args, project)
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
                **ui.missing_tools_payload(result.missing_tools),
            }
        )
    else:
        render_upstream(project.upstream)
        render_review(project.manifest, review, applied=True)
        settled = [
            c for c in review.resolved if c.reason is not ConflictReason.PRESERVED
        ]
        updated = len(review.resolved) - len(settled)
        touched = len(result.touched_paths)
        parts = [
            (
                f"Updated {count(touched, 'path')}."
                if touched
                else "No files changed.",
                "bold green" if touched else "dim",
            )
        ]
        if settled:
            parts.append((f" Resolved {count(len(settled), 'conflict')}.", ""))
        if updated:
            parts.append((f" Took the update for {count(updated, 'kept edit')}.", ""))
        if review.conflicts:
            parts.append(
                (
                    f" {count(len(review.conflicts), 'conflict')} still open;"
                    " yours stays until you choose.",
                    "cyan",
                )
            )
        ui.console.print(Text.assemble(*parts))
        ui.print_missing_tools(result.missing_tools)
    if partial:
        sys.exit(1)
