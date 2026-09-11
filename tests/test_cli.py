import argparse
import importlib.metadata
import json
import subprocess
import sys

import pytest

from protostar.cli.main import (
    _parse_dynamic_kwargs,
    configure_logging,
    handle_config,
    handle_init,
    main,
)
from protostar.cli.parser import (
    JsonAwareParser,
    ProtoHelpFormatter,
    _resolve_usage_doc_path,
    build_parser,
    intercept_interactive_wizards,
)
from protostar.config import DEFAULT_CONFIG_CONTENT, UserConfig
from protostar.errors import (
    CommandExecutionError,
    ConfigurationError,
    ExecutionAbortedError,
    ExitCode,
    FileSystemError,
    InvalidUsageError,
    MissingDependencyError,
    NetworkFetchError,
    TemplateResolutionError,
)
from protostar.system_deps import GlobalExecutable
from protostar.wizard import WizardSelections


def test_proto_help_formatter_usage():
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
        "protostar.cli.parser.run_init_wizard",
        side_effect=ExecutionAbortedError("Initialization wizard cancelled by user."),
    )
    with pytest.raises(ExecutionAbortedError):
        intercept_interactive_wizards(parser)
    parser.parse_args.assert_not_called()


def test_intercept_interactive_wizards_non_interactive_fallback(mocker):
    """Test that non-interactive execution returns cleanly without running orchestrator."""
    parser = mocker.Mock()
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch("protostar.cli.parser.run_init_wizard", return_value=None)
    mock_orch = mocker.patch("protostar.cli.main.Orchestrator")

    intercept_interactive_wizards(parser)
    mock_orch.assert_not_called()


def test_configure_logging():
    """Test that the rich handler is successfully attached to the global logger."""
    import logging

    from rich.logging import RichHandler

    try:
        configure_logging()
        logger = logging.getLogger("protostar")

        assert logger.level == logging.DEBUG
        assert any(isinstance(h, RichHandler) for h in logger.handlers)
    finally:
        logger = logging.getLogger("protostar")
        logger.setLevel(logging.NOTSET)
        logger.handlers.clear()


def test_handle_config_success(mocker, tmp_path):
    """Test the config command successfully spawns the user's editor."""
    mock_config_file = tmp_path / "config.toml"
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
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
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
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
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
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
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = None

    args = argparse.Namespace(reset=True, force_merge=False, force_replace=False)
    with pytest.raises(ExecutionAbortedError, match=r"Configuration reset aborted\."):
        handle_config(args)


def test_handle_config_reset_force(mocker, tmp_path):
    """Test that handle_config with --reset and --force bypasses confirmation prompt."""
    mock_config_file = tmp_path / "config.toml"
    mock_config_file.write_text("custom_setting = true\n")
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
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
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
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
    mocker.patch("protostar.cli.parser.intercept_interactive_wizards")
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()
    mock_exit.assert_called_once_with(1)


def test_main_value_error_handling(mocker):
    """Test that TOML parsing ValueErrors are gracefully handled without crashing."""
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch("protostar.cli.parser.intercept_interactive_wizards")
    mocker.patch(
        "protostar.cli.main.handle_init", side_effect=ValueError("Syntax Error in TOML")
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()
    # Updated from 1 to ExitCode.SOFTWARE (70) to align with standard UNIX runtime constraints
    mock_exit.assert_called_once_with(70)


def test_handle_init_crash_test_injection(mocker):
    """Test that the --crash-test flag injects the CrashModule and its methods work."""
    mock_orchestrator = mocker.patch("protostar.cli.main.Orchestrator")
    mocker.patch(
        "protostar.cli.main.UserConfig.load",
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
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=KeyboardInterrupt,
    )
    mock_print = mocker.patch("protostar.cli.ui.console.print")

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

    selections = WizardSelections(modules=[], docker=True)
    mocker.patch("protostar.cli.parser.run_init_wizard", return_value=selections)
    mocker.patch("protostar.cli.parser.UserConfig.load")
    mock_orchestrator = mocker.patch("protostar.cli.parser.Orchestrator")
    mocker.patch(
        "protostar.cli.parser.UserConfig.load",
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

    mock_orchestrator.return_value.plan.return_value = mocker.MagicMock(
        diagnostics=[], tasks=mocker.MagicMock(system_tasks=[], post_install_tasks=[])
    )
    mock_orchestrator.return_value.execute.return_value = mocker.MagicMock(
        diagnostics=(), touched_paths=frozenset()
    )

    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)

    mock_orchestrator.return_value.plan.assert_called_once()
    mock_orchestrator.return_value.execute.assert_called_once()
    mock_exit.assert_called_once_with(0)


def test_print_table_help_execution(mocker):
    """Test the custom table help formatter does not raise on layout evaluation."""
    parser = build_parser()
    mock_print = mocker.patch("protostar.cli.ui.console.print")

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
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config_file)
    mocker.patch.dict("os.environ", {"EDITOR": "nano"})
    mocker.patch("shutil.which", return_value="/usr/bin/nano")
    mocker.patch("subprocess.run")

    handle_config(argparse.Namespace())

    assert mock_config_file.parent.exists()
    assert mock_config_file.exists()


