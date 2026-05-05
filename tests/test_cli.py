import argparse
import importlib.metadata
import subprocess
import sys

import pytest

from protostar.cli import (
    ProtoHelpFormatter,
    build_parser,
    configure_logging,
    handle_config,
    handle_init,
    intercept_interactive_wizards,
    main,
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
    """Test that cancelling wizards safely exits the process with code 130."""
    parser = mocker.Mock()

    # Init Wizard Cancellation
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch("protostar.cli.run_init_wizard", return_value=None)
    with pytest.raises(SystemExit) as exc_info:
        intercept_interactive_wizards(parser)
    assert exc_info.value.code == 130
    parser.parse_args.assert_not_called()


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
    assert "ide =" in mock_config_file.read_text()
    mock_run.assert_called_once_with(["nano", str(mock_config_file)], check=True)


def test_handle_config_errors(mocker, tmp_path):
    """Test missing binaries, empty env vars, and subprocess crashes in handle_config."""
    mock_config_file = tmp_path / "config.toml"
    mocker.patch("protostar.cli.CONFIG_FILE", mock_config_file)
    args = argparse.Namespace()

    # 1. Empty EDITOR
    mocker.patch.dict("os.environ", {"EDITOR": ""})
    with pytest.raises(SystemExit):
        handle_config(args)

    # 2. Missing EDITOR executable
    mocker.patch.dict("os.environ", {"EDITOR": "not-a-real-editor"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(SystemExit):
        handle_config(args)

    # 3. Subprocess fails
    mocker.patch.dict("os.environ", {"EDITOR": "nano"})
    mocker.patch("shutil.which", return_value="/usr/bin/nano")
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "nano"))
    with pytest.raises(SystemExit):
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
    mock_exit.assert_called_once_with(1)


def test_handle_init_crash_test_injection(mocker):
    """Test that the --crash-test flag injects the CrashModule and its methods work."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")

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
