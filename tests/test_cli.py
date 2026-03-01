import argparse

from protostar.cli import get_ide_module, handle_init
from protostar.modules import (
    DirenvModule,
    JetBrainsModule,
    MarkdownLintModule,
    MypyModule,
    PytestModule,
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