def test_main_verbose_flag_before_subcommand(mocker):
    """Test that the --verbose flag correctly triggers logging configuration before the subcommand."""
    mocker.patch.object(sys, "argv", ["protostar", "--verbose", "init"])
    mocker.patch("protostar.cli.parser.intercept_interactive_wizards")
    mock_configure_logging = mocker.patch("protostar.cli.main.configure_logging")
    mocker.patch("protostar.cli.main.handle_init")

    main()

    mock_configure_logging.assert_called_once()


def test_main_verbose_flag_after_subcommand(mocker):
    """Test that the --verbose flag correctly triggers logging configuration after the subcommand."""
    mocker.patch.object(sys, "argv", ["protostar", "init", "--verbose"])
    mocker.patch("protostar.cli.parser.intercept_interactive_wizards")
    mock_configure_logging = mocker.patch("protostar.cli.main.configure_logging")
    mocker.patch("protostar.cli.main.handle_init")

    main()

    mock_configure_logging.assert_called_once()


def test_main_handles_expected_operational_errors(mocker):
    """Test that known operational errors bubble up to main, are wrapped in a rich Panel, and exit cleanly."""
    from protostar.cli import main
    from protostar.errors import ProtostarError

    mocker.patch("protostar.cli.main.parser.build_parser")
    # Simulate an error raised from deep within the execution sequence
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=ProtostarError("Known config collision"),
    )
    mock_print = mocker.patch("protostar.cli.ui.console.print")
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

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

    mocker.patch("protostar.cli.main.parser.build_parser")
    # Simulate an unhandled Python bug (e.g., dictionary lookup failure)
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=KeyError("Random dictionary crash"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    # Updated from 1 to ExitCode.SOFTWARE (70) to align with standard UNIX runtime constraints
    mock_exit.assert_called_once_with(70)


def test_main_handles_keyboard_interrupt(mocker):
    """Test that Ctrl+C exists gracefully with code 130."""
    from protostar.cli import main

    mocker.patch("protostar.cli.main.parser.build_parser")
    # Simulate the user aborting the prompt
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=KeyboardInterrupt,
    )
    mock_print = mocker.patch("protostar.cli.ui.console.print")
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(130)
    printed = " ".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "Aborted by user" in printed


def test_main_routes_invalid_usage_error_to_posix_status(mocker):
    """Verify that an InvalidUsageError returns ExitCode.USAGE (64)."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=InvalidUsageError("bad flag"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.USAGE)


def test_resolve_usage_doc_path_known_subcommand(mocker):
    mocker.patch.object(sys, "argv", ["protostar", "init", "--bad"])
    assert _resolve_usage_doc_path() == "usage/init/"


def test_resolve_usage_doc_path_unknown_subcommand_falls_back_to_root(mocker):
    mocker.patch.object(sys, "argv", ["protostar", "deploy", "--bad"])
    assert _resolve_usage_doc_path() == "usage/cli-reference/"


def test_resolve_usage_doc_path_no_subcommand_falls_back_to_root(mocker):
    mocker.patch.object(sys, "argv", ["protostar"])
    assert _resolve_usage_doc_path() == "usage/cli-reference/"


def test_main_routes_configuration_error_to_posix_status(mocker):
    """Verify that a ConfigurationError returns ExitCode.CONFIG (78)."""
    # Mock an operation *inside* the try-except frame to catch the error correctly
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=ConfigurationError("Malformed config"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.CONFIG)  # 78


def test_main_routes_template_resolution_error_to_posix_status(mocker):
    """Verify that a TemplateResolutionError returns ExitCode.DATAERR (65)."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=TemplateResolutionError("my-template", "Malformed archive"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.DATAERR)  # 65


