import json

from protostar.config import ProtostarConfig
from protostar.modules import BootstrapModule
from protostar.orchestrator import Orchestrator
from protostar.presets.base import PresetModule


class DummyModule(BootstrapModule):
    """A mock module for testing the orchestrator lifecycle."""

    @property
    def name(self):
        return "Dummy"

    def pre_flight(self):
        self.pre_flight_called = True

    def build(self, manifest):
        manifest.add_vcs_ignore("dummy_file.txt")
        manifest.add_system_task(["echo", "dummy"])
        manifest.add_dependency("dummy-pkg")


class DummyPreset(PresetModule):
    """A mock preset for testing the orchestrator lifecycle."""

    @property
    def name(self):
        return "DummyPreset"

    def build(self, manifest):
        manifest.add_dependency("dummy-preset-pkg")


def test_orchestrator_lifecycle(mocker):
    """Test that the orchestrator calls pre_flight, build, and executes tasks."""
    mock_run_quiet = mocker.patch("protostar.orchestrator.run_quiet")
    mocker.patch("protostar.orchestrator.Orchestrator._write_injected_files")
    mocker.patch("protostar.orchestrator.Orchestrator._write_pre_commit_config")
    mocker.patch("protostar.orchestrator.Orchestrator._write_ignores")
    mocker.patch("protostar.orchestrator.Orchestrator._write_docker_artifacts")
    mocker.patch("protostar.orchestrator.Orchestrator._write_ide_settings")

    # Mock the global config lookup inside _install_dependencies
    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    dummy_mod = DummyModule()
    dummy_preset = DummyPreset()

    # Pass both the module and the preset
    orchestrator = Orchestrator([dummy_mod], presets=[dummy_preset])

    orchestrator.run()

    assert dummy_mod.pre_flight_called is True
    assert "dummy_file.txt" in orchestrator.manifest.vcs_ignores

    # Verify tasks and dependencies were executed (1 from module, 1 from preset)
    mock_run_quiet.assert_any_call(["echo", "dummy"], "Executing echo")
    mock_run_quiet.assert_any_call(
        ["uv", "add", "dummy-pkg", "dummy-preset-pkg"],
        "Resolving and installing 2 dependencies",
    )


def test_orchestrator_writes_injected_files(mocker):
    """Test that the orchestrator flushes queued file injections to disk."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.add_file_injection(".test_config.yaml", "mock content")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)
    mock_mkdir = mocker.patch("protostar.orchestrator.Path.mkdir")
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_injected_files()

    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_write.assert_called_once_with("mock content")


def test_orchestrator_install_dependencies_uv(mocker):
    """Test that the orchestrator uses uv add --dev for dev dependencies."""
    mock_run_quiet = mocker.patch("protostar.orchestrator.run_quiet")
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)

    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    orchestrator.manifest.add_dependency("fastapi")
    orchestrator.manifest.add_dev_dependency("pytest")

    orchestrator._install_dependencies()

    mock_run_quiet.assert_any_call(
        ["uv", "add", "fastapi"],
        "Resolving and installing 1 dependencies",
    )
    mock_run_quiet.assert_any_call(
        ["uv", "add", "--dev", "pytest"],
        "Resolving and installing 1 development dependencies",
    )


def test_orchestrator_install_dependencies_pip_freeze(mocker):
    """Test that the orchestrator executes a local pip installation and writes a freeze state."""
    mock_run_quiet = mocker.patch("protostar.orchestrator.run_quiet")
    mock_run = mocker.patch("protostar.orchestrator.subprocess.run")
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)

    # Mock config to force pip route
    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    mock_run.return_value.stdout = "dummy-pkg==1.0.0\ndev-pkg==2.0.0"

    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Manually populate the manifest
    orchestrator.manifest.add_dependency("dummy-pkg")
    orchestrator.manifest.add_dev_dependency("dev-pkg")

    orchestrator._install_dependencies()

    # Pip lacks native dev dependency segregation, so they are installed collectively
    mock_run_quiet.assert_called_once_with(
        [".venv/bin/pip", "install", "dummy-pkg", "dev-pkg"],
        "Resolving and installing 2 total dependencies",
    )

    mock_run.assert_called_once_with(
        [".venv/bin/pip", "freeze"], capture_output=True, text=True, check=True
    )
    mock_write.assert_called_once_with("dummy-pkg==1.0.0\ndev-pkg==2.0.0")


def test_orchestrator_append_files_late_binding(mocker):
    """Test that configuration payloads are interpolated with the active python version."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    orchestrator.manifest.add_file_append(
        "pyproject.toml", 'python_version = "{{PYTHON_VERSION}}"'
    )

    # Mock pyproject.toml existing and containing a requires-python metadata string
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text",
        return_value='requires-python = ">=3.11"\n',
    )

    mock_file = mocker.mock_open()
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    orchestrator._append_files()

    written_data = mock_file().write.call_args[0][0]
    # Verify the regex successfully extracted '3.11' and interpolated the {{PYTHON_VERSION}} token
    assert 'python_version = "3.11"' in written_data


