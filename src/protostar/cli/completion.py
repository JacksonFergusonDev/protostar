import argparse
import sys
from enum import StrEnum

from rich import box
from rich.panel import Panel
from rich.table import Table

from protostar.cli import schema, ui


class Shell(StrEnum):
    """Supported shells for CLI autocompletion."""

    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"


def generate_completion_script(shell: Shell, executable: str = "protostar") -> str:
    """Generates shell completion code for the specified shell using argcomplete.

    Args:
        shell: The target shell environment.
        executable: The name of the executable command to complete.

    Returns:
        The raw shell script string suitable for eval or sourcing.
    """
    import argcomplete.shell_integration as si

    return si.shellcode([executable], shell=shell.value)


def print_completion_guide() -> None:
    """Displays user-friendly terminal instructions for enabling autocompletion."""
    ui.console.print(
        Panel(
            "[bold cyan]Protostar Shell Autocompletion Setup[/bold cyan]\n\n"
            "Add the one-liner for your shell to your configuration file to enable dynamic tab completion.",
            box=box.ROUNDED,
            border_style="cyan",
            padding=(1, 2),
        )
    )

    table = Table(
        box=box.ROUNDED,
        title="Shell Integration Commands",
        title_style="bold blue",
        title_justify="left",
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("Shell", style="cyan", no_wrap=True)
    table.add_column("Configuration File", style="yellow", no_wrap=True)
    table.add_column("One-Liner Hook", style="green", no_wrap=True)

    table.add_row(
        "Zsh\n(macOS / Linux)",
        "~/.zshrc",
        'eval "$(protostar completion zsh)"',
    )
    table.add_row(
        "Bash\n(Linux / macOS)",
        "~/.bashrc",
        'eval "$(protostar completion bash)"',
    )
    table.add_row(
        "Fish\n(macOS / Linux)",
        "~/.config/fish/config.fish",
        "protostar completion fish | source",
    )
    table.add_row(
        "PowerShell\n(Windows / Cross-platform)",
        "$PROFILE",
        "protostar completion powershell | Out-String | Invoke-Expression",
    )

    ui.console.print(table)
    ui.console.print(
        "\n[dim]Run [bold]protostar completion <shell>[/bold] to output the raw shell script.[/dim]\n"
    )


def handle_completion(args: argparse.Namespace) -> None:
    """Handles the 'completion' CLI subcommand.

    Args:
        args: Parsed command-line arguments containing the optional target shell.
    """
    target_shell: str | None = getattr(args, "shell", None)

    if not target_shell:
        if ui.is_json_mode:
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "success",
                    "supported_shells": [s.value for s in Shell],
                }
            )
            sys.exit(0)
        print_completion_guide()
        return

    shell_enum = Shell(target_shell)
    script = generate_completion_script(shell_enum)

    if ui.is_json_mode:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "shell": shell_enum.value,
                "script": script,
            }
        )
        sys.exit(0)

    # Human/shell mode: emit raw script to stdout without Rich formatting
    sys.stdout.write(script)
    if not script.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
