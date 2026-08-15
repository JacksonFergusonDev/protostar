import argparse
import importlib.metadata
import os
import subprocess
import sys

import pytest

from protostar.cli import (
    ProtoHelpFormatter,
    _parse_dynamic_kwargs,
    build_parser,
    configure_logging,
    handle_config,
    handle_init,
    intercept_interactive_wizards,
    main,
)
from protostar.config import DEFAULT_CONFIG_CONTENT, UserConfig
from protostar.errors import (
    CommandExecutionError,
    ConfigurationError,
    ExecutionAbortedError,
    FileSystemError,
    MissingDependencyError,
)


def test_proto_help_formatter_usage(mocker):
    """Test that the custom formatter correctly overrides the usage prefix."""
    parser = argparse.ArgumentParser(formatter_class=ProtoHelpFormatter)
    parser.add_argument("--foo", help="Foo argument")

    help_output = parser.format_help()

    # Ensure the capitalized 'Usage:' prefix is applied
    assert "Usage:" in help_output
    assert "usage:" not in help_output


def test_build_parser_package_not_found(mocker):
    """Test that the parser gracefully handles missing metadata during development."""
    mocker.patch(
        "importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError,
    )
    # Just checking it doesn't crash during construction
    parser = build_parser()
    assert parser is not None


def test_dispatch_help(mocker):
    """Test the internal help dispatch routing."""
    parser = build_parser()

    mock_print_help = mocker.patch.object(parser, "print_help")
    args = parser.parse_args(["help"])
    args.func(args)
    mock_print_help.assert_called_once()


def test_intercept_interactive_wizards_cancellations(mocker):
    """Test that cancelling wizards propagates ExecutionAbortedError."""
    parser = mocker.Mock()

    # Init Wizard Cancellation
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch(
        "protostar.cli.run_init_wizard",
        side_effect=ExecutionAbortedError("Initialization wizard cancelled by user."),
    )
    with pytest.raises(ExecutionAbortedError):
        intercept_interactive_wizards(parser)
    parser.parse_args.assert_not_called()


def test_intercept_interactive_wizards_non_interactive_fallback(mocker):
    """Test that non-interactive execution returns cleanly without running orchestrator."""
    parser = mocker.Mock()
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch("protostar.cli.run_init_wizard", return_value=None)
    mock_orch = mocker.patch("protostar.cli.Orchestrator")

    intercept_interactive_wizards(parser)
    mock_orch.assert_not_called()


def test_configure_logging():
    """Test that the rich handler is successfully attached to the global logger."""
    import logging

    from rich.logging import RichHandler

    configure_logging()
    logger = logging.getLogger("protostar")

    assert logger.level == logging.DEBUG
    assert any(isinstance(h, RichHandler) for h in logger.handlers)


def test_handle_config_success(mocker, tmp_path):
    """Test the config command successfully spawns the user's editor."""
    mock_config_file = tmp_path / "config.toml"
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    mocker.patch.dict("os.environ", {"EDITOR": "nano"})
    mocker.patch("shutil.which", return_value="/usr/bin/nano")
    mock_run = mocker.patch("subprocess.run")

    handle_config(argparse.Namespace())

    assert mock_config_file.exists()
    assert "ide =" in __import__("protostar.config").config.DEFAULT_CONFIG_CONTENT
    mock_run.assert_called_once_with(["nano", str(mock_config_file)], check=True)


def test_handle_config_reset_confirmed(mocker, tmp_path):
    """Test that handle_config with --reset overwrites existing config when confirmed."""
    mock_config_file = tmp_path / "config.toml"
    mock_config_file.write_text("custom_setting = true\n")
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = True
    mock_run = mocker.patch("subprocess.run")

    args = argparse.Namespace(reset=True, force=False)
    handle_config(args)

    assert mock_config_file.exists()
    assert mock_config_file.read_text() == DEFAULT_CONFIG_CONTENT
    mock_run.assert_not_called()
    mock_confirm.assert_called_once_with(
        "Warning: this will erase your current configuration, are you sure you want to do this?",
        default=False,
    )


