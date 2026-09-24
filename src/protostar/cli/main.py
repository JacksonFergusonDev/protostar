import argparse
import importlib.resources
import logging
import os
import platform
import shlex
import shutil
import subprocess
import sys
import traceback
import urllib.parse
from typing import TYPE_CHECKING, Any

from rich.columns import Columns

if TYPE_CHECKING:
    from protostar.orchestrator import Orchestrator
from rich.console import Group
from rich.logging import RichHandler
from rich.markup import escape
from rich.text import Text

from protostar.cli import parser, schema, ui
from protostar.cli.docs_links import format_docs_link
from protostar.cli.tui.launch import edit_variables, review_changes
from protostar.config import (
    DEFAULT_CONFIG_CONTENT,
    TemplateSource,
    UserConfig,
    active_config_source,
    select_config_source,
)
from protostar.docs_registry import DocsPage
from protostar.errors import (
    AggregatedDependencyError,
    CommandExecutionError,
    ConfigurationError,
    ExecutionAbortedError,
    ExecutionInterruptedError,
    ExitCode,
    FileSystemError,
    InvalidUsageError,
    MissingDependencyError,
    NetworkFetchError,
    ProtostarError,
    SecurityViolationError,
    TemplateResolutionError,
)
from protostar.fs import atomic_write_text
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.intent import TemplateOrigin
from protostar.interpolation import VARIABLE_NAME
from protostar.manifest import CollisionStrategy
from protostar.modules import (
    TOOLING_MODULES,
    BootstrapModule,
)
from protostar.secret_guard import credential_named
from protostar.sync_state import check_one_shot_workspace, check_workspace_identity
from protostar.system import is_interactive

