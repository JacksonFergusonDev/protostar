import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from protostar.cli import schema, ui
from protostar.cli.completion import (
    Shell,
    generate_completion_script,
    get_available_templates,
    template_completer,
)
from protostar.cli.parser import build_parser
from protostar.config import UserConfig


def test_generate_completion_script_supported_shells() -> None:
    """Verify script generation for all supported shell environments."""
    for shell in Shell:
        script = generate_completion_script(shell)
        assert isinstance(script, str)
        assert len(script) > 0
        assert "protostar" in script

    # Verify shell-specific syntax markers
    bash_script = generate_completion_script(Shell.BASH)
    assert "_python_argcomplete" in bash_script or "complete" in bash_script

    zsh_script = generate_completion_script(Shell.ZSH)
    assert "#compdef protostar" in zsh_script
    assert "compdef" in zsh_script

    fish_script = generate_completion_script(Shell.FISH)
    assert "fish" in fish_script.lower()

    pwsh_script = generate_completion_script(Shell.POWERSHELL)
    assert "Register-ArgumentCompleter" in pwsh_script
    assert "ARGCOMPLETE_USE_TEMPFILES" in pwsh_script


def test_generate_completion_script_custom_executable() -> None:
    """Verify script generation works with custom executable aliases like 'proto'."""
    script = generate_completion_script(Shell.ZSH, executable="proto")
    assert "#compdef proto" in script
    assert "compdef _python_argcomplete proto" in script


