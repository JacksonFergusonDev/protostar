import argparse
import os
import sys
from dataclasses import dataclass
from enum import StrEnum

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
    completion_file: str
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
            completion_file="~/.protostar-completion.zsh",
            eval_hook="source ~/.protostar-completion.zsh",
            quick_setup_cmd="protostar completion zsh > ~/.protostar-completion.zsh && echo 'source ~/.protostar-completion.zsh' >> ~/.zshrc && source ~/.zshrc",
            description=f"{os_display} (Zsh)",
        )
    if shell == Shell.BASH:
        profile = "~/.bash_profile" if is_macos else "~/.bashrc"
        return ShellEnvironment(
            shell=Shell.BASH,
            os_name=os_display,
            profile_path=profile,
            completion_file="~/.protostar-completion.bash",
            eval_hook="source ~/.protostar-completion.bash",
            quick_setup_cmd=f"protostar completion bash > ~/.protostar-completion.bash && echo 'source ~/.protostar-completion.bash' >> {profile} && source {profile}",
            description=f"{os_display} (Bash)",
        )
    if shell == Shell.FISH:
        return ShellEnvironment(
            shell=Shell.FISH,
            os_name=os_display,
            profile_path="~/.config/fish/config.fish",
            completion_file="~/.config/fish/completions/protostar.fish",
            eval_hook="Built-in autoload (no config edits needed)",
            quick_setup_cmd="mkdir -p ~/.config/fish/completions && protostar completion fish > ~/.config/fish/completions/protostar.fish",
            description=f"{os_display} (Fish)",
        )
    # Shell.POWERSHELL
    return ShellEnvironment(
        shell=Shell.POWERSHELL,
        os_name=os_display,
        profile_path="$PROFILE",
        completion_file="$HOME\\protostar-completion.ps1",
        eval_hook='. "$HOME\\protostar-completion.ps1"',
        quick_setup_cmd='protostar completion powershell > "$HOME\\protostar-completion.ps1"; Add-Content -Path $PROFILE -Value \'. "$HOME\\protostar-completion.ps1"\'; . $PROFILE',
        description=f"{os_display} (PowerShell)",
    )


def print_completion_guide() -> None:
    """Displays user-friendly terminal instructions tailored to the detected shell."""
    env = detect_environment()

    ui.console.print(
        f"[bold green]✓ Detected Environment: {env.description}[/bold green]\n"
    )

    if env.shell == Shell.POWERSHELL:
        ui.console.print("[bold]Recommended One-Liner (Zero Startup Overhead):[/bold]")
        ui.console.print(f"  [cyan]{env.quick_setup_cmd}[/cyan]", soft_wrap=True)
        ui.console.print("")
        ui.console.print("[bold]Manual Steps:[/bold]")
        ui.console.print("  1. Create profile if it does not exist:")
        ui.console.print(
            "     [cyan]if (!(Test-Path -Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force }[/cyan]",
            soft_wrap=True,
        )
        ui.console.print("  2. Generate static completion script:")
        ui.console.print(
            '     [cyan]protostar completion powershell > "$HOME\\protostar-completion.ps1"[/cyan]',
            soft_wrap=True,
        )
        ui.console.print("  3. Source completion script in profile:")
        ui.console.print(
            "     [cyan]Add-Content -Path $PROFILE -Value '. \"$HOME\\protostar-completion.ps1\"'[/cyan]",
            soft_wrap=True,
        )
        ui.console.print("  4. Reload profile in current session:")
        ui.console.print("     [cyan]. $PROFILE[/cyan]\n")
    elif env.shell == Shell.FISH:
        ui.console.print(
            "[bold]Recommended Setup (Native Lazy Loading, 0ms startup overhead):[/bold]"
        )
        ui.console.print(f"  [cyan]{env.quick_setup_cmd}[/cyan]", soft_wrap=True)
        ui.console.print(
            "\n  [dim]Fish automatically loads completions from ~/.config/fish/completions on demand.[/dim]\n"
        )
    else:
        tip = ""
        if env.shell == Shell.ZSH:
            tip = (
                "\n  [dim]Tip: If you use an $fpath completions folder, you can save directly:[/dim]\n"
                "       [cyan]protostar completion zsh > ~/.zsh/completions/_protostar[/cyan]\n"
            )
        ui.console.print("[bold]Recommended One-Liner (Zero Startup Overhead):[/bold]")
        ui.console.print(f"  [cyan]{env.quick_setup_cmd}[/cyan]", soft_wrap=True)
        ui.console.print("")
        ui.console.print("[bold]Manual Steps:[/bold]")
        ui.console.print("  1. Generate static completion script:")
        ui.console.print(
            f"     [cyan]protostar completion {env.shell.value} > {env.completion_file}[/cyan]",
            soft_wrap=True,
        )
        ui.console.print(f"  2. Add to {env.profile_path}:")
        ui.console.print(
            f"     [cyan]echo '{env.eval_hook}' >> {env.profile_path}[/cyan]",
            soft_wrap=True,
        )
        ui.console.print("  3. Reload active session:")
        ui.console.print(f"     [cyan]source {env.profile_path}[/cyan]", soft_wrap=True)
        if tip:
            ui.console.print(tip)
        else:
            ui.console.print("")

    shells_list = ", ".join(s.value for s in Shell)
    ui.console.print(
        f"[dim]Using a different shell? Run [bold]protostar completion <shell>[/bold] ({shells_list}).[/dim]\n"
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
                    "completion_file": env.completion_file,
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
