import argparse

from protostar.cli import handle_init
from protostar.modules import PythonModule


def test_scientific_init_hook(mocker):
    """Test the --scientific flag injects data directories and vcs ignores."""
    # Mock Orchestrator to intercept the built manifest before execution
    mock_orchestrator = mocker.patch("protostar.cli.Orchestrator")
    mocker.patch("protostar.cli.get_os_module")
    mocker.patch("protostar.cli.get_ide_module", return_value=None)
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    args = argparse.Namespace(
        python=True,
        scientific=True,
        rust=False,
        node=False,
        cpp=False,
        latex=False,
    )

    handle_init(args)

    # Extract the modules list passed to the Orchestrator
    modules = mock_orchestrator.call_args[0][0]
    python_mod = next(m for m in modules if isinstance(m, PythonModule))

    # Manually execute the hooked build sequence against a mock manifest
    from protostar.manifest import EnvironmentManifest

    manifest = EnvironmentManifest()
    python_mod.build(manifest)

    # Verify data pipeline architecture was injected
    assert "astropy" in manifest.dependencies
    assert "data" in manifest.directories
    assert "notebooks" in manifest.directories

    # Verify binary data formats are excluded from VCS
    assert "*.csv" in manifest.vcs_ignores
    assert "*.parquet" in manifest.vcs_ignores
    assert "*.nc" in manifest.vcs_ignores
