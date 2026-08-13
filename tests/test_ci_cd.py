from protostar.config import ProtostarConfig
from protostar.executor import SystemExecutor
from protostar.manifest import EnvironmentManifest
from protostar.modules.ci_layer import CIModule, ReleaseModule


def test_cimodule_build(manifest: EnvironmentManifest) -> None:
    mod = CIModule()
    mod.build(manifest)
    assert manifest.wants_ci is True
    assert any("workflows" in str(d) for d in manifest.directories)


def test_releasemodule_build(manifest: EnvironmentManifest) -> None:
    mod = ReleaseModule()
    mod.build(manifest)
    assert manifest.wants_release is True
    assert any("workflows" in str(d) for d in manifest.directories)


def test_executor_ci_assembly(manifest: EnvironmentManifest, mocker) -> None:
    manifest.wants_ci = True
    manifest.metadata = {
        "supported_os": ["Linux", "MacOS"],
        "minimum_python": "3.11",
    }
    manifest.ci_flags = {"pytest", "codecov"}
    manifest.ci_steps = ["      - name: Run Ruff\\n        run: uv run ruff check"]

    mock_write = mocker.patch("protostar.executor.atomic_write_text")
    executor = SystemExecutor(manifest, ProtostarConfig())
    executor._write_ci_workflow()

    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    path, content = args
    assert str(path) == ".github/workflows/ci.yml"
    assert (
        "Test on ${{ matrix.os }} with Python ${{ matrix.python-version }}" in content
    )
    assert '"ubuntu-latest", "macos-latest"' in content
    assert '"3.11", "3.12", "3.13", "3.14"' in content
    assert "name: Run Tests with Coverage" in content
    assert "name: Run Ruff" in content
    assert "name: Upload Coverage" in content


def test_executor_release_assembly(manifest: EnvironmentManifest, mocker) -> None:
    manifest.wants_release = True
    mock_write = mocker.patch("protostar.executor.atomic_write_text")
    executor = SystemExecutor(manifest, ProtostarConfig())
    executor._write_release_workflow()

    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    path, content = args
    assert str(path) == ".github/workflows/release.yml"
    assert "pypa/gh-action-pypi-publish@release/v1" in content
