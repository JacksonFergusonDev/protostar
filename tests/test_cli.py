import argparse
import importlib.metadata
import subprocess
import sys
import types

import pytest
from rich.console import Group
from rich.table import Table

from protostar.cli import (
    GenerateEpilogTable,
    LazyTargetHelp,
    ProtoHelpFormatter,
    build_parser,
    configure_logging,
    get_ide_module,
    handle_config,
    handle_generate,
    handle_init,
    intercept_interactive_wizards,
    main,
    print_table_help,
)
from protostar.modules import (
    LANG_MODULES,
    DirenvModule,
    JetBrainsModule,
    MarkdownLintModule,
    MypyModule,
    PytestModule,
    PythonModule,
    RuffModule,
    VSCodeModule,
)
from protostar.modules.tooling_layer import PreCommitModule


def test_handle_init_dispatch(mocker):
    """Test that dynamically generated CLI flags instantiate modules and presets."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch("protostar.cli.get_os_module")
    mocker.patch("protostar.cli.get_ide_module", return_value=None)

    # Simulate running `proto init -p -s -a -d -e --docker --direnv -m --python-version 3.12 --ruff --mypy --pytest --pre-commit`
    args = argparse.Namespace(
        PythonModule=True,
        RustModule=False,
        NodeModule=False,
        CppModule=False,
        LatexModule=False,
        ScientificPreset=True,
        AstroPreset=True,
        DspPreset=True,
        EmbeddedPreset=True,
        docker=True,
        DirenvModule=True,
        MarkdownLintModule=True,
        RuffModule=True,
        MypyModule=True,
        PytestModule=True,
        PreCommitModule=True,
        python_version="3.12",
    )

    handle_init(args)

    # Extract the arguments passed to Orchestrator(modules, presets, docker=...)
    modules = mock_orchestrator.call_args[0][0]

    # Verify Tooling Modules
    assert any(isinstance(m, DirenvModule) for m in modules)
    assert any(isinstance(m, MarkdownLintModule) for m in modules)
    assert any(isinstance(m, RuffModule) for m in modules)
    assert any(isinstance(m, MypyModule) for m in modules)
    assert any(isinstance(m, PytestModule) for m in modules)
    assert any(isinstance(m, PreCommitModule) for m in modules)


def test_handle_init_tooling_requires_language_context(mocker):
    """Test that python-specific tooling does not activate if PythonModule is absent."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch("protostar.cli.get_os_module")
    mocker.patch("protostar.cli.get_ide_module", return_value=None)

    # Mock the global config to request Ruff and Mypy by default
    mock_config = mocker.patch("protostar.cli.ProtostarConfig.load")
    mock_config.return_value.ruff = True
    mock_config.return_value.mypy = True

    # Simulate a Rust-only initialization
    args = argparse.Namespace(
        RustModule=True,
        PythonModule=False,
        NodeModule=False,
        CppModule=False,
        LatexModule=False,
        docker=False,
        DirenvModule=False,
        MarkdownLintModule=False,
        RuffModule=False,
        MypyModule=False,
        PytestModule=False,
    )

    handle_init(args)

    modules = mock_orchestrator.call_args[0][0]

    # Verify that despite config defaults, Ruff and Mypy do not pollute the Rust context
    assert not any(isinstance(m, RuffModule) for m in modules)
    assert not any(isinstance(m, MypyModule) for m in modules)


def test_get_ide_module_dispatch():
    """Test that IDE aliases correctly resolve to their respective module classes."""
    vscode_mod = get_ide_module("cursor")
    assert isinstance(vscode_mod, VSCodeModule)

    jetbrains_mod = get_ide_module("jetbrains")
    assert isinstance(jetbrains_mod, JetBrainsModule)

    unknown_mod = get_ide_module("eclipse")
    assert unknown_mod is None


def test_main_intercepts_bare_invocation(mocker):
    """Test that a zero-argument execution routes to the discovery wizard."""
    # Mock sys.argv to simulate running just `protostar`
    mocker.patch.object(sys, "argv", ["protostar"])

    mock_discovery = mocker.patch(
        "protostar.cli.run_discovery_wizard", return_value="init"
    )

    # We expect sys.exit to be called because parse_args won't actually execute handle_init in our mock
    with pytest.raises(SystemExit):
        main()

    mock_discovery.assert_called_once()
    # Verify the interceptor appended the selection to sys.argv
    assert sys.argv == ["protostar", "init"]