def test_main_routes_network_fetch_error_to_posix_status(mocker):
    """Verify that a NetworkFetchError returns ExitCode.TEMPFAIL (75)."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=NetworkFetchError("https://example.com"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.TEMPFAIL)  # 75


def test_main_routes_missing_dependency_to_posix_status(mocker):
    """Verify that a MissingDependencyError returns ExitCode.UNAVAILABLE (69)."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=MissingDependencyError(GlobalExecutable.UV, "env scaffolding"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.UNAVAILABLE)  # 69


def test_main_routes_execution_aborted_to_posix_status(mocker):
    """Verify that an ExecutionAbortedError returns code 130."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=ExecutionAbortedError("Interactive prompt aborted"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(130)


def test_main_routes_filesystem_error_to_posix_status(mocker):
    """Verify that a FileSystemError returns ExitCode.IOERR (74)."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=FileSystemError("write", "foo.txt", OSError("Permission denied")),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.IOERR)  # 74


def test_main_routes_generic_crash_to_software_status(mocker):
    """Verify that a standard unhandled exception returns ExitCode.SOFTWARE (70)."""
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=ZeroDivisionError("Unexpected math fault"),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)
    mocker.patch("protostar.cli.ui.console.print")

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_with(ExitCode.SOFTWARE)  # 70


def test_cli_handles_command_execution_error_output(mocker):
    """Test that the CLI extracts and displays stdout/stderr from CommandExecutionError."""
    # Mock CLI arguments to bypass the TUI wizard
    mocker.patch("sys.argv", ["protostar", "init", "--force-merge"])

    # Force _run_engine to throw the specific error we want to format
    mocker.patch(
        "protostar.cli.ui._run_engine",
        side_effect=CommandExecutionError(
            command=["uv", "init"],
            returncode=1,
            stdout="Resolving dependencies...",
            stderr="Network timeout",
        ),
    )

    mock_print = mocker.patch("protostar.cli.ui.console.print")
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


def test_handle_init_template_resolution(mocker):
    """Test that passing --template resolves the internal template."""
    import importlib.resources

    # We will mock _run_engine so it doesn't actually scaffold
    mocker.patch("protostar.cli.ui._run_engine")

    args = argparse.Namespace(
        template_name="astro",
        from_path=None,
        template_context={},
        python_version="3.12",
        docker=False,
    )

    from protostar.config import UserConfig

    mock_load = mocker.patch(
        "protostar.cli.main.UserConfig.load", return_value=UserConfig()
    )
    mock_bp_load = mocker.patch("protostar.cli.main.TemplateBlueprint.load")

    # Removed handle_init import as it is global

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
    mock_orchestrator = mocker.patch("protostar.cli.main.Orchestrator")
    mocker.patch(
        "protostar.cli.main.UserConfig.load",
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

    # Verify the template blueprint was loaded and passed to the Orchestrator via InitRequest
    request = mock_orchestrator.call_args.kwargs.get("request")
    assert request is not None
    blueprint = request.template_blueprint
    assert blueprint is not None
    assert "typer" in blueprint.dependencies
    assert "rich" in blueprint.dependencies


def test_cli_resolves_user_template_aliases(mocker) -> None:
    """Verifies that --template successfully resolves keys from the global config alias table."""

    # Mock the global config to contain a custom alias
    from protostar.config import TemplateAliasConfig

    mock_config = UserConfig(
        templates={
            "my-custom-org": TemplateAliasConfig(
                source="https://example.com/template.toml"
            )
        }
    )
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=mock_config)

    # Mock the Orchestrator instantiation so we can inspect the flags passed to it
    mock_orchestrator = mocker.patch("protostar.cli.main.Orchestrator")
    # _run_engine will call plan/execute on the mock — set up safe returns
    mock_orchestrator.return_value.plan.return_value = mocker.MagicMock(
        diagnostics=[], tasks=mocker.MagicMock(system_tasks=[], post_install_tasks=[])
    )
    mock_orchestrator.return_value.execute.return_value = mocker.MagicMock(
        diagnostics=(), touched_paths=frozenset()
    )

    # Mock TemplateBlueprint to prevent network calls during the test
    mocker.patch("protostar.cli.main.TemplateBlueprint.load", return_value=None)

    args = argparse.Namespace(
        template_name="my-custom-org",
        from_path=None,
        template_context={},
        docker=False,
        force_merge=False,
        force_replace=False,
        python_version=None,
        crash_test=False,
    )

    handle_init(args)

    # Verify the orchestrator was initialized with the correct security flags via InitRequest
    _, kwargs = mock_orchestrator.call_args
    request = kwargs.get("request")
    assert request is not None
    assert request.is_external is True
    assert request.is_user_aliased is True
    assert request.is_trusted is False

    # Now verify trusted alias sets is_trusted to True
    from protostar.config import TemplateAliasConfig

    mock_config.templates["trusted-corp"] = TemplateAliasConfig(
        source="https://example.com/corp.toml", trusted=True
    )
    args.template_name = "trusted-corp"
    handle_init(args)
    _, kwargs = mock_orchestrator.call_args
    trusted_request = kwargs.get("request")
    assert trusted_request is not None
    assert trusted_request.is_external is True
    assert trusted_request.is_user_aliased is True
    assert trusted_request.is_trusted is True


