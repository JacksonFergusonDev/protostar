import argparse

from protostar.cli import get_ide_module, handle_init
from protostar.modules import JetBrainsModule, PythonModule, VSCodeModule
from protostar.presets import (
    AstroPreset,
    DspPreset,
    EmbeddedPreset,
    ScientificPreset,
)


def test_handle_init_dispatch(mocker):
    """Test that dynamically generated CLI flags instantiate modules and presets."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch("protostar.cli.get_os_module")
    mocker.patch("protostar.cli.get_ide_module", return_value=None)

    # Simulate running `proto init -p -s -a -d -e --docker --direnv --python-version 3.12`
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
        direnv=True,
        python_version="3.12",
    )

    handle_init(args)

    # Extract the arguments passed to Orchestrator(modules, presets, docker=...)
    modules = mock_orchestrator.call_args[0][0]
    presets = mock_orchestrator.call_args[0][1]
    kwargs = mock_orchestrator.call_args[1]

    # Verify Language Module and Version injection
    python_mod = next((m for m in modules if isinstance(m, PythonModule)), None)
    assert python_mod is not None
    assert python_mod.python_version == "3.12"

    # Verify Presets
    assert any(isinstance(p, ScientificPreset) for p in presets)
    assert any(isinstance(p, AstroPreset) for p in presets)
    assert any(isinstance(p, DspPreset) for p in presets)
    assert any(isinstance(p, EmbeddedPreset) for p in presets)

    # Verify Context Artifact Flags
    assert kwargs.get("docker") is True
    assert kwargs.get("direnv") is True


def test_get_ide_module_dispatch():
    """Test that IDE aliases correctly resolve to their respective module classes."""
    vscode_mod = get_ide_module("cursor")
    assert isinstance(vscode_mod, VSCodeModule)

    jetbrains_mod = get_ide_module("jetbrains")
    assert isinstance(jetbrains_mod, JetBrainsModule)

    unknown_mod = get_ide_module("eclipse")
    assert unknown_mod is None