def test_handle_config_reset_cancelled(mocker, tmp_path):
    """Test that handle_config with --reset does not overwrite config when cancelled."""
    mock_config_file = tmp_path / "config.toml"
    initial_content = "custom_setting = true\n"
    mock_config_file.write_text(initial_content)
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = False
    mock_run = mocker.patch("subprocess.run")

    args = argparse.Namespace(reset=True, force=False)
    handle_config(args)

    assert mock_config_file.exists()
    assert mock_config_file.read_text() == initial_content
    mock_run.assert_not_called()


def test_handle_config_reset_aborted(mocker, tmp_path):
    """Test that handle_config with --reset raises ExecutionAbortedError when cancelled via Esc/Ctrl+C."""
    mock_config_file = tmp_path / "config.toml"
    mock_config_file.write_text("custom_setting = true\n")
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = None

    args = argparse.Namespace(reset=True, force_merge=False, force_replace=False)
    with pytest.raises(ExecutionAbortedError, match=r"Configuration reset aborted\."):
        handle_config(args)


def test_handle_config_reset_force(mocker, tmp_path):
    """Test that handle_config with --reset and --force bypasses confirmation prompt."""
    mock_config_file = tmp_path / "config.toml"
    mock_config_file.write_text("custom_setting = true\n")
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    mock_confirm = mocker.patch("questionary.confirm")
    mock_run = mocker.patch("subprocess.run")

    args = argparse.Namespace(reset=True, force_replace=True)
    handle_config(args)

    assert mock_config_file.exists()
    assert mock_config_file.read_text() == DEFAULT_CONFIG_CONTENT
    mock_run.assert_not_called()
    mock_confirm.assert_not_called()


def test_build_parser_config_reset():
    """Test that the parser correctly parses the --reset and --force flags for config."""
    parser = build_parser()
    args = parser.parse_args(["config", "--reset", "--force-replace"])
    assert args.command == "config"
    assert args.reset is True
    assert args.force_replace is True


def test_handle_config_errors(mocker, tmp_path):
    """Test missing binaries, empty env vars, and subprocess crashes in handle_config."""
    mock_config_file = tmp_path / "config.toml"
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    args = argparse.Namespace()

    # 1. Empty EDITOR
    mocker.patch.dict("os.environ", {"EDITOR": ""})
    with pytest.raises(ConfigurationError, match="environment variable is empty"):
        handle_config(args)

    # 2. Missing EDITOR executable
    mocker.patch.dict("os.environ", {"EDITOR": "not-a-real-editor"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(ConfigurationError, match="Could not resolve editor executable"):
        handle_config(args)

    # 3. Subprocess fails
    mocker.patch.dict("os.environ", {"EDITOR": "nano"})
    mocker.patch("shutil.which", return_value="/usr/bin/nano")
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "nano"))
    with pytest.raises(ConfigurationError, match="exited with non-zero status"):
        handle_config(args)


def test_main_no_command(mocker):
    """Test main gracefully exits if no subcommand is parsed."""
    mocker.patch.object(sys, "argv", ["protostar"])
    mocker.patch("protostar.cli.intercept_interactive_wizards")
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()
    mock_exit.assert_called_once_with(1)