def test_orchestrator_writes_pre_commit_config(mocker):
    """Test that the orchestrator concatenates hooks and interpolates Mypy dependencies."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # 1. Flag activation and populate dynamic dependencies
    orchestrator.manifest.wants_pre_commit = True
    orchestrator.manifest.add_dependency("fastapi")
    orchestrator.manifest.add_dev_dependency("pytest")

    # 2. Queue a hook with the interpolation token
    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
{{MYPY_DEPENDENCIES}}"""
    orchestrator.manifest.add_pre_commit_hook(hook_payload)

    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_pre_commit_config()

    # Verify what was written to the .pre-commit-config.yaml file
    written_data = mock_write.call_args[0][0]

    # Verify base hooks were prepended
    assert "trailing-whitespace" in written_data
    # Verify the target hook was appended
    assert "id: mypy" in written_data

    # Verify the dependency token was successfully evaluated and formatted
    assert "{{MYPY_DEPENDENCIES}}" not in written_data
    assert "- fastapi" in written_data
    assert "- pytest" in written_data


def test_orchestrator_writes_dockerignore(mocker):
    """Test that the orchestrator aggregates base ignores and vcs ignores for docker."""
    dummy_mod = DummyModule()

    # Initialize with the docker flag set to True
    orchestrator = Orchestrator([dummy_mod], docker=True)
    orchestrator.manifest.add_vcs_ignore("custom_build_artifact/")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.Path.read_text", return_value=".env\n")

    mock_file = mocker.mock_open()
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    orchestrator._write_docker_artifacts()

    # Verify what was written to the .dockerignore file
    written_data = mock_file().write.call_args[0][0]

    # Should contain our custom manifest ignore
    assert "custom_build_artifact/" in written_data

    # Should contain the standard daemon exclusions appended by the orchestrator
    assert ".git/" in written_data
    assert "README*" in written_data


def test_orchestrator_writes_gitignore(mocker):
    """Test that .gitignore is safely updated without duplicating existing lines."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.add_vcs_ignore("new_ignore.txt")

    # Patch Path methods directly to avoid Path division (__truediv__) mock issues
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text", return_value="existing_ignore.txt\n"
    )

    # Use mocker.mock_open to correctly simulate the file context manager
    mock_file = mocker.mock_open()
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    orchestrator._write_ignores()

    # Since the mock file content already ends with \n, the prefix is empty.
    mock_file().write.assert_called_once_with("new_ignore.txt\n")


def test_orchestrator_writes_vscode_settings(mocker):
    """Test that IDE settings merge correctly with existing JSON."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.add_ide_setting("files.exclude", {"**/.venv": True})

    existing_settings = {"search.exclude": {"**/node_modules": True}}

    # Patch Path methods directly
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text",
        return_value=json.dumps(existing_settings),
    )
    mock_write_text = mocker.patch("protostar.orchestrator.Path.write_text")
    mocker.patch("protostar.orchestrator.Path.mkdir")  # Prevent physical dir creation

    orchestrator._write_ide_settings()

    # Verify the write_text call contains both the old and new keys
    written_data = mock_write_text.call_args[0][0]
    parsed_write = json.loads(written_data)

    assert "**/.venv" in parsed_write["files.exclude"]
    assert "**/node_modules" in parsed_write["search.exclude"]


def test_orchestrator_creates_directories(mocker):
    """Test that the orchestrator generates all requested workspace directories."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Queue directory scaffolding
    orchestrator.manifest.add_directory("data")
    orchestrator.manifest.add_directory("src/core")

    mock_mkdir = mocker.patch("protostar.orchestrator.Path.mkdir")

    orchestrator._create_directories()

    assert mock_mkdir.call_count == 2
    mock_mkdir.assert_any_call(parents=True, exist_ok=True)
