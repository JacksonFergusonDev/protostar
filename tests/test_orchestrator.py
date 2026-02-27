import json

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
    mocker.patch("protostar.orchestrator.Orchestrator._write_ignores")
    mocker.patch("protostar.orchestrator.Orchestrator._write_docker_artifacts")
    mocker.patch("protostar.orchestrator.Orchestrator._write_ide_settings")

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