def test_main_value_error_handling(mocker):
    """Test that TOML parsing ValueErrors are gracefully handled without crashing."""
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch("protostar.cli.intercept_interactive_wizards")
    mocker.patch(
        "protostar.cli.handle_init", side_effect=ValueError("Syntax Error in TOML")
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()
    # Updated from 1 to os.EX_SOFTWARE (70) to align with standard UNIX runtime constraints
    mock_exit.assert_called_once_with(70)


def test_handle_init_crash_test_injection(mocker):
    """Test that the --crash-test flag injects the CrashModule and its methods work."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch(
        "protostar.cli.UserConfig.load",
        return_value=UserConfig(
            just=True,
            zensical=True,
            commitizen=True,
            ci=True,
            release=True,
            readthedocs=True,
            prek=True,
            codecov=True,
            renovate=True,
            markdownlint=True,
        ),
    )

    # Simulate running `protostar init -p --crash-test`
    args = argparse.Namespace(
        PythonCore=True,  # Required to bypass the 'no language' abort
        RustModule=False,
        NodeModule=False,
        CppModule=False,
        LatexModule=False,
        docker=False,
        DirenvModule=False,
        MarkdownLintModule=False,
        RuffModule=False,
        MypyModule=False,
        PytestModule=False,
        PreCommitModule=False,
        python_version=None,
        crash_test=True,  # Trigger the injection
    )

    handle_init(args)

    # Extract the modules list passed to the Orchestrator
    modules = mock_orchestrator.call_args[0][0]

    # Find the dynamically generated CrashModule instance
    crash_mod = next(
        (m for m in modules if m.__class__.__name__ == "CrashModule"), None
    )
    assert crash_mod is not None, (
        "CrashModule was not injected into the execution stack."
    )

    assert crash_mod.name == "CrashTest"
    crash_mod.build(None)

    with pytest.raises(TypeError, match="INTENTIONAL_CRASH"):
        crash_mod.pre_flight()


def test_main_keyboard_interrupt_handling(mocker):
    """Test that a KeyboardInterrupt cleanly exits the application with code 130."""
    mocker.patch.object(sys, "argv", ["protostar", "init"])

    # Trigger the interrupt early in the main execution block
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards", side_effect=KeyboardInterrupt
    )
    mock_print = mocker.patch("protostar.cli.console.print")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 130
    assert any(
        "Aborted by user." in str(call.args[0]) for call in mock_print.call_args_list
    )


def test_dispatch_help_topic(mocker):
    """Test dispatching help strictly for a localized subcommand."""
    parser = build_parser()

    # Safely extract the init subparser
    subparsers = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    init_parser = subparsers.choices["init"]

    mock_sub_help = mocker.patch.object(init_parser, "print_help")

    args = parser.parse_args(["help", "init"])
    args.func(args)
    mock_sub_help.assert_called_once()


def test_intercept_interactive_wizards_success(mocker):
    """Test successful execution pathway of the terminal UI wizard."""
    parser = mocker.Mock()

    # Emulate running `protostar` with no arguments
    mocker.patch.object(sys, "argv", ["protostar"])

    selections = {"modules": [], "presets": [], "docker": True}
    mocker.patch("protostar.cli.run_init_wizard", return_value=selections)
    mocker.patch("protostar.cli.UserConfig.load")
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch(
        "protostar.cli.UserConfig.load",
        return_value=UserConfig(
            just=True,
            zensical=True,
            commitizen=True,
            ci=True,
            release=True,
            readthedocs=True,
            prek=True,
            codecov=True,
            renovate=True,
            markdownlint=True,
        ),
    )
    mock_exit = mocker.patch("sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)

    mock_orchestrator.return_value.run.assert_called_once()
    mock_exit.assert_called_once_with(0)


def test_print_table_help_execution(mocker):
    """Test the custom table help formatter does not raise on layout evaluation."""
    parser = build_parser()
    mock_print = mocker.patch("protostar.cli.console.print")

    # Safely extract the init subparser
    subparsers = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    init_parser = subparsers.choices["init"]

    init_parser.print_help()

    assert mock_print.called


def test_handle_config_parent_dir_creation(mocker, tmp_path):
    """Test configuration gracefully builds missing parent directories."""
    mock_config_file = tmp_path / "deep" / "nested" / "config.toml"
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    mocker.patch.dict("os.environ", {"EDITOR": "nano"})
    mocker.patch("shutil.which", return_value="/usr/bin/nano")
    mocker.patch("subprocess.run")

    handle_config(argparse.Namespace())

    assert mock_config_file.parent.exists()
    assert mock_config_file.exists()


def test_main_verbose_flag_before_subcommand(mocker):
    """Test that the --verbose flag correctly triggers logging configuration before the subcommand."""
    mocker.patch.object(sys, "argv", ["protostar", "--verbose", "init"])
    mocker.patch("protostar.cli.intercept_interactive_wizards")
    mock_configure_logging = mocker.patch("protostar.cli.configure_logging")
    mocker.patch("protostar.cli.handle_init")

    main()

    mock_configure_logging.assert_called_once()


def test_main_verbose_flag_after_subcommand(mocker):
    """Test that the --verbose flag correctly triggers logging configuration after the subcommand."""
    mocker.patch.object(sys, "argv", ["protostar", "init", "--verbose"])
    mocker.patch("protostar.cli.intercept_interactive_wizards")
    mock_configure_logging = mocker.patch("protostar.cli.configure_logging")
    mocker.patch("protostar.cli.handle_init")

    main()

    mock_configure_logging.assert_called_once()


def test_main_handles_expected_operational_errors(mocker):
    """Test that known operational errors bubble up to main, are wrapped in a rich Panel, and exit cleanly."""
    from protostar.cli import main
    from protostar.errors import ProtostarError

    mocker.patch("protostar.cli.build_parser")
    # Simulate an error raised from deep within the execution sequence
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=ProtostarError("Known config collision"),
    )
    mock_print = mocker.patch("protostar.cli.console.print")
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(1)

    # Locate the call that rendered the Rich Panel, guarding against empty print() calls
    panel_call = next(
        call
        for call in mock_print.call_args_list
        if call.args and hasattr(call.args[0], "renderable")
    )
    assert "Known config collision" in str(panel_call.args[0].renderable)
    assert "Execution Aborted" in str(panel_call.args[0].title)


def test_main_handles_unexpected_bugs(mocker):
    """Test that unknown exceptions trigger the traceback and GitHub telemetry payload."""
    from protostar.cli import main

    mocker.patch("protostar.cli.build_parser")
    # Simulate an unhandled Python bug (e.g., dictionary lookup failure)
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=KeyError("Random dictionary crash"),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    # Updated from 1 to os.EX_SOFTWARE (70) to align with standard UNIX runtime constraints
    mock_exit.assert_called_once_with(70)


def test_main_handles_keyboard_interrupt(mocker):
    """Test that Ctrl+C exists gracefully with code 130."""
    from protostar.cli import main

    mocker.patch("protostar.cli.build_parser")
    # Simulate the user aborting the prompt
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards", side_effect=KeyboardInterrupt
    )
    mock_print = mocker.patch("protostar.cli.console.print")
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(130)
    printed = " ".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "Aborted by user" in printed


def test_main_routes_configuration_error_to_posix_status(mocker):
    """Verify that a ConfigurationError returns os.EX_CONFIG (78)."""
    # Mock an operation *inside* the try-except frame to catch the error correctly
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=ConfigurationError("Malformed config"),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(os.EX_CONFIG)  # 78


def test_main_routes_missing_dependency_to_posix_status(mocker):
    """Verify that a MissingDependencyError returns os.EX_UNAVAILABLE (69)."""
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=MissingDependencyError("uv", "env scaffolding", "install hint"),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(os.EX_UNAVAILABLE)  # 69


def test_main_routes_execution_aborted_to_posix_status(mocker):
    """Verify that an ExecutionAbortedError returns code 130."""
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=ExecutionAbortedError("Interactive prompt aborted"),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(130)


def test_main_routes_filesystem_error_to_posix_status(mocker):
    """Verify that a FileSystemError returns os.EX_IOERR (74)."""
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=FileSystemError("write", "foo.txt", OSError("Permission denied")),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(os.EX_IOERR)  # 74


def test_main_routes_generic_crash_to_software_status(mocker):
    """Verify that a standard unhandled exception returns os.EX_SOFTWARE (70)."""
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=ZeroDivisionError("Unexpected math fault"),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)
    mocker.patch("protostar.cli.console.print")

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_with(os.EX_SOFTWARE)  # 70


def test_cli_handles_command_execution_error_output(mocker):
    """Test that the CLI extracts and displays stdout/stderr from CommandExecutionError."""
    # Mock CLI arguments to bypass the TUI wizard
    mocker.patch("sys.argv", ["protostar", "init", "--force-merge"])

    # Force the orchestrator to throw the specific error we want to format
    mocker.patch(
        "protostar.cli.Orchestrator.run",
        side_effect=CommandExecutionError(
            command=["uv", "init"],
            returncode=1,
            stdout="Resolving dependencies...",
            stderr="Network timeout",
        ),
    )

    mock_print = mocker.patch("protostar.cli.console.print")
    mock_exit = mocker.patch("sys.exit")

    main()

    # The CLI should intercept the domain error and trigger a standard exit(1)
    mock_exit.assert_called_with(1)

    # Extract the payload passed to rich.console.print
    # The last call is the panel rendering the error
    panel_arg = mock_print.call_args_list[-1][0][0]
    panel_body = str(panel_arg.renderable)

    assert "--- STDOUT ---" in panel_body
    assert "Resolving dependencies..." in panel_body
    assert "--- STDERR ---" in panel_body
    assert "Network timeout" in panel_body


def test_parse_dynamic_kwargs_valid():
    """Test that dynamic CLI kwargs are parsed correctly."""
    args = ["--project_name=orbit", "--author", "jackson", "--flag_without_value"]
    kwargs = _parse_dynamic_kwargs(args)

    assert kwargs == {
        "project_name": "orbit",
        "author": "jackson",
        "flag_without_value": "",
    }


def test_parse_dynamic_kwargs_rejects_positional():
    """Test that positional arguments raise a ConfigurationError."""
    args = ["--project_name", "orbit", "invalid_positional"]

    with pytest.raises(ConfigurationError, match="Unrecognized positional argument"):
        _parse_dynamic_kwargs(args)


def test_handle_init_template_resolution(mocker, tmp_path):
    """Test that passing --template resolves the internal template."""
    import importlib.resources

    # We will mock Orchestrator.run so it doesn't actually scaffold
    mocker.patch("protostar.cli.Orchestrator.run")

    args = argparse.Namespace(
        template_name="astro",
        from_path=None,
        template_context={},
        python_version="3.12",
        docker=False,
    )

    from protostar.config import UserConfig

    mock_load = mocker.patch("protostar.cli.UserConfig.load", return_value=UserConfig())
    mock_bp_load = mocker.patch("protostar.cli.TemplateBlueprint.load")

    from protostar.cli import handle_init

    handle_init(args)

    # Ensure load was called with the absolute path of the built-in astro.toml
    expected_path = str(
        importlib.resources.files("protostar.templates").joinpath("astro.toml")
    )
    mock_bp_load.assert_any_call(
        expected_path,
        template_context={},
        variable_resolver=mocker.ANY,
    )
    assert mock_load.call_count >= 1


def test_handle_init_cli_template_resolution(mocker):
    """Test that passing --template cli resolves and loads the cli.toml template."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch(
        "protostar.cli.UserConfig.load",
        return_value=UserConfig(
            just=True,
            zensical=True,
            commitizen=True,
            ci=True,
            release=True,
            readthedocs=True,
            prek=True,
            codecov=True,
            renovate=True,
            markdownlint=True,
        ),
    )

    args = argparse.Namespace(
        template_name="cli",
        from_path=None,
        template_context={},
        python_version="3.12",
        docker=False,
    )

    handle_init(args)

    assert mock_orchestrator.call_count == 1

    # Verify the template blueprint was loaded and passed to the Orchestrator
    blueprint = mock_orchestrator.call_args.kwargs.get("blueprint")
    assert blueprint is not None
    assert "typer" in blueprint.dependencies
    assert "rich" in blueprint.dependencies
