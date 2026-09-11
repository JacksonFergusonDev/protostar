import argparse
import os
import sys
from dataclasses import dataclass
from enum import StrEnum

from rich import box
from rich.panel import Panel

from protostar.cli import schema, ui


class Shell(StrEnum):
    """Supported shells for CLI autocompletion."""

    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"


@dataclass(frozen=True)
class ShellEnvironment:
    """Represents a detected shell and its associated platform configuration."""

    shell: Shell
    os_name: str
    profile_path: str
    eval_hook: str
    quick_setup_cmd: str
    description: str


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


def get_available_templates() -> dict[str, str]:
    """Discovers built-in templates and user config aliases with descriptions.

    Returns:
        A dictionary mapping template names to human-readable descriptions.
    """
    import importlib.resources

    from protostar.config import UserConfig

    descriptions: dict[str, str] = {
        "api": "FastAPI web application scaffold",
        "astro": "Astro web framework integration",
        "cli": "Rich & Typer command-line application",
        "dsp": "Digital signal processing scaffold",
        "embedded": "Embedded Python development setup",
        "ml": "Machine learning & data science scaffold",
    }

    templates: dict[str, str] = {}
    try:
        template_dir = importlib.resources.files("protostar.templates")
        for item in sorted(template_dir.iterdir(), key=lambda x: x.name):
            if item.is_file() and item.name.endswith(".toml"):
                name = item.name[:-5]
                templates[name] = descriptions.get(name, "Built-in template")
    except (OSError, TypeError, ValueError, AttributeError, ModuleNotFoundError):
        pass

    try:
        user_config = UserConfig.load()
        for alias, source in user_config.templates.items():
            templates[alias] = f"Global alias ({source})"
    except (OSError, TypeError, ValueError, KeyError, AttributeError):
        pass

    return templates


def template_completer(prefix: str, **kwargs: object) -> dict[str, str]:
    """Completer for the '--template' flag matching built-in templates and user aliases."""
    return {
        name: desc
        for name, desc in get_available_templates().items()
        if name.startswith(prefix)
    }


def detect_environment() -> ShellEnvironment:
    """Inspects system platform and environment variables to detect the active shell.

    Returns:
        A ShellEnvironment dataclass populated with shell metadata and instructions.
    """
    is_windows = sys.platform == "win32"
    is_macos = sys.platform == "darwin"
    os_display = "Windows" if is_windows else ("macOS" if is_macos else "Linux")

    shell: Shell
    if "ZSH_VERSION" in os.environ:
        shell = Shell.ZSH
    elif "BASH_VERSION" in os.environ:
        shell = Shell.BASH
    elif "FISH_VERSION" in os.environ:
        shell = Shell.FISH
    else:
        raw_shell = os.environ.get("SHELL", "").lower()
        if "zsh" in raw_shell:
            shell = Shell.ZSH
        elif "bash" in raw_shell:
            shell = Shell.BASH
        elif "fish" in raw_shell:
            shell = Shell.FISH
        elif is_windows:
            shell = Shell.POWERSHELL
        elif is_macos:
            shell = Shell.ZSH
        else:
            shell = Shell.BASH

    if shell == Shell.ZSH:
        return ShellEnvironment(
            shell=Shell.ZSH,
            os_name=os_display,
            profile_path="~/.zshrc",
            eval_hook='eval "$(protostar completion zsh)"',
            quick_setup_cmd="echo 'eval \"$(protostar completion zsh)\"' >> ~/.zshrc && source ~/.zshrc",
            description=f"{os_display} (Zsh)",
        )
    if shell == Shell.BASH:
        profile = "~/.bash_profile" if is_macos else "~/.bashrc"
        return ShellEnvironment(
            shell=Shell.BASH,
            os_name=os_display,
            profile_path=profile,
            eval_hook='eval "$(protostar completion bash)"',
            quick_setup_cmd=f"echo 'eval \"$(protostar completion bash)\"' >> {profile} && source {profile}",
            description=f"{os_display} (Bash)",
        )
    if shell == Shell.FISH:
        return ShellEnvironment(
            shell=Shell.FISH,
            os_name=os_display,
            profile_path="~/.config/fish/config.fish",
            eval_hook="protostar completion fish | source",
            quick_setup_cmd="protostar completion fish > ~/.config/fish/completions/protostar.fish",
            description=f"{os_display} (Fish)",
        )
    # Shell.POWERSHELL
    return ShellEnvironment(
        shell=Shell.POWERSHELL,
        os_name=os_display,
        profile_path="$PROFILE",
        eval_hook="protostar completion powershell | Out-String | Invoke-Expression",
        quick_setup_cmd="Add-Content -Path $PROFILE -Value 'protostar completion powershell | Out-String | Invoke-Expression'",
        description=f"{os_display} (PowerShell)",
    )


