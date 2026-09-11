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
from typing import Any

from rich.logging import RichHandler
from rich.panel import Panel

from protostar.cli import parser, schema, ui
from protostar.config import (
    CONFIG_FILE,
    DEFAULT_CONFIG_CONTENT,
    TemplateBlueprint,
    UserConfig,
)
from protostar.errors import (
    AggregatedDependencyError,
    CommandExecutionError,
    ConfigurationError,
    ExecutionAbortedError,
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
from protostar.metadata import resolve_auto_metadata
from protostar.models import InitRequest
from protostar.modules import (
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    SystemWorkspaceModule,
)
from protostar.orchestrator import Orchestrator
from protostar.ui import confirm
from protostar.wizard import resolve_missing_variables


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments."""
    if getattr(args, "list_templates", False):
        ui._print_templates_and_exit()

    override_target = getattr(args, "from_path", None)
    template_name = getattr(args, "template_name", None)
    template_context = getattr(args, "template_context", {})

    user_config = UserConfig.load()
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

    if override_target:
        blueprint = TemplateBlueprint.load(
            override_target,
            template_context=template_context,
            variable_resolver=resolve_missing_variables,
        )

    modules: list[BootstrapModule] = []

    # 1. Universal System Layer
    modules.append(SystemWorkspaceModule())

    # 2. Mandatory Python Core
    python_core = PythonCore(
        python_version=getattr(args, "python_version", None),
    )
    modules.append(python_core)

    # 3. Tooling Layers
    for mod in TOOLING_MODULES:
        # 3. Lowest priority: User's global defaults
        is_active = getattr(user_config, mod.config_key, False)

        # 2. Medium priority: Template author's explicit overrides
        if blueprint and mod.config_key in blueprint.tooling_overrides:
            is_active = blueprint.tooling_overrides[mod.config_key]

        # 1. Highest priority: User's CLI flags for this specific run
        if mod.cli_flags:
            cli_override = getattr(args, mod.__class__.__name__, None)
            if cli_override is not None:
                is_active = cli_override

        if is_active:
            modules.append(mod)

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

    resolved_metadata = resolve_auto_metadata(required_keys)

    request = InitRequest(
        template_blueprint=blueprint,
        docker=args.docker,
        force_merge=getattr(args, "force_merge", False),
        force_replace=getattr(args, "force_replace", False),
        metadata=resolved_metadata,
        is_external=is_external,
        is_user_aliased=is_user_aliased,
        is_trusted=is_trusted,
    )
    engine = Orchestrator(modules, user_config, request=request)

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
            ui._print_dry_run_summary(manifest)
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
    if not CONFIG_FILE.parent.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if getattr(args, "reset", False):
        if not getattr(args, "force_merge", False) and not getattr(
            args, "force_replace", False
        ):
            confirmed = confirm(
                "Warning: this will erase your current configuration, are you sure you want to do this?",
                default=False,
            )
            if confirmed is None:
                raise ExecutionAbortedError("Configuration reset aborted.")
            if not confirmed:
                ui.console.print("[yellow]Configuration reset aborted.[/yellow]")
                return

        atomic_write_text(CONFIG_FILE, DEFAULT_CONFIG_CONTENT)
        ui.console.print(
            f"[bold green]Reset configuration at {CONFIG_FILE} to default state.[/bold green]"
        )
        return

    if not CONFIG_FILE.exists():
        atomic_write_text(CONFIG_FILE, DEFAULT_CONFIG_CONTENT)
        ui.console.print(
            f"[bold green]Initialized default configuration at {CONFIG_FILE}[/bold green]"
        )

    editor_env = os.environ.get("EDITOR", "nano")
    editor_cmd = shlex.split(editor_env)

    if not editor_cmd:
        raise ConfigurationError("The $EDITOR environment variable is empty.")

    if not shutil.which(editor_cmd[0]):
        raise ConfigurationError(
            f"Could not resolve editor executable '{editor_cmd[0]}'.\n"
            "Ensure your $EDITOR environment variable is set to a valid binary in your PATH."
        )

    editor_cmd.append(str(CONFIG_FILE))

    try:
        subprocess.run(editor_cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise ConfigurationError(
            f"Editor '{editor_env}' exited with non-zero status: {e}"
        ) from e


def configure_logging() -> None:
    """Injects Rich tracebacks and debug handlers into the global logger.

    In JSON mode, the handler writes to ``stderr`` to preserve ``stdout`` for
    the exclusive use of machine-readable JSON payloads.
    """
    log_console = ui._stderr_console if ui.is_json_mode else ui.console
    logger = logging.getLogger("protostar")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(
        RichHandler(console=log_console, markup=True, rich_tracebacks=True)
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
            if e.docs_url:
                error_dict["docs_url"] = e.docs_url
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

            body = str(e)
            if isinstance(e, CommandExecutionError) and e.output_detail:
                body += f"\n\n[dim]{e.output_detail}[/dim]"
            if e.hint:
                body += f"\n\n[dim]Hint: {e.hint}[/dim]"
            if e.docs_url:
                body += f"\n\n[bold cyan][link={e.docs_url}]Read the documentation ↗[/link][/bold cyan]"

            ui.console.print(
                Panel(
                    body,
                    title="[bold red]Execution Aborted",
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
        if isinstance(e, ExecutionAbortedError):
            sys.exit(130)  # User aborted via interactive prompt

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
            "\nThis looks like a bug. Please help us fix it by submitting an issue with your telemetry:"
        )
        ui.console.print(
            f"[bold cyan][link={issue_url}]Click here to open a GitHub issue with your telemetry[/link][/bold cyan]"
        )

        sys.exit(ExitCode.SOFTWARE)  # 70: Internal software malfunction code
