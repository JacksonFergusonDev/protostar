from protostar.config import UserConfig
from protostar.executor import SystemExecutor
from protostar.manifest import EnvironmentManifest
from protostar.modules.ci_layer import CIModule, ReleaseModule


def test_cimodule_build(manifest: EnvironmentManifest) -> None:
    mod = CIModule()
    mod.build(manifest)
    assert manifest.tooling.wants_ci is True
    assert any("workflows" in str(d) for d in manifest.filesystem.directories)


def test_releasemodule_build(manifest: EnvironmentManifest) -> None:
    mod = ReleaseModule()
    mod.build(manifest)
    assert manifest.tooling.wants_release is True
    assert any("workflows" in str(d) for d in manifest.filesystem.directories)


def test_executor_ci_assembly(manifest: EnvironmentManifest, mocker) -> None:
    manifest.tooling.wants_ci = True
    manifest.metadata = {
        "supported_os": ["Linux", "MacOS"],
        "minimum_python": "3.11",
    }
    manifest.tooling.ci_flags = {"pytest", "codecov"}
    manifest.tooling.ci_steps = [
        "      - name: Run Ruff\\n        run: uv run ruff check"
    ]

    mock_write = mocker.patch("protostar.executor.atomic_write_text")
    executor = SystemExecutor(manifest, UserConfig())
    executor._write_ci_workflow()

    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    path, content = args
    assert path.as_posix() == ".github/workflows/ci.yml"
    assert (
        "Test on ${{ matrix.os }} with Python ${{ matrix.python-version }}" in content
    )
    assert '"ubuntu-latest", "macos-latest"' in content
    assert '"3.11", "3.12", "3.13", "3.14"' in content
    assert "name: Run tests with coverage # (for Codecov)" in content
    assert "name: Lint & Type Check" in content
    assert "coverage: true" in content
    assert "if: matrix.coverage" in content
    assert "if: ${{ !matrix.coverage }}" in content
    assert "name: Run Ruff" in content
    assert "name: Upload coverage to Codecov" in content
    assert "name: Upload test analytics to Codecov" in content


def test_executor_ci_assembly_no_codecov(manifest: EnvironmentManifest, mocker) -> None:
    manifest.tooling.wants_ci = True
    manifest.metadata = {
        "supported_os": ["Linux"],
        "minimum_python": "3.11",
    }
    manifest.tooling.ci_flags = {"pytest"}
    manifest.tooling.ci_steps = [
        "      - name: Run Ruff\\n        run: uv run ruff check"
    ]

    mock_write = mocker.patch("protostar.executor.atomic_write_text")
    executor = SystemExecutor(manifest, UserConfig())
    executor._write_ci_workflow()

    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    _path, content = args
    assert "name: Run tests with coverage" not in content
    assert "name: Run Tests" in content
    assert "Upload coverage to Codecov" not in content
    assert "coverage: true" not in content


def test_executor_ci_assembly_no_pytest(manifest: EnvironmentManifest, mocker) -> None:
    manifest.tooling.wants_ci = True
    manifest.metadata = {
        "supported_os": ["Linux"],
        "minimum_python": "3.11",
    }
    manifest.tooling.ci_flags = set()
    manifest.tooling.ci_steps = [
        "      - name: Run Ruff\\n        run: uv run ruff check"
    ]

    mock_write = mocker.patch("protostar.executor.atomic_write_text")
    executor = SystemExecutor(manifest, UserConfig())
    executor._write_ci_workflow()

    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    _path, content = args
    assert "name: Run Tests" not in content


def test_executor_release_assembly(manifest: EnvironmentManifest, mocker) -> None:
    manifest.tooling.wants_release = True
    mock_write = mocker.patch("protostar.executor.atomic_write_text")
    executor = SystemExecutor(manifest, UserConfig())
    executor._write_release_workflow()

    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    path, content = args
    assert path.as_posix() == ".github/workflows/release.yml"
    assert "pypa/gh-action-pypi-publish@release/v1" in content