def print_completion_guide() -> None:
    """Displays user-friendly terminal instructions tailored to the detected shell."""
    env = detect_environment()

    if env.shell == Shell.POWERSHELL:
        pwsh_setup = (
            "  [bold cyan]1. Create profile if it does not exist:[/bold cyan]\n"
            "     [green]if (!(Test-Path -Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force }[/green]\n\n"
            "  [bold cyan]2. Append completion hook to profile:[/bold cyan]\n"
            "     [green]Add-Content -Path $PROFILE -Value 'protostar completion powershell | Out-String | Invoke-Expression'[/green]\n\n"
            "  [bold cyan]3. Reload profile in current session:[/bold cyan]\n"
            "     [green]. $PROFILE[/green]"
        )
        body = (
            f"[bold green]✓ Detected Environment: {env.description}[/bold green]\n\n"
            "[bold]Recommended Setup (Run in PowerShell):[/bold]\n"
            f"{pwsh_setup}\n\n"
            "[dim]Manual Configuration:[/dim]\n"
            f"  Add this line to [cyan]{env.profile_path}[/cyan]:\n"
            f"    [yellow]{env.eval_hook}[/yellow]"
        )
    else:
        body = (
            f"[bold green]✓ Detected Environment: {env.description}[/bold green]\n\n"
            "[bold]Recommended One-Liner (Run to enable and reload):[/bold]\n"
            f"  [green]{env.quick_setup_cmd}[/green]\n\n"
            "[dim]Manual Configuration:[/dim]\n"
            f"  Add this line to [cyan]{env.profile_path}[/cyan]:\n"
            f"    [yellow]{env.eval_hook}[/yellow]"
        )

    other_shells = [s for s in Shell if s != env.shell]
    other_lines: list[str] = []
    for s in other_shells:
        if s == Shell.ZSH:
            other_lines.append(
                "  • [bold]Zsh[/bold] [dim](~/.zshrc)[/dim]:\n"
                '    [dim]eval "$(protostar completion zsh)"[/dim]'
            )
        elif s == Shell.BASH:
            other_lines.append(
                "  • [bold]Bash[/bold] [dim](~/.bashrc)[/dim]:\n"
                '    [dim]eval "$(protostar completion bash)"[/dim]'
            )
        elif s == Shell.FISH:
            other_lines.append(
                "  • [bold]Fish[/bold] [dim](~/.config/fish/config.fish)[/dim]:\n"
                "    [dim]protostar completion fish | source[/dim]"
            )
        elif s == Shell.POWERSHELL:
            other_lines.append(
                "  • [bold]PowerShell[/bold] [dim]($PROFILE)[/dim]:\n"
                "    [dim]protostar completion powershell | Out-String | Invoke-Expression[/dim]"
            )

    body += (
        "\n\n[dim]──────────────────────────────────────────────────────────────────────[/dim]\n"
        "[bold]Other Supported Shells:[/bold]\n" + "\n".join(other_lines)
    )

    ui.console.print(
        Panel(
            body,
            title="[bold blue]Shell Autocompletion Setup[/bold blue]",
            box=box.ROUNDED,
            border_style="cyan",
            padding=(1, 2),
        )
    )
    ui.console.print(
        "[dim]Run [bold]protostar completion <shell>[/bold] to generate raw completion scripts.[/dim]\n"
    )


def handle_completion(args: argparse.Namespace) -> None:
    """Handles the 'completion' CLI subcommand.

    Args:
        args: Parsed command-line arguments containing the optional target shell.
    """
    target_shell: str | None = getattr(args, "shell", None)

    if not target_shell:
        env = detect_environment()
        if ui.is_json_mode:
            ui.emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "success",
                    "detected_os": env.os_name.lower(),
                    "detected_shell": env.shell.value,
                    "recommended_profile": env.profile_path,
                    "recommended_hook": env.eval_hook,
                    "quick_setup_command": env.quick_setup_cmd,
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
