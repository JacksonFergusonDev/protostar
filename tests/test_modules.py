import pytest

from protostar.config import ProtostarConfig
from protostar.modules import PythonCore


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
