import argparse
import sys
import types

import pytest
from rich.console import Group
from rich.table import Table

from protostar.cli import (
    GenerateEpilogTable,
    LazyTargetHelp,
    ProtoHelpFormatter,
    get_ide_module,
    handle_init,
    main,
    print_table_help,
)
from protostar.modules import (
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
