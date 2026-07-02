from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.modules import (
    DirenvModule,
    MarkdownLintModule,
    PreCommitModule,
    PytestModule,
    PythonCore,
)


def test_python_module_uv_build(manifest, mocker):
    """Test Python manifest mutation prioritizes uv by default and enforces bare initialization."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Prevent IDE injection to isolate build testing
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide=None)

    mod = PythonCore(package_manager="uv")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ".ruff_cache/" not in manifest.vcs_ignores
    assert any(
        t.command
        == [
            "uv",
            "init",
            "--no-workspace",
            "--bare",
            "--pin-python",
            "--python",
            "3.13",
        ]
        for t in manifest.system_tasks
    )

    # Find the uv init task and verify its description
    task = next(t for t in manifest.system_tasks if t.command[0] == "uv")
    assert task.description == "Scaffolding uv virtual environment"


def test_python_module_uv_with_version(manifest, mocker):
    """Test Python manifest includes the specific python version flag alongside bare initialization."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide=None)

    mod = PythonCore(package_manager="uv", python_version="3.12")
    mod.build(manifest)

    assert any(
        t.command
        == [
            "uv",
            "init",
            "--no-workspace",
            "--bare",
            "--pin-python",
            "--python",
            "3.12",
        ]
        for t in manifest.system_tasks
    )


def test_python_module_ide_injection_active(manifest, mocker):
    """Test that the Python module dynamically injects the interpreter path for supported IDEs."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Mock global config to explicitly request VS Code
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide="vscode")

    mod = PythonCore(package_manager="uv")
    mod.build(manifest)

    assert "python.defaultInterpreterPath" in manifest.ide_settings
    assert "/.venv/bin/python" in manifest.ide_settings["python.defaultInterpreterPath"]
    assert manifest.ide_settings["python.terminal.activateEnvironment"] is True


def test_python_module_ide_injection_inactive(manifest, mocker):
    """Test that the Python module skips IDE injection if the preferred IDE is unsupported or None."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Mock global config to represent an unconfigured or non-VS Code state
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide=None)

    mod = PythonCore(package_manager="uv")
    mod.build(manifest)

    assert "python.defaultInterpreterPath" not in manifest.ide_settings


def test_python_module_pip_build(manifest, mocker):
    """Test Python manifest correctly initializes standard library venv for pip."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonCore(package_manager="pip")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert any(
        t.command == ["python3.13", "-m", "venv", ".venv"]
        for t in manifest.system_tasks
    )


def test_python_module_pip_with_version(manifest, mocker):
    """Test Python manifest formats the python executable correctly for pip venvs."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonCore(package_manager="pip", python_version="3.11")
    mod.build(manifest)

    assert any(
        t.command == ["python3.11", "-m", "venv", ".venv"]
        for t in manifest.system_tasks
    )


def test_python_module_pre_flight_missing_uv(mocker):
    """Test PythonCore aborts pre-flight if uv is missing."""
    mod = PythonCore(package_manager="uv")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(RuntimeError, match="Missing dependency: 'uv' is required"):
        mod.pre_flight()


def test_python_module_pre_flight_missing_pip(mocker):
    """Test PythonCore aborts pre-flight if python/python3 are missing."""
    mod = PythonCore(package_manager="pip")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(RuntimeError, match="Missing dependency: 'python' is required"):
        mod.pre_flight()


# --- DirenvModule Tests ---


def test_direnv_pre_flight_missing(mocker):
    """Test DirenvModule aborts pre-flight if direnv is missing."""
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(RuntimeError, match="direnv is not installed"):
        DirenvModule().pre_flight()


def test_direnv_collision_markers():
    assert DirenvModule().collision_markers == [Path(".envrc")]


def test_direnv_build(manifest, mocker):
    """Test DirenvModule generates the `.envrc` injection and queues evaluation."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    mod = DirenvModule()
    mod.build(manifest)

    assert ".envrc.local" in manifest.vcs_ignores
    assert ".direnv/" in manifest.vcs_ignores
    assert ".envrc" in manifest.file_injections
    assert any(t.command == ["direnv", "allow"] for t in manifest.post_install_tasks)


def test_direnv_build_file_exists(manifest, mocker):
    """Test DirenvModule skips `.envrc` injection if it already exists."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    mod = DirenvModule()
    mod.build(manifest)
    assert ".envrc" not in manifest.file_injections


# --- MarkdownLintModule Tests ---


def test_markdownlint_collision_markers():
    assert MarkdownLintModule().collision_markers == [Path(".markdownlint.yaml")]


def test_markdownlint_build(manifest, mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    mod = MarkdownLintModule()
    mod.build(manifest)

    assert ".markdownlint.yaml" in manifest.file_injections
    assert any("markdownlint-cli" in hook for hook in manifest.pre_commit_hooks)


def test_markdownlint_build_file_exists(manifest, mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    mod = MarkdownLintModule()
    mod.build(manifest)
    assert ".markdownlint.yaml" not in manifest.file_injections


# --- PytestModule Tests ---


def test_pytest_build(manifest):
    mod = PytestModule()
    mod.build(manifest)

    assert "pytest" in manifest.dev_dependencies
    assert "pytest-cov" in manifest.dev_dependencies
    assert "tests" in manifest.directories
    assert ".coverage" in manifest.workspace_hides
    assert "pyproject.toml" in manifest.file_appends


# --- PreCommitModule Tests ---


def test_pre_commit_pre_flight_missing(mocker):
    """Test PreCommitModule aborts pre-flight if git is missing."""
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(RuntimeError, match="Missing dependency: 'git'"):
        PreCommitModule().pre_flight()


def test_pre_commit_collision_markers():
    assert PreCommitModule().collision_markers == [Path(".pre-commit-config.yaml")]


def test_pre_commit_build_uv(manifest, mocker):
    """Test PreCommitModule configures standard hooks routing via uv."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    mod = PreCommitModule()
    mod.build(manifest)

    assert manifest.wants_pre_commit is True
    assert "pre-commit" in manifest.dev_dependencies
    assert any(t.command == ["git", "init"] for t in manifest.system_tasks)
    assert any(
        t.command == ["uv", "run", "pre-commit", "install"]
        for t in manifest.post_install_tasks
    )
    assert any(
        t.command == ["uv", "run", "pre-commit", "autoupdate"]
        for t in manifest.post_install_tasks
    )


def test_pre_commit_build_pip(manifest, mocker):
    """Test PreCommitModule configures standard hooks routing via pip/venv."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    mod = PreCommitModule()
    mod.build(manifest)
    assert any(
        t.command == [".venv/bin/pre-commit", "install"]
        for t in manifest.post_install_tasks
    )