logger = logging.getLogger("protostar")


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments."""
    if getattr(args, "list_templates", False):
        ui._print_templates_and_exit()

    override_target = getattr(args, "from_path", None)
    template_name = getattr(args, "template_name", None)
    flag_values = _parse_var_flags(getattr(args, "variables", []))

    from dataclasses import replace
    from pathlib import Path

    from protostar.analysis import analyze_project
    from protostar.recipe import Tool, read_recipe

    user_config = UserConfig.load()
    existing_recipe = read_recipe(Path("pyproject.toml"))
    if getattr(args, "one_shot", False):
        check_one_shot_workspace(Path.cwd())
    analysis = None if existing_recipe else analyze_project(Path.cwd())
    if existing_recipe:
        user_config = replace(
            user_config, python_version=existing_recipe.python, ide=existing_recipe.ide
        )
    is_external = False
    is_user_aliased = False
    is_trusted = False

    if override_target and template_name:
        raise ConfigurationError(
            "Cannot use both '--template' and '--from' simultaneously."
        )

    if override_target:
        is_external = True

    if template_name:
        from protostar.templates import TemplateType, discover_templates

        matched_info = None
        # 1. Match by alias (case-insensitive)
        for tmpl in discover_templates(user_config):
            if tmpl.alias.lower() == template_name.lower():
                matched_info = tmpl
                break

        # 2. Match by display name (case-insensitive)
        if matched_info is None:
            for tmpl in discover_templates(user_config):
                if tmpl.name.lower() == template_name.lower():
                    matched_info = tmpl
                    break

        if matched_info:
            if matched_info.type == TemplateType.BUILT_IN:
                override_target = str(
                    importlib.resources.files("protostar.templates").joinpath(
                        f"{matched_info.alias}.toml"
                    )
                )
                is_trusted = True
            else:
                alias_cfg = user_config.templates[matched_info.alias]
                override_target = alias_cfg.source
                is_external = True
                is_user_aliased = True
                is_trusted = alias_cfg.trusted
        else:
            raise ConfigurationError(
                f"Template '{template_name}' not found in built-ins or global configuration aliases."
            )

    built_in = (
        matched_info.alias
        if template_name and matched_info and not is_external
        else None
    )
    source: TemplateSource | None = None
    if not override_target and existing_recipe and existing_recipe.source:
        source = existing_recipe.source.acquire(Path.cwd())
        is_external = existing_recipe.source.origin is not TemplateOrigin.BUILT_IN
        is_trusted = not is_external
    elif override_target:
        source = TemplateSource.load(
            override_target, built_in=built_in, display_name=template_name
        )
    # plan() checks this too, but only after the variables are entered.
    check_workspace_identity(Path.cwd(), source.reference if source else None)
    variables = _resolve_template_variables(
        source,
        dict(existing_recipe.variables) if existing_recipe else {},
        flag_values,
    )
    allowed_secrets = _check_allowed_secrets(
        source, getattr(args, "allowed_secrets", [])
    )
    if source and (flagged := credential_named(source.variables)):
        ui.warn_credential_names(flagged)
    tool_overrides = tuple(
        (Tool(mod.config_key), value)
        for mod in TOOLING_MODULES
        if (value := getattr(args, mod.__class__.__name__, None)) is not None
    )
    if getattr(args, "force_merge", False) and getattr(args, "force_replace", False):
        raise ConfigurationError("Choose either --force-merge or --force-replace.")
    strategy = (
        CollisionStrategy.MERGE
        if getattr(args, "force_merge", False)
        else CollisionStrategy.OVERWRITE
        if getattr(args, "force_replace", False)
        else None
    )
    draft = InitDraft(
        template=DraftTemplate(source, is_external, is_user_aliased, is_trusted)
        if source
        else None,
        tool_overrides=tool_overrides,
        docker=getattr(args, "docker", None),
        python_version=getattr(args, "python_version", None),
        variables=tuple(sorted(variables.items())),
        allowed_secrets=allowed_secrets,
        collision_strategy=strategy,
        existing_recipe=existing_recipe,
        analysis=analysis,
        one_shot=getattr(args, "one_shot", False),
    )
    if (
        source
        and source.variables - variables.keys()
        and is_interactive()
        and not ui.is_json_mode
    ):
        edited = edit_variables(draft, user_config)
        if edited is None:
            raise ExecutionAbortedError("Variable entry cancelled by user.")
        draft = edited
    modules, request = resolve_init(draft, user_config)

    # 4. Undocumented Crash Test Injection
    if getattr(args, "crash_test", False):

        class CrashModule(BootstrapModule):
            @property
            def name(self) -> str:
                return "CrashTest"

            def pre_flight(self) -> None:
                raise TypeError("INTENTIONAL_CRASH")

            def build(self, manifest: Any) -> None:
                pass

        modules.append(CrashModule())

    orchestrator_cls: type[Orchestrator] = sys.modules[__name__].Orchestrator
    engine = orchestrator_cls(modules, user_config, request=request)

    if getattr(args, "dry_run", False):
        manifest = engine.plan()
        if ui.is_json_mode:
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "planned",
                    "manifest": manifest.to_dict(),
                    "analysis": analysis.to_dict() if analysis else None,
                }
            )
        else:
            ui.print_dry_run_summary(manifest)
        sys.exit(0)

    decision = None
    if (
        is_interactive()
        and not ui.is_json_mode
        and ui.needs_review(request, engine.plan())
    ):
        decision = review_changes(draft, user_config)
        if decision is None:
            raise ExecutionAbortedError("Change review cancelled by user.")
        ui.print_review_summary(decision)
        request = replace(request, collision_strategy=decision.draft.collision_strategy)
        engine.request = request

    result = ui._run_engine(engine, request, decision)
    if ui.is_json_mode:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "result": result.to_dict(),
            }
        )


def handle_config(args: argparse.Namespace) -> None:
    """Handles the 'config' subcommand to manage global CLI settings.

    Opens the global configuration file in the system's default editor.
    Ensures the parent directory exists and seeds a default configuration
    template if the file is missing. Safely tokenizes the $EDITOR environment
    variable to support complex commands (e.g., 'code --wait').

    Args:
        args: Parsed CLI arguments mapping to this command.
    """
    source = active_config_source()
    if source.path is None:
        raise InvalidUsageError(
            "There is no configuration file to edit while configuration is disabled.",
            hint="Drop '--no-config' to edit the selected configuration file.",
            docs_path=DocsPage.CONFIGURATION,
        )
    config_path = source.path
    logger.debug("Handling 'config' command (config path: %s)", config_path)
    if not config_path.parent.exists():
        logger.debug("Creating configuration parent directory: %s", config_path.parent)
        config_path.parent.mkdir(parents=True, exist_ok=True)

    if getattr(args, "force", False) and not getattr(args, "reset", False):
        raise InvalidUsageError(
            "--force can only be used with --reset.",
            hint="Run 'protostar config --reset --force' to reset configuration without prompting.",
            docs_path=DocsPage.CONFIGURATION,
        )

    if getattr(args, "reset", False):
        if not getattr(args, "force", False):
            from rich.prompt import Confirm

            try:
                confirmed = Confirm.ask(
                    "Warning: this will erase your current configuration, are you sure you want to do this?",
                    default=False,
                    console=ui.console,
                )
            except (KeyboardInterrupt, EOFError) as e:
                raise ExecutionAbortedError("Configuration reset aborted.") from e
            if not confirmed:
                ui.console.print("[yellow]Configuration reset aborted.[/yellow]")
                return

        logger.debug(
            "Resetting configuration file at %s to default template", config_path
        )
        atomic_write_text(config_path, DEFAULT_CONFIG_CONTENT)
        ui.console.print(
            Text.assemble(
                (f"{ui.glyph('✔', '+')} ", "green"),
                ("Reset configuration at ", "bold green"),
                (str(config_path), "cyan"),
                (" to default state.", "bold green"),
            )
        )
        return

    if not config_path.exists():
        logger.debug("Writing initial default configuration to %s", config_path)
        atomic_write_text(config_path, DEFAULT_CONFIG_CONTENT)
        ui.console.print(
            Text.assemble(
                (f"{ui.glyph('✔', '+')} ", "green"),
                ("Initialized default configuration at ", "bold green"),
                (str(config_path), "cyan"),
            )
        )

    editor_env = os.environ.get("EDITOR", "nano")
    logger.debug("Resolved $EDITOR environment variable: %r", editor_env)
    editor_cmd = shlex.split(editor_env)

    if not editor_cmd:
        raise ConfigurationError("The $EDITOR environment variable is empty.")

    editor_binary = shutil.which(editor_cmd[0])
    logger.debug(
        "Looked up editor binary '%s' in PATH: %s", editor_cmd[0], editor_binary
    )
    if not editor_binary:
        raise ConfigurationError(
            f"Could not resolve editor executable '{editor_cmd[0]}'.\n"
            "Ensure your $EDITOR environment variable is set to a valid binary in your PATH."
        )

    editor_cmd.append(str(config_path))
    logger.debug("Launching editor command: %s", editor_cmd)

    try:
        subprocess.run(editor_cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise ConfigurationError(
            f"Editor '{editor_env}' exited with non-zero status: {e}"
        ) from e


def configure_logging() -> None:
    """Injects Rich tracebacks and debug handlers into the global logger.

    Writes to ``stderr`` to preserve ``stdout`` for data output and
    machine-readable JSON payloads.
    """
    logger = logging.getLogger("protostar")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(
        RichHandler(console=ui._stderr_console, markup=True, rich_tracebacks=True)
    )


def _parse_var_flags(entries: list[str]) -> dict[str, str]:
    """Parses repeated ``--var NAME=VALUE`` flags.

    Error messages never repeat a value: one may be a secret passed by mistake.

    Args:
        entries: The raw ``--var`` arguments, in order.

    Returns:
        Each variable name mapped to its value.

    Raises:
        InvalidUsageError: If an entry is malformed or a name repeats.
    """
    values: dict[str, str] = {}
    for entry in entries:
        name, separator, value = entry.partition("=")
        if not separator or not VARIABLE_NAME.fullmatch(name):
            raise InvalidUsageError(
                "Each --var must be NAME=VALUE.",
                hint="NAME is a letter or underscore followed by letters, digits, or underscores.",
            )
        if name in values:
            raise InvalidUsageError(
                f"--var {name} is given more than once.",
                hint="Pass each template variable once.",
            )
        values[name] = value
    return values


def _resolve_template_variables(
    source: TemplateSource | None,
    recorded: dict[str, str],
    flags: dict[str, str],
) -> dict[str, str]:
    """Collects values for a template's variables.

    Recorded values come first and ``--var`` flags override them. Any still
    missing are left out: the caller asks for them in an interactive terminal,
    and otherwise rendering raises ``MissingTemplateVariablesError`` listing
    them all.

    Args:
        source: The template being applied, if any.
        recorded: Values from the project's existing recipe.
        flags: Values from ``--var`` flags.

    Returns:
        Values for the template's variables; recorded values the template no
        longer uses are dropped.

    Raises:
        InvalidUsageError: If a flag names no variable of the template, or
            flags are given without a template.
    """
    if source is None:
        if flags:
            raise InvalidUsageError(
                "--var needs a template.",
                hint="Pass --template or --from, or run init in a project that records one.",
            )
        return {}
    unknown = sorted(set(flags) - source.variables)
    if unknown:
        known = ", ".join(sorted(source.variables)) or "none"
        raise InvalidUsageError(
            f"The template has no variable named {', '.join(unknown)}.",
            hint=f"Its variables are: {known}.",
        )
    values = {
        name: value for name, value in recorded.items() if name in source.variables
    }
    values.update(flags)
    return values


def _check_allowed_secrets(
    source: TemplateSource | None, names: list[str]
) -> frozenset[str]:
    """Validates ``--allow-secret`` names against the template's variables.

    Args:
        source: The template being applied, if any.
        names: The raw ``--allow-secret`` arguments.

    Returns:
        The variables whose flagged values the user confirmed are not secrets.

    Raises:
        InvalidUsageError: If a name is no variable of the template, or names
            are given without a template.
    """
    if names and source is None:
        raise InvalidUsageError(
            "--allow-secret needs a template.",
            hint="Pass --template or --from, or run init in a project that records one.",
        )
    unknown = sorted(set(names) - (source.variables if source else frozenset()))
    if unknown:
        known = ", ".join(sorted(source.variables)) if source else ""
        raise InvalidUsageError(
            f"The template has no variable named {', '.join(unknown)}.",
            hint=f"Its variables are: {known or 'none'}.",
        )
    return frozenset(names)


def main() -> None:
    """Main execution pipeline for the Protostar CLI."""
    ui.replace_unencodable_output()
    ui.is_json_mode = ui.is_json_mode or ("--json" in sys.argv)

    arg_parser = parser.build_parser()
    parser._dispatch_preparser_flags(arg_parser)

    try:
        parser.intercept_interactive_wizards(arg_parser)
        args = arg_parser.parse_args()

        # Applied before any handler reads configuration.
        select_config_source(
            getattr(args, "config", None),
            disabled=getattr(args, "no_config", False),
        )

        if getattr(args, "verbose", False):
            configure_logging()

        if not getattr(args, "command", None):
            arg_parser.print_help()
            sys.exit(1)

        args.func(args)

    except ProtostarError as e:
        if ui.is_json_mode:
            # Machine-readable error envelope: structured type, message, and optional extras.
            error_dict: dict[str, Any] = {
                "type": type(e).__name__,
                "message": str(e),
            }
            if e.hint:
                error_dict["hint"] = e.hint
            ctx = getattr(e, "rollback_context", None)
            if ctx is not None:
                error_dict["rollback_context"] = ctx.to_dict()
            docs_url = None
            if e.docs_path:
                docs_url = e.docs_path.build_url(e.docs_anchor)
            elif ctx is not None and not ctx.is_external:
                docs_url = DocsPage.ROLLBACK.build_url()
            if docs_url:
                error_dict["docs_url"] = docs_url
            error_dict.update(e.details())
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "error",
                    "error": error_dict,
                }
            )
        else:
            # Expected domain errors route here for clean terminal formatting
            ui.console.print()

            # Domain error text is data, not markup: escape it before composing
            # the error body so literal '[templates]' survives Rich rendering.
            body = escape(str(e))
            if isinstance(e, CommandExecutionError) and e.output_detail:
                body += f"\n\n[dim]{escape(e.output_detail)}[/dim]"
            if e.hint:
                body += f"\n\n[dim]Hint: {escape(e.hint)}[/dim]"
            ctx = getattr(e, "rollback_context", None)
            from rich.console import RenderableType

            body_renderable: RenderableType
            if ctx is not None:
                rb_group: list[RenderableType] = []
                if ctx.touched_paths:
                    paths = sorted(ctx.touched_paths)
                    if len(paths) > 15:
                        display_paths = [f"[dim]{p}[/dim]" for p in paths[:15]]
                        display_paths.append(
                            f"[dim]...and {len(paths) - 15} more paths[/dim]"
                        )
                    else:
                        display_paths = [f"[dim]{p}[/dim]" for p in paths]

                    rb_group.append(
                        Text.from_markup(
                            f"[bold green]{ui.glyph('✓', '+')} Protostar successfully "
                            "rolled back all tracked workspace changes:[/bold green]\n"
                        )
                    )
                    rb_group.append(Columns(display_paths, padding=(0, 2)))
                    rb_group.append(Text(""))

                if ctx.is_external:
                    rb_group.append(
                        Text.from_markup(
                            "[yellow]Note: Protostar could not clean up side effects from external subprocesses.[/yellow]"
                        )
                    )
                    if ctx.completed_tasks or ctx.interrupted_task:
                        rb_group.append(
                            Text(
                                "The following commands were run before execution aborted:\n"
                            )
                        )
                        for t in ctx.completed_tasks:
                            desc = " ".join(t.command) if t.command else ""
                            rb_group.append(
                                Text.assemble(
                                    ("• ", "dim"),
                                    ("[Completed]   ", "green"),
                                    (desc, "dim"),
                                )
                            )
                        if ctx.interrupted_task:
                            t = ctx.interrupted_task
                            desc = " ".join(t.command) if t.command else ""
                            rb_group.append(
                                Text.assemble(
                                    ("• ", "dim"),
                                    ("[Interrupted] ", "yellow"),
                                    (desc, "dim"),
                                )
                            )
                else:
                    rb_group.append(
                        Text(
                            "Note: Some standard artifacts (like the .venv/ directory) remain but are safe to ignore.",
                            "dim",
                        )
                    )
                    docs_page = e.docs_path or DocsPage.ROLLBACK
                    rb_group.append(Text(""))
                    rb_group.append(format_docs_link(docs_page, e.docs_anchor))

                # Create a Group to render multiple items seamlessly
                body_renderable = (
                    Group(Text.from_markup(body), Text(""), *rb_group)
                    if body.strip()
                    else Group(*rb_group)
                )
            else:
                if e.docs_path:
                    body_renderable = Group(
                        Text.from_markup(body),
                        Text(""),
                        format_docs_link(e.docs_path, e.docs_anchor),
                    )
                else:
                    body_renderable = Text.from_markup(body)

            title = (
                "Execution interrupted"
                if isinstance(e, ExecutionInterruptedError)
                else "Execution aborted"
            )
            ui.console.print(ui.heading(title, "bold red"))
            ui.console.print(ui.indented(body_renderable))

        # Route specific domain exceptions to standard POSIX status codes
        if isinstance(e, InvalidUsageError):
            sys.exit(ExitCode.USAGE)  # 64: Command line usage error
        if isinstance(e, SecurityViolationError):
            sys.exit(ExitCode.NOPERM)  # 77: Permission denied / Security constraint
        if isinstance(e, ConfigurationError):
            sys.exit(ExitCode.CONFIG)  # 78: Malformed configuration tables
        if isinstance(e, TemplateResolutionError):
            sys.exit(
                ExitCode.DATAERR
            )  # 65: Data format error (e.g., bad zip, missing variables)
        if isinstance(e, NetworkFetchError):
            sys.exit(ExitCode.TEMPFAIL)  # 75: Temporary failure (network drop)
        if isinstance(e, (MissingDependencyError, AggregatedDependencyError)):
            sys.exit(
                ExitCode.UNAVAILABLE
            )  # 69: Expected background tool executable missing
        if isinstance(e, FileSystemError):
            sys.exit(ExitCode.IOERR)  # 74: Critical disk access or storage write faults
        if isinstance(e, (ExecutionAbortedError, ExecutionInterruptedError)):
            sys.exit(
                130
            )  # User aborted via interactive prompt or interrupted execution

        sys.exit(1)  # Generic operational failure fallback

    except KeyboardInterrupt:
        # Catch Ctrl+C cleanly
        if ui.is_json_mode:
            ui._stderr_console.print("\n[bold red]Aborted by user.[/bold red]")
        else:
            ui.console.print("\n[bold red]Aborted by user.[/bold red]")
        sys.exit(130)

    except Exception as e:
        if ui.is_json_mode:
            # Emit a compact JSON error envelope; print the traceback to stderr.
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "error",
                    "error": {
                        "type": "InternalError",
                        "message": (
                            f"An unexpected internal error occurred: "
                            f"{type(e).__name__}: {e}"
                        ),
                    },
                }
            )
            ui._stderr_console.print_exception(show_locals=False, max_frames=10)
            sys.exit(ExitCode.SOFTWARE)

        # Unexpected core system bugs route here for the crash report payload
        ui.console.print(
            "\n[bold red]CRITICAL FAILURE:[/bold red] Protostar encountered an unexpected error."
        )

        ui.console.print_exception(show_locals=False, max_frames=10)

        # Cap the traceback to 10 frames to avoid exceeding URL length limits
        tb_str = "".join(
            traceback.format_exception(type(e), e, e.__traceback__, limit=10)
        )
        issue_body = (
            "### Environment\n"
            f"- **OS**: {platform.system()} {platform.release()}\n"
            f"- **Python**: {sys.version.split()[0]}\n"
            f"- **Command**: `{' '.join(sys.argv)}`\n\n"
            "### Traceback\n"
            f"```python\n{tb_str}\n```\n"
        )
        encoded_body = urllib.parse.quote(issue_body)
        issue_url = f"https://github.com/jacksonfergusondev/protostar/issues/new?title=Crash+Report&body={encoded_body}"

        ui.console.print(
            "\nThis looks like a bug. Please help us fix it by submitting an issue with your system details:"
        )
        ui.console.print(
            f"[bold cyan][link={issue_url}]Click here to open a GitHub issue with pre-filled crash details[/link][/bold cyan]"
        )

        sys.exit(ExitCode.SOFTWARE)  # 70: Internal software malfunction code


def __getattr__(name: str) -> Any:
    """Lazy evaluation for heavy CLI dependencies."""
    if name == "Orchestrator":
        from protostar.orchestrator import Orchestrator

        globals()["Orchestrator"] = Orchestrator
        return Orchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