def test_main_intercepts_init_wizard(mocker):
    """Test that `protostar init` routes directly to the init wizard and executes the Orchestrator."""
    mocker.patch.object(sys, "argv", ["protostar", "init"])

    mock_init_wizard = mocker.patch("protostar.cli.run_init_wizard")
    mock_init_wizard.return_value = {
        "modules": [PythonModule()],
        "presets": [],
        "docker": False,
    }

    mock_config = mocker.patch("protostar.cli.ProtostarConfig.load")
    mock_config.return_value.ide = "vscode"

    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    mock_init_wizard.assert_called_once()

    # Verify Orchestrator was initialized with the wizard payload + implicit OS/IDE layers
    orchestrator_args = mock_orchestrator.call_args[0]
    modules_passed = orchestrator_args[0]

    assert any(isinstance(m, PythonModule) for m in modules_passed)
    assert any(isinstance(m, VSCodeModule) for m in modules_passed)
    mock_orchestrator.return_value.run.assert_called_once()


def test_main_intercepts_generate_wizard(mocker):
    """Test that `protostar generate` routes to the wizard and executes the target generator."""
    mocker.patch.object(sys, "argv", ["protostar", "generate"])

    mock_gen_wizard = mocker.patch("protostar.cli.run_generate_wizard")
    mock_gen_wizard.return_value = {"target": "cpp_class", "name": "OrbitalMechanics"}
    mocker.patch("protostar.cli.ProtostarConfig.load")

    # Mock the generator execution
    mock_target_gen = mocker.MagicMock()
    mock_target_gen.execute.return_value = []

    mock_registry = mocker.patch("protostar.cli.GENERATOR_REGISTRY")
    mock_registry.get.return_value = mock_target_gen

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    mock_gen_wizard.assert_called_once()
    mock_target_gen.execute.assert_called_once_with("OrbitalMechanics", mocker.ANY)


def test_lazy_target_help_proxy():
    """Test that the lazy evaluation proxy mimics a string and yields native rich objects."""
    proxy = LazyTargetHelp()

    # 1. Test string conversion and argparse interpolation interception
    string_eval = str(proxy)
    assert "The boilerplate target" in string_eval
    assert "cpp-class" in string_eval

    mod_eval = proxy % {}
    assert "The boilerplate target" in mod_eval

    # 2. Test attribute delegation (masquerading as a string to formatters)
    stripped = proxy.strip()
    assert isinstance(stripped, str)

    # 3. Test native rich object generation
    renderable = proxy.get_renderable()
    assert isinstance(renderable, Group)
    assert isinstance(renderable.renderables[1], Table)


def test_generate_epilog_table_proxy():
    """Test that the epilog proxy evaluates cleanly as both a string and a table."""
    proxy = GenerateEpilogTable()

    # 1. Test string fallbacks
    assert str(proxy) == "How NAME is evaluated:"
    assert (proxy % {}) == "How NAME is evaluated:"
    assert proxy.upper() == "HOW NAME IS EVALUATED:"

    # 2. Test native table generation
    renderable = proxy.get_renderable()
    assert isinstance(renderable, Table)
    assert renderable.title == "How NAME is evaluated:"


def test_proto_help_formatter_usage(mocker):
    """Test that the custom formatter correctly overrides the usage prefix."""
    parser = argparse.ArgumentParser(formatter_class=ProtoHelpFormatter)
    parser.add_argument("--foo", help="Foo argument")

    help_output = parser.format_help()

    # Ensure the capitalized 'Usage:' prefix is applied
    assert "Usage:" in help_output
    assert "usage:" not in help_output


def test_print_table_help_rendering(mocker):
    """Test that the custom table renderer parses actions and delegates to rich."""
    mock_print = mocker.patch("protostar.cli.console.print")

    parser = argparse.ArgumentParser(description="Test parser description")

    # 1. Standard argument
    parser.add_argument("--foo", help="Foo argument help")

    # 2. Suppressed argument (should be filtered out)
    parser.add_argument("--hidden", help=argparse.SUPPRESS)

    # 3. Proxy epilog
    parser.epilog = GenerateEpilogTable()  # type: ignore[assignment]

    # Monkey-patch the method just like the main execution does
    parser.print_help = types.MethodType(print_table_help, parser)  # type: ignore[method-assign]

    parser.print_help()

    # Aggregate all the objects sent to console.print
    printed_args = [call.args[0] for call in mock_print.call_args_list if call.args]

    # Verify description printed
    assert "Test parser description\n" in printed_args

    # Verify the table was generated
    tables = [obj for obj in printed_args if isinstance(obj, Table)]
    assert len(tables) > 0

    # The epilog renderable should be the last table
    assert tables[-1].title == "How NAME is evaluated:"

    # Ensure suppressed arguments didn't make it to the output
    table_strings = str(tables[0].columns)
    assert "foo" in table_strings
    assert "hidden" not in table_strings