def test_completion_subcommand_outputs_script(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that 'protostar completion <shell>' outputs raw completion code to stdout."""
    parser = build_parser()
    for shell in Shell:
        args = parser.parse_args(["completion", shell.value])
        args.func(args)
        captured = capsys.readouterr()
        assert "protostar" in captured.out
        assert captured.err == ""


def test_completion_subcommand_guide(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that 'protostar completion' without arguments outputs the interactive setup guide."""
    parser = build_parser()
    args = parser.parse_args(["completion"])
    args.func(args)
    captured = capsys.readouterr()
    assert "Detected Environment:" in captured.out
    assert "Recommended One-Liner" in captured.out
    assert "Manual Steps:" in captured.out
    assert "Using a different shell?" in captured.out
    assert "Shell Autocompletion Setup" not in captured.out


def test_completion_subcommand_json_mode(mocker: Any) -> None:
    """Test structured JSON emission for single shell and shell listing."""
    emit_mock = mocker.patch("protostar.cli.ui.emit_json")
    mocker.patch("sys.exit")

    ui.is_json_mode = True
    try:
        parser = build_parser()

        # 1. Single shell mode
        args = parser.parse_args(["completion", "zsh"])
        args.func(args)
        emit_mock.assert_called_once()
        payload = emit_mock.call_args[0][0]
        assert payload["api_version"] == schema.CLI_API_VERSION
        assert payload["status"] == "success"
        assert payload["shell"] == "zsh"
        assert "protostar" in payload["script"]

        emit_mock.reset_mock()

        # 2. Bare completion command (listing supported shells with detection)
        args_bare = parser.parse_args(["completion"])
        args_bare.func(args_bare)
        emit_mock.assert_called_once()
        bare_payload = emit_mock.call_args[0][0]
        assert bare_payload["status"] == "success"
        assert "detected_os" in bare_payload
        assert "detected_shell" in bare_payload
        assert "recommended_profile" in bare_payload
        assert "completion_file" in bare_payload
        assert "recommended_hook" in bare_payload
        assert "quick_setup_command" in bare_payload
        assert bare_payload["supported_shells"] == [s.value for s in Shell]
    finally:
        ui.is_json_mode = False


def test_detect_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test environment detection heuristics across different shells and operating systems."""
    from protostar.cli.completion import detect_environment

    # 1. Explicit ZSH_VERSION
    monkeypatch.setenv("ZSH_VERSION", "5.9")
    monkeypatch.delenv("BASH_VERSION", raising=False)
    monkeypatch.delenv("FISH_VERSION", raising=False)
    env_zsh = detect_environment()
    assert env_zsh.shell == Shell.ZSH
    assert env_zsh.profile_path == "~/.zshrc"
    assert env_zsh.completion_file == "~/.protostar-completion.zsh"

    # 2. Explicit BASH_VERSION on Linux
    monkeypatch.delenv("ZSH_VERSION", raising=False)
    monkeypatch.setenv("BASH_VERSION", "5.2")
    monkeypatch.setattr("sys.platform", "linux")
    env_bash = detect_environment()
    assert env_bash.shell == Shell.BASH
    assert env_bash.profile_path == "~/.bashrc"
    assert env_bash.completion_file == "~/.protostar-completion.bash"

    # 3. Explicit FISH_VERSION
    monkeypatch.delenv("BASH_VERSION", raising=False)
    monkeypatch.setenv("FISH_VERSION", "3.6.1")
    env_fish = detect_environment()
    assert env_fish.shell == Shell.FISH
    assert env_fish.profile_path == "~/.config/fish/config.fish"
    assert env_fish.completion_file == "~/.config/fish/completions/protostar.fish"

    # 4. Windows default fallback
    monkeypatch.delenv("FISH_VERSION", raising=False)
    monkeypatch.delenv("SHELL", raising=False)
    monkeypatch.setattr("sys.platform", "win32")
    env_win = detect_environment()
    assert env_win.shell == Shell.POWERSHELL
    assert env_win.profile_path == "$PROFILE"
    assert "protostar-completion.ps1" in env_win.completion_file
    assert "Add-Content" in env_win.quick_setup_cmd


def test_template_completer(mocker: Any) -> None:
    """Test dynamic template discovery and filtering logic."""
    templates = get_available_templates()
    assert "cli" in templates
    assert "astro" in templates
    assert "api" in templates

    # Prefix filtering
    res = template_completer("as")
    assert "astro" in res
    assert "cli" not in res

    # Global alias support via UserConfig
    from protostar.config import TemplateAliasConfig

    fake_config = UserConfig(
        templates={
            "my-custom-stack": TemplateAliasConfig(source="git@github.com:foo/bar")
        }
    )
    mocker.patch("protostar.config.UserConfig.load", return_value=fake_config)

    alias_res = template_completer("my")
    assert "my-custom-stack" in alias_res
    assert "Global alias (git@github.com:foo/bar)" in alias_res["my-custom-stack"]


def test_template_completer_resilience(mocker: Any) -> None:
    """Verify template completer gracefully handles missing directories and invalid configs."""
    mocker.patch(
        "importlib.resources.files",
        side_effect=OSError("Resource error"),
    )
    mocker.patch(
        "protostar.config.UserConfig.load",
        side_effect=ValueError("Bad config"),
    )

    templates = get_available_templates()
    assert templates == {}
    assert template_completer("cli") == {}


def test_parser_action_completers() -> None:
    """Verify that custom completers are properly bound to CLI parser actions."""
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    init_parser = subparsers_action.choices["init"]

    template_action = next(
        a for a in init_parser._actions if "--template" in a.option_strings
    )
    assert hasattr(template_action, "completer")
    assert callable(template_action.completer)

    from_action = next(a for a in init_parser._actions if "--from" in a.option_strings)
    assert hasattr(from_action, "completer")

    python_version_action = next(
        a for a in init_parser._actions if "--python-version" in a.option_strings
    )
    assert hasattr(python_version_action, "completer")


def test_powershell_tempfile_completion_protocol(tmp_path: Path) -> None:
    """End-to-end simulation of Windows PowerShell completion protocol via tempfile IPC."""
    completion_file = tmp_path / "completion.out"
    completion_file.touch()

    env = os.environ.copy()
    env["_ARGCOMPLETE"] = "1"
    env["ARGCOMPLETE_USE_TEMPFILES"] = "1"
    env["_ARGCOMPLETE_STDOUT_FILENAME"] = str(completion_file)
    env["_ARGCOMPLETE_SHELL"] = "powershell"
    env["_ARGCOMPLETE_IFS"] = "\n"
    env["COMP_LINE"] = "protostar init --template a"
    env["COMP_POINT"] = str(len(env["COMP_LINE"]))

    proc = subprocess.run(
        [sys.executable, "-m", "protostar.cli"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    content = completion_file.read_text().splitlines()
    assert "api" in content
    assert "astro" in content
    assert "cli" not in content


def test_powershell_tempfile_python_version_completion(tmp_path: Path) -> None:
    """End-to-end simulation of PowerShell completion for '--python-version' choices."""
    completion_file = tmp_path / "completion.out"
    completion_file.touch()

    env = os.environ.copy()
    env["_ARGCOMPLETE"] = "1"
    env["ARGCOMPLETE_USE_TEMPFILES"] = "1"
    env["_ARGCOMPLETE_STDOUT_FILENAME"] = str(completion_file)
    env["_ARGCOMPLETE_SHELL"] = "powershell"
    env["_ARGCOMPLETE_IFS"] = "\n"
    env["COMP_LINE"] = "protostar init --python-version 3."
    env["COMP_POINT"] = str(len(env["COMP_LINE"]))

    proc = subprocess.run(
        [sys.executable, "-m", "protostar.cli"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    content = completion_file.read_text().splitlines()
    assert "3.12" in content
    assert "3.13" in content
    assert "3.14" in content


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX fd 8 protocol is Unix-specific"
)
def test_posix_fd8_completion_protocol() -> None:
    """End-to-end simulation of POSIX (Bash/Zsh) completion protocol streaming over fd 8."""
    env = os.environ.copy()
    env["_ARGCOMPLETE"] = "1"
    env["COMP_LINE"] = "protostar init --template a"
    env["COMP_POINT"] = str(len(env["COMP_LINE"]))

    cmd = f'"{sys.executable}" -m protostar.cli 8>&1'
    proc = subprocess.run(
        cmd,
        shell=True,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0

    # Argcomplete joins POSIX completions with \x0b (vertical tab)
    output = proc.stdout
    assert "api" in output
    assert "astro" in output
    assert "cli" not in output