def test_cli_rejects_unknown_templates(mocker) -> None:
    """Verifies that a template not in built-ins or aliases raises a ConfigurationError."""
    from protostar.config import TemplateAliasConfig

    mock_config = UserConfig(
        templates={"valid-alias": TemplateAliasConfig(source="...")}
    )
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=mock_config)

    args = argparse.Namespace(
        template_name="non-existent-template",
        from_path=None,
        template_context={},
    )

    with pytest.raises(
        ConfigurationError,
        match="not found in built-ins or global configuration aliases",
    ):
        handle_init(args)


def test_export_schema_json_mode(capsys, monkeypatch):
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "export-schema", "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "properties" in payload


def test_list_templates_json_mode(capsys, monkeypatch):
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--list-templates", "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert "templates" in payload
    assert isinstance(payload["templates"], list)
    assert len(payload["templates"]) >= 6
    sample = payload["templates"][0]
    for key in ("alias", "name", "description", "type", "source", "trusted"):
        assert key in sample


def test_list_templates_table_output(capsys, monkeypatch):
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--list-templates"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Available Templates" in captured.out
    assert "FastAPI" in captured.out
    assert "(api)" not in captured.out
    assert "Built-in" in captured.out


def test_list_templates_table_output_with_external(capsys, monkeypatch):
    from protostar.config import TemplateAliasConfig, UserConfig

    fake_cfg = UserConfig(
        templates={
            "custom-app": TemplateAliasConfig(
                source="https://github.com/org/template",
                name="Custom App",
                description="Custom company application",
                trusted=True,
            )
        }
    )
    monkeypatch.setattr("protostar.config.UserConfig.load", lambda: fake_cfg)
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--list-templates"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Custom App" in captured.out
    assert "External" in captured.out
    assert "Built-in" in captured.out