def test_handle_init_aborts_on_no_language(mocker):
    """Test that `protostar init` gracefully aborts if no language is selected."""
    args = argparse.Namespace(docker=False, force=False)
    for mod in LANG_MODULES:
        setattr(args, mod.__class__.__name__, False)

    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.cli.console.print")

    with pytest.raises(SystemExit):
        handle_init(args)

    mock_exit.assert_called_once_with(1)
    printed = " ".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "Please specify at least one language flag" in printed


def test_handle_generate_unknown_target(mocker):
    """Test that handle_generate catches invalid targets safely."""
    args = argparse.Namespace(target="unknown_target", name="foo")
    mock_print = mocker.patch("protostar.cli.console.print")

    handle_generate(args)

    printed = " ".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "Unknown target" in printed


def test_handle_generate_success_and_error(mocker):
    """Test both the happy path and collision exceptions in file generation."""
    args = argparse.Namespace(target="cpp_class", name="Engine")
    mocker.patch("protostar.cli.ProtostarConfig.load")
    mock_print = mocker.patch("protostar.cli.console.print")

    mock_gen = mocker.Mock()
    mock_gen.execute.return_value = ["Engine.hpp"]
    mocker.patch.dict("protostar.cli.GENERATOR_REGISTRY", {"cpp_class": mock_gen})

    # Success Path
    handle_generate(args)
    assert any(
        "Generated" in str(call.args[0])
        for call in mock_print.call_args_list
        if call.args
    )

    # FileExistsError Path
    mock_gen.execute.side_effect = FileExistsError("File already exists")
    handle_generate(args)
    assert any(
        "Generation Aborted" in str(call.args[0])
        for call in mock_print.call_args_list
        if call.args
    )


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
    """Test that cancelling wizards safely exits the process and prints help."""
    parser = mocker.Mock()

    # 1. Discovery Wizard Cancellation
    mocker.patch.object(sys, "argv", ["protostar"])
    mocker.patch("protostar.cli.run_discovery_wizard", return_value=None)
    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)
    parser.print_help.assert_called_once()

    # 2. Init Wizard Cancellation
    mocker.patch.object(sys, "argv", ["protostar", "init"])
    mocker.patch("protostar.cli.run_init_wizard", return_value=None)
    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)
    parser.parse_args.assert_called_with(["init", "--help"])

    # 3. Generate Wizard Cancellation
    mocker.patch.object(sys, "argv", ["protostar", "generate"])
    mocker.patch("protostar.cli.run_generate_wizard", return_value=None)
    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)
    parser.parse_args.assert_called_with(["generate", "--help"])


def test_intercept_generate_wizard_errors(mocker):
    """Test error handling routing inside the generate TUI wrapper."""
    parser = mocker.Mock()
    mock_print = mocker.patch("protostar.cli.console.print")
    mocker.patch.object(sys, "argv", ["protostar", "generate"])

    # 1. Unknown target returned by wizard
    mocker.patch(
        "protostar.cli.run_generate_wizard",
        return_value={"target": "unknown", "name": "foo"},
    )
    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)
    assert any("Unknown target" in str(c) for c in mock_print.call_args_list)

    # 2. Target execution crash
    mock_gen = mocker.Mock()
    mock_gen.execute.side_effect = ValueError("Bad identifier")
    mocker.patch.dict("protostar.cli.GENERATOR_REGISTRY", {"cpp_class": mock_gen})
    mocker.patch(
        "protostar.cli.run_generate_wizard",
        return_value={"target": "cpp_class", "name": "foo"},
    )
    with pytest.raises(SystemExit):
        intercept_interactive_wizards(parser)
    assert any("Generation Aborted" in str(c) for c in mock_print.call_args_list)


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
    mocker.patch.object(sys, "argv", ["protostar", "init", "--python"])
    mocker.patch("protostar.cli.intercept_interactive_wizards")
    mocker.patch(
        "protostar.cli.handle_init", side_effect=ValueError("Syntax Error in TOML")
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()
    mock_exit.assert_called_once_with(1)
