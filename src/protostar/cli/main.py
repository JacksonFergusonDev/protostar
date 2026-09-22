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
from typing import TYPE_CHECKING, Any, cast

from rich.columns import Columns

if TYPE_CHECKING:
    from protostar.orchestrator import Orchestrator
from rich.console import Group
from rich.logging import RichHandler
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from protostar.cli import parser, schema, ui
from protostar.cli.docs_links import format_docs_link
from protostar.cli.prompts import confirm
from protostar.cli.wizard import resolve_missing_variables
from protostar.config import (
    DEFAULT_CONFIG_CONTENT,
    TemplateBlueprint,
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
    WorkspaceCollisionError,
)
from protostar.fs import atomic_write_text
from protostar.intent import TemplateOrigin
from protostar.manifest import ProjectMetadata
from protostar.metadata import resolve_auto_metadata
from protostar.models import InitRequest
from protostar.modules import (
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    SystemWorkspaceModule,
)

logger = logging.getLogger("protostar")


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments."""
    if getattr(args, "list_templates", False):
        ui._print_templates_and_exit()

    override_target = getattr(args, "from_path", None)
    template_name = getattr(args, "template_name", None)
    template_context = getattr(args, "template_context", {})

    from dataclasses import replace
    from pathlib import Path

    from protostar.recipe import RecipeIntent, Tool, establish_recipe, read_recipe

    user_config = UserConfig.load()
    existing_recipe = read_recipe(Path("pyproject.toml"))
    bindings = dict(existing_recipe.bindings) if existing_recipe else {}
    for binding in getattr(args, "bind", []):
        variable, separator, environment = binding.partition("=")
        if not separator:
            raise ConfigurationError(
                "Invalid environment binding.", hint="Use --bind VARIABLE=ENVIRONMENT."
            )
        bindings[variable] = environment
    # Validate binding names before touching environment values.
    binding_recipe = establish_recipe(user_config)
    from protostar.recipe import decode_recipe

    decode_recipe(
        replace(binding_recipe, bindings=tuple(sorted(bindings.items()))).to_dict()
    )
    for variable, environment in bindings.items():
        if environment not in os.environ:
            raise ConfigurationError(
                f"Missing environment binding for {variable}.",
                hint=f"Set environment variable {environment}.",
            )
        template_context[variable] = os.environ[environment]
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

    blueprint = None
    built_in = (
        matched_info.alias
        if template_name and matched_info and not is_external
        else None
    )

    def resolve_bound_variables(missing: list[str]) -> dict[str, str]:
        if getattr(args, "dry_run", False):
            return resolve_missing_variables(missing)
        raise ConfigurationError(
            "Custom interpolation requires environment bindings.",
            hint="Provide --bind VARIABLE=ENVIRONMENT for every custom template variable.",
        )

    if not override_target and existing_recipe and existing_recipe.source:
        blueprint = existing_recipe.source.load(
            Path.cwd(), existing_recipe.rendering_context()
        )
        is_external = existing_recipe.source.origin is not TemplateOrigin.BUILT_IN
        is_trusted = not is_external
    elif override_target:
        blueprint = TemplateBlueprint.load(
            override_target,
            template_context=template_context,
            variable_resolver=resolve_bound_variables,
            built_in=built_in,
            display_name=template_name,
        )

    modules: list[BootstrapModule] = []

    # 1. Universal System Layer
    modules.append(SystemWorkspaceModule())

    # 2. Mandatory Python Core
    python_core = PythonCore(
        python_version=getattr(args, "python_version", None)
        or user_config.python_version,
    )
    modules.append(python_core)

    overrides = dict(existing_recipe.tools) if existing_recipe else {}
    for mod in TOOLING_MODULES:
        cli_override = getattr(args, mod.__class__.__name__, None)
        if cli_override is not None:
            overrides[Tool(mod.config_key)] = cli_override
    fallback = (
        dict(existing_recipe.fallback)
        if existing_recipe
        else {tool: bool(getattr(user_config, tool)) for tool in Tool}
    )
    selection_recipe = establish_recipe(
        user_config, RecipeIntent(reference=blueprint.reference if blueprint else None)
    )
    selection_recipe = replace(
        selection_recipe,
        tools=tuple(sorted(overrides.items())),
        fallback=tuple(sorted(fallback.items())),
    )
    from protostar.recipe import select_tooling

    opinions = blueprint.tooling_overrides if blueprint else {}
    modules.extend(select_tooling(selection_recipe, opinions))

    # Validate mutually exclusive tooling modules
    active_tooling_names = [type(mod).__name__ for mod in modules]
    if (
        "PreCommitModule" in active_tooling_names
        and "PrekModule" in active_tooling_names
    ):
        raise ConfigurationError(
            "Cannot use both '--pre-commit' and '--prek' simultaneously. "
            "Please choose one git hook manager."
        )

    if (
        "ReadTheDocsModule" in active_tooling_names
        and "ZensicalModule" not in active_tooling_names
    ):
        raise ConfigurationError(
            "Cannot scaffold Read the Docs without the Zensical module enabled. "
            "Please enable '--zensical' or configure 'zensical = true'."
        )

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

    required_keys: set[str] = set()
    for mod in modules:
        required_keys.update(mod.required_metadata)

    resolved_metadata = (
        {k: list(v) if isinstance(v, tuple) else v for k, v in existing_recipe.metadata}
        if existing_recipe
        else resolve_auto_metadata(required_keys, config=user_config)
    )
    if "license" in resolved_metadata:
        python_core.license = str(resolved_metadata["license"])

    # Precedence mirrors tooling flags: explicit flag > captured recipe > template.
    template_docker = (
        blueprint.tooling_overrides.get("docker", False) if blueprint else False
    )
    docker = (
        args.docker
        if args.docker is not None
        else (existing_recipe.docker if existing_recipe else template_docker)
    )
    recipe = establish_recipe(
        user_config,
        RecipeIntent(
            blueprint.reference if blueprint else None,
            cast(ProjectMetadata, resolved_metadata),
            docker,
            getattr(args, "python_version", None),
        ),
    )
    from protostar.recipe import decode_recipe

    recipe = replace(
        recipe,
        tools=tuple(sorted(overrides.items())),
        fallback=tuple(sorted(fallback.items())),
        bindings=tuple(sorted(bindings.items())),
        context=existing_recipe.context if existing_recipe else recipe.context,
    )
    if getattr(args, "python_version", None):
        context = dict(recipe.context)
        context["PYTHON_VERSION"] = args.python_version
        recipe = replace(recipe, context=tuple(sorted(context.items())))
    recipe = decode_recipe(recipe.to_dict())

    # Custom answers must have replayable bindings; never persist their values.
    custom = set(template_context) - set(dict(recipe.context))
    if not custom <= set(bindings) and not getattr(args, "dry_run", False):
        raise ConfigurationError(
            "Custom interpolation requires environment bindings.",
            hint="Use --bind VARIABLE=ENVIRONMENT instead of persisting interpolation answers.",
        )
    request = InitRequest(
        recipe=recipe,
        python_version=recipe.python,
        template_blueprint=blueprint,
        template_reference=blueprint.reference if blueprint else None,
        docker=docker,
        force_merge=getattr(args, "force_merge", False),
        force_replace=getattr(args, "force_replace", False),
        metadata=resolved_metadata,
        is_external=is_external,
        is_user_aliased=is_user_aliased,
        is_trusted=is_trusted,
    )
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
                }
            )
        else:
            ui.print_dry_run_summary(manifest)
        sys.exit(0)

    result = ui._run_engine(engine, request)
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
            confirmed = confirm(
                "Warning: this will erase your current configuration, are you sure you want to do this?",
                default=False,
            )
            if confirmed is None:
                raise ExecutionAbortedError("Configuration reset aborted.")
            if not confirmed:
                ui.console.print("[yellow]Configuration reset aborted.[/yellow]")
                return

        logger.debug(
            "Resetting configuration file at %s to default template", config_path
        )
        atomic_write_text(config_path, DEFAULT_CONFIG_CONTENT)
        ui.console.print(
            f"[bold green]Reset configuration at {config_path} to default state.[/bold green]"
        )
        return

    if not config_path.exists():
        logger.debug("Writing initial default configuration to %s", config_path)
        atomic_write_text(config_path, DEFAULT_CONFIG_CONTENT)
        ui.console.print(
            f"[bold green]Initialized default configuration at {config_path}[/bold green]"
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


def _parse_dynamic_kwargs(unknown_args: list[str]) -> dict[str, str]:
    """Parses trailing unknown CLI arguments into a variable dictionary.

    Args:
        unknown_args: The trailing list of arguments rejected by the main parser.

    Returns:
        A dictionary mapping the dynamic flag names to their values.

    Raises:
        ConfigurationError: If positional (non-flag) arguments are encountered.
    """
    kwargs = {}
    i = 0
    while i < len(unknown_args):
        arg = unknown_args[i]
        if arg.startswith("--"):
            key = arg.lstrip("-")
            if "=" in key:
                k, v = key.split("=", 1)
                kwargs[k] = v
            else:
                if i + 1 < len(unknown_args) and not unknown_args[i + 1].startswith(
                    "--"
                ):
                    kwargs[key] = unknown_args[i + 1]
                    i += 1
                else:
                    kwargs[key] = ""
        else:
            raise ConfigurationError(
                f"Unrecognized positional argument for interpolation: {arg}"
            )
        i += 1
    return kwargs


def main() -> None:
    """Main execution pipeline for the Protostar CLI."""
    ui.replace_unencodable_output()
    ui.is_json_mode = ui.is_json_mode or ("--json" in sys.argv)

    arg_parser = parser.build_parser()
    parser._dispatch_preparser_flags(arg_parser)

    try:
        parser.intercept_interactive_wizards(arg_parser)
        args, unknown = arg_parser.parse_known_args()

        if unknown and (
            getattr(args, "command", None) != "init"
            or not getattr(args, "from_path", None)
        ):
            raise InvalidUsageError(
                f"Unrecognized arguments: {' '.join(unknown)}",
                docs_path=parser._resolve_usage_doc_path(),
            )

        args.template_context = _parse_dynamic_kwargs(unknown)

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
            if isinstance(e, WorkspaceCollisionError):
                error_dict["paths"] = sorted(str(p) for p in e.paths)
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
            # the panel body so literal '[templates]' survives Rich rendering.
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
                            desc = (
                                t.command[0] if not t.command else " ".join(t.command)
                            )
                            rb_group.append(
                                Text.from_markup(f"[dim]• [Completed]   {desc}[/dim]")
                            )
                        if ctx.interrupted_task:
                            t = ctx.interrupted_task
                            desc = (
                                t.command[0] if not t.command else " ".join(t.command)
                            )
                            rb_group.append(
                                Text.from_markup(f"[dim]• [Interrupted] {desc}[/dim]")
                            )
                else:
                    rb_group.append(
                        Text.from_markup(
                            "Note: Some standard artifacts (like the .venv/ directory) remain but are safe to ignore."
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

            panel_title = (
                "[bold red]Execution Interrupted"
                if isinstance(e, ExecutionInterruptedError)
                else "[bold red]Execution Aborted"
            )
            ui.console.print(
                Panel(
                    body_renderable,
                    title=panel_title,
                    border_style="red",
                    expand=False,
                    padding=(1, 2),
                )
            )

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