def test_init_resolves_template_by_display_name(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", False)
    monkeypatch.setattr(
        "sys.argv", ["protostar", "init", "--template", "FastAPI", "--dry-run"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Summary" in captured.out
    assert "fastapi" in captured.out


def test_collision_bubbles_in_json_mode(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").touch()
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(
        "sys.argv", ["protostar", "init", "--template", "cli", "--json"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "WorkspaceCollisionError"
    assert "pyproject.toml" in payload["error"]["paths"][0]


def test_resolve_usage_doc_path_with_leading_flags(mocker):
    """Test that doc path resolution extracts the subcommand even if flags precede it."""
    mocker.patch.object(sys, "argv", ["protostar", "-v", "init", "--bad"])
    assert _resolve_usage_doc_path() == "usage/init/"


def test_json_aware_parser_raises_invalid_usage_error():
    """Test that JsonAwareParser.error raises InvalidUsageError with doc path."""
    parser = JsonAwareParser()
    with pytest.raises(InvalidUsageError) as exc_info:
        parser.error("test parse error")
    assert "test parse error" in str(exc_info.value)


def test_main_invalid_subcommand_human_mode(mocker):
    """Test that an invalid subcommand in human mode is pretty-printed and exits with EX_USAGE."""
    mocker.patch.object(sys, "argv", ["protostar", "wrong-command"])
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.cli.ui.console.print")

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.USAGE)
    assert mock_print.call_count >= 1
    # Check that the Rich Panel was passed to console.print
    from rich.panel import Panel

    panels = [
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], Panel)
    ]
    assert len(panels) == 1
    assert "invalid choice" in str(panels[0].renderable)
    assert "wrong-command" in str(panels[0].renderable)


def test_main_invalid_subcommand_json_mode(capsys, monkeypatch):
    """Test that an invalid subcommand in JSON mode emits structured error and exits with EX_USAGE."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "wrong-command", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == ExitCode.USAGE
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "InvalidUsageError"
    assert "invalid choice" in payload["error"]["message"]
    assert "wrong-command" in payload["error"]["message"]


def test_main_missing_argument_human_mode(mocker):
    """Test that missing required option arguments exit with EX_USAGE and rich panel."""
    mocker.patch.object(sys, "argv", ["protostar", "init", "--python-version"])
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.cli.ui.console.print")

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(ExitCode.USAGE)
    from rich.panel import Panel

    panels = [
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], Panel)
    ]
    assert len(panels) == 1
    assert "expected one argument" in str(panels[0].renderable)


def test_main_missing_argument_json_mode(capsys, monkeypatch):
    """Test that missing required option arguments in JSON mode emit structured error."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--python-version", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == ExitCode.USAGE
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "InvalidUsageError"
    assert "expected one argument" in payload["error"]["message"]


def test_help_json_mode_global(capsys, monkeypatch):
    """Test that 'protostar help --json' emits full capabilities JSON schema."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "help", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert "capabilities" in payload
    commands = payload["capabilities"]["commands"]
    assert "init" in commands
    assert "config" in commands
    assert "export-schema" in commands


def test_help_subcommand_json_mode(capsys, monkeypatch):
    """Test that 'protostar help init --json' emits scoped capabilities JSON schema."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "help", "init", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert "capabilities" in payload
    commands = payload["capabilities"]["commands"]
    assert "init" in commands
    assert "config" not in commands
    assert "export-schema" not in commands


def test_init_help_flag_json_mode(capsys, monkeypatch):
    """Test that 'protostar init --help --json' emits scoped capabilities JSON schema."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--help", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert "capabilities" in payload
    commands = payload["capabilities"]["commands"]
    assert "init" in commands
    assert "config" not in commands


def test_help_invalid_subcommand_json_mode(capsys, monkeypatch):
    """Test that 'protostar help invalid --json' emits InvalidUsageError JSON payload."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "help", "invalid-topic", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == ExitCode.USAGE
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "InvalidUsageError"
    assert "invalid choice" in payload["error"]["message"]


def test_cli_reference_fixture_tables():
    """Verify that all generated CLI fixture tables exist and contain required headers and flags."""
    from pathlib import Path

    from protostar.modules import TOOLING_MODULES

    fixtures_dir = Path("docs/fixtures")
    assert fixtures_dir.exists()

    # Verify Global Options fixture
    global_file = fixtures_dir / "table_cli_global.md"
    assert global_file.exists()
    global_content = global_file.read_text()
    assert "| Flag | Shorthand | Description |" in global_content
    assert "`--json`" in global_content
    assert "`--dry-run`" in global_content
    assert "`--verbose`" in global_content

    # Verify Init Core Options fixture
    init_core_file = fixtures_dir / "table_cli_init_core.md"
    assert init_core_file.exists()
    init_core_content = init_core_file.read_text()
    assert "| Option | Shorthand | Description |" in init_core_content
    assert "`--template <NAME>`" in init_core_content
    assert "`--force-merge`" in init_core_content

    # Verify Tooling Flags fixture contains all TOOLING_MODULES
    tooling_flags_file = fixtures_dir / "table_cli_tooling_flags.md"
    assert tooling_flags_file.exists()
    tooling_flags_content = tooling_flags_file.read_text()
    assert "| Enable Flag | Disable Flag | Description |" in tooling_flags_content
    for mod in TOOLING_MODULES:
        if mod.cli_flags:
            assert f"`{mod.cli_flags[0]}`" in tooling_flags_content

    # Verify Config Options fixture
    config_file = fixtures_dir / "table_cli_config.md"
    assert config_file.exists()
    config_content = config_file.read_text()
    assert "`--reset`" in config_content

    # Verify Export Schema Options fixture
    export_file = fixtures_dir / "table_cli_export_schema.md"
    assert export_file.exists()
    export_content = export_file.read_text()
    assert "`--json`" in export_content

    # Verify Completion Options fixture
    completion_file = fixtures_dir / "table_cli_completion.md"
    assert completion_file.exists()
    completion_content = completion_file.read_text()
    assert "`<shell>`" in completion_content

    # Verify Exit Codes fixture
    exit_codes_file = fixtures_dir / "table_exit_codes.md"
    assert exit_codes_file.exists()
    exit_codes_content = exit_codes_file.read_text()
    assert (
        "| Exit Code | POSIX Name | Exception Class | Trigger Condition |"
        in exit_codes_content
    )
    assert "`EX_OK`" in exit_codes_content
    assert "`os.EX_USAGE`" in exit_codes_content


def test_version_flag_toplevel(capsys, monkeypatch):
    """Test that 'protostar --version' prints the top-level application version and exits 0."""
    import protostar

    monkeypatch.setattr(sys, "argv", ["protostar", "--version"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"protostar {protostar.__version__}"


def test_version_flag_subcommand_rejected(monkeypatch):
    """Test that passing '--version' to a subcommand is rejected as an invalid argument."""
    monkeypatch.setattr(sys, "argv", ["protostar", "config", "--version"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == ExitCode.USAGE


def test_version_flag_json_mode_toplevel(capsys, monkeypatch):
    """Test that 'protostar --version --json' returns a success payload with the version."""
    import protostar

    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(sys, "argv", ["protostar", "--version", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert payload["version"] == protostar.__version__


def test_version_flag_json_mode_subcommand_rejected(capsys, monkeypatch):
    """Test that passing '--version' to a subcommand in JSON mode returns an error envelope."""
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(sys, "argv", ["protostar", "config", "--version", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == ExitCode.USAGE
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "InvalidUsageError"
    assert "Unrecognized arguments: --version" in payload["error"]["message"]


def test_verbose_flag_suppressed_in_non_init_help(capsys, monkeypatch):
    """Test that '--verbose' is suppressed from non-init subcommand help output."""
    monkeypatch.setattr(sys, "argv", ["protostar", "config", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--verbose" not in captured.out
    assert "-v," not in captured.out


def test_verbose_flag_visible_in_init_help():
    """Test that '--verbose' is visible in 'init --help' output."""
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    init_parser = subparsers_action.choices["init"]
    assert any(
        action.dest == "verbose" and action.help != argparse.SUPPRESS
        for action in init_parser._actions
    )


def test_verbose_flag_functional_on_non_init_subcommands():
    """Test that '--verbose' and '-v' are still accepted by non-init subcommands."""
    parser = build_parser()
    args1 = parser.parse_args(["config", "-v"])
    assert getattr(args1, "verbose", False) is True

    args2 = parser.parse_args(["completion", "--verbose"])
    assert getattr(args2, "verbose", False) is True


def test_completion_verbose_logging(capsys, monkeypatch):
    """Test that 'completion --verbose' emits debug log entries to stderr."""
    import logging

    monkeypatch.setattr(sys, "argv", ["protostar", "completion", "bash", "--verbose"])
    try:
        main()
        captured = capsys.readouterr()
        assert "Handling 'completion' command" in captured.err
        assert "Generating completion script" in captured.err
    finally:
        logger = logging.getLogger("protostar")
        logger.setLevel(logging.NOTSET)
        logger.handlers.clear()


def test_config_verbose_logging(capsys, monkeypatch, tmp_path, mocker):
    """Test that 'config -v' emits debug logs to stderr."""
    import logging

    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\n")
    mocker.patch("protostar.cli.main.CONFIG_FILE", mock_config)
    mocker.patch("subprocess.run")

    monkeypatch.setattr(sys, "argv", ["protostar", "config", "-v"])
    try:
        main()
        captured = capsys.readouterr()
        assert "Handling 'config' command" in captured.err
        assert "Looked up editor binary" in captured.err
    finally:
        logger = logging.getLogger("protostar")
        logger.setLevel(logging.NOTSET)
        logger.handlers.clear()
