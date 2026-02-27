import argparse

from protostar.cli import handle_init
from protostar.modules import PythonModule
from protostar.presets import (
    AstroPreset,
    DspPreset,
    EmbeddedPreset,
    ScientificPreset,
)


def test_handle_init_dispatch(mocker):
    """Test that CLI flags correctly instantiate modules, presets, and docker settings."""
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch("protostar.cli.get_os_module")
    mocker.patch("protostar.cli.get_ide_module", return_value=None)

    # Simulate running `proto init -p -s -a -d -e --docker`
    args = argparse.Namespace(
        python=True,
        rust=False,
        node=False,
        cpp=False,
        latex=False,
        scientific=True,
        astro=True,
        dsp=True,
        embedded=True,
        docker=True,
    )

    handle_init(args)

    # Extract the arguments passed to Orchestrator(modules, presets, docker=...)
    modules = mock_orchestrator.call_args[0][0]
    presets = mock_orchestrator.call_args[0][1]
    kwargs = mock_orchestrator.call_args[1]

    # Verify Language Module
    assert any(isinstance(m, PythonModule) for m in modules)

    # Verify Presets
    assert any(isinstance(p, ScientificPreset) for p in presets)
    assert any(isinstance(p, AstroPreset) for p in presets)
    assert any(isinstance(p, DspPreset) for p in presets)
    assert any(isinstance(p, EmbeddedPreset) for p in presets)

    # Verify Context Artifact Flags
    assert kwargs.get("docker") is True
