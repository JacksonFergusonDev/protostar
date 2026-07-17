from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.errors import ProtostarError
from protostar.manifest import CollisionStrategy, Severity
from protostar.modules import BootstrapModule
from protostar.orchestrator import Orchestrator
from protostar.presets.base import PresetModule


@pytest.fixture
def mock_config() -> ProtostarConfig:
    """Provides a fresh baseline configuration for DI injections."""
    return ProtostarConfig()


class DummyModule(BootstrapModule):
    """A mock module for testing the orchestrator lifecycle."""

    @property
    def name(self):
        return "Dummy"

    @property
    def collision_markers(self):
        return [Path("dummy_marker.txt")]

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


def test_orchestrator_lifecycle(mocker, mock_config):
    """Test that the orchestrator calls pre_flight, build, and executes tasks."""
    mock_execute = mocker.patch("protostar.orchestrator.SystemExecutor.execute")
    mocker.patch("protostar.orchestrator.Orchestrator._evaluate_collisions")

    dummy_mod = DummyModule()
    dummy_preset = DummyPreset()

    orchestrator = Orchestrator([dummy_mod], mock_config, presets=[dummy_preset])
    orchestrator.run()

    assert dummy_mod.pre_flight_called is True
    assert "dummy_file.txt" in orchestrator.manifest.vcs_ignores
    assert "dummy-pkg" in orchestrator.manifest.dependencies
    assert "dummy-preset-pkg" in orchestrator.manifest.dependencies

    # Verify execution handoff
    mock_execute.assert_called_once()


def test_orchestrator_evaluate_collisions_headless_aborts_by_default(
    mocker, mock_config
):
    """Test that a headless environment safely aborts on collision without the force flag."""
    # Assuming DummyModule is defined in your test file
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    # Simulate the marker existing and a headless environment by patching the base pathlib object
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=False)

    # The orchestrator should raise a ProtostarError directly instead of printing/exiting
    with pytest.raises(ProtostarError, match="--force"):
        orchestrator._evaluate_collisions()


def test_orchestrator_evaluate_collisions_headless_with_force_merges(
    mocker, mock_config
):
    """Test that a headless environment respects the --force flag and defaults to MERGE."""
    dummy_mod = DummyModule()

    # Initialize with the force flag enabled
    orchestrator = Orchestrator([dummy_mod], mock_config, force=True)

    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=False)

    orchestrator._evaluate_collisions()

    assert orchestrator.manifest.collision_strategy == CollisionStrategy.MERGE


def test_orchestrator_evaluate_collisions_interactive_abort(mocker, mock_config):
    """Test that selecting ABORT in the collision TUI triggers a safe exit."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    # Mock questionary to return ABORT
    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.ABORT

    mock_exit = mocker.patch("protostar.orchestrator.sys.exit")

    orchestrator._evaluate_collisions()
    mock_exit.assert_called_once_with(1)


def test_orchestrator_evaluate_collisions_interactive_overwrite(mocker, mock_config):
    """Test that selecting OVERWRITE correctly updates the manifest strategy."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.OVERWRITE

    orchestrator._evaluate_collisions()
    assert orchestrator.manifest.collision_strategy == CollisionStrategy.OVERWRITE


def test_orchestrator_run_global_injections(mocker, mock_config):
    """Test that global dev dependencies and pyproject injections are added in Phase 3."""
    mock_config.global_dev_dependencies = ["test-global-dep"]
    mock_config.pyproject_injections = {"custom_key": "custom_payload"}

    orchestrator = Orchestrator([], mock_config)

    # Mock evaluation to prevent aborts and SystemExecutor to prevent execution
    mocker.patch.object(orchestrator, "_evaluate_collisions")
    mocker.patch("protostar.orchestrator.SystemExecutor.execute")

    orchestrator.run()

    assert "test-global-dep" in orchestrator.manifest.dev_dependencies
    assert "custom_payload" in orchestrator.manifest.file_appends["pyproject.toml"]


def test_orchestrator_run_partial_success(mocker, mock_config):
    """Test that populated warnings trigger the PARTIAL SUCCESS terminal output."""
    orchestrator = Orchestrator([], mock_config)
    mocker.patch.object(orchestrator, "_evaluate_collisions")
    mocker.patch("protostar.orchestrator.SystemExecutor")

    # Inject a warning directly into the manifest
    orchestrator.manifest.add_diagnostic(
        phase="Executor",
        message="Mocked resolution failure",
        severity=Severity.WARNING,
    )

    mock_print = mocker.patch("protostar.orchestrator.console.print")

    orchestrator.run()

    # Safely extract text only from print calls that actually contained arguments
    printed_text = " ".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "PARTIAL SUCCESS" in printed_text


def test_orchestrator_transfers_config_warnings(mocker) -> None:
    # 1. Create a config with a cached parsing warning
    config = ProtostarConfig()
    config._parsing_warnings = ["A simulated configuration warning."]

    # 2. Mock execution boundaries to isolate the test
    mocker.patch("protostar.orchestrator.SystemExecutor")

    orchestrator = Orchestrator(modules=[], config=config)

    # Mock collision evaluation so it doesn't try to prompt or abort
    mocker.patch.object(orchestrator, "_evaluate_collisions")

    # 3. Run the orchestrator
    orchestrator.run()

    # 4. Verify the warning was transferred to the manifest correctly
    assert len(orchestrator.manifest.diagnostics) == 1
    event = orchestrator.manifest.diagnostics[0]

    assert event.phase == "Config"
    assert event.message == "A simulated configuration warning."
    assert event.severity == Severity.WARNING


def test_orchestrator_panel_rendering(mocker, capsys) -> None:
    # 1. Inject a diagnostic event directly into an empty orchestrator
    config = ProtostarConfig()
    orchestrator = Orchestrator(modules=[], config=config)

    mocker.patch("protostar.orchestrator.SystemExecutor")
    mocker.patch.object(orchestrator, "_evaluate_collisions")

    orchestrator.run()

    # No diagnostics = SUCCESS output
    captured = capsys.readouterr()
    assert "SUCCESS" in captured.out
    assert "PARTIAL SUCCESS" not in captured.out
    assert "Diagnostic Summary" not in captured.out

    # 2. Add a warning and re-run
    orchestrator.manifest.add_diagnostic(
        phase="Test", message="Simulated warning", severity=Severity.WARNING
    )
    orchestrator.run()

    captured = capsys.readouterr()
    assert "Diagnostic Summary" in captured.out
    assert "Simulated warning" in captured.out
    assert "PARTIAL SUCCESS" in captured.out
