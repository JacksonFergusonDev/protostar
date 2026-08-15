from pathlib import Path

import pytest

from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import ExecutionAbortedError, ProtostarError
from protostar.manifest import CollisionStrategy, Severity
from protostar.modules import BootstrapModule
from protostar.orchestrator import Orchestrator


@pytest.fixture
def mock_config() -> UserConfig:
    """Provides a fresh baseline configuration for DI injections."""
    return UserConfig()


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


def test_orchestrator_lifecycle(mocker, mock_config):
    """Test that the orchestrator calls pre_flight, build, and executes tasks."""
    mock_execute = mocker.patch("protostar.orchestrator.SystemExecutor.execute")
    mocker.patch("protostar.orchestrator.Orchestrator._evaluate_collisions")

    dummy_mod = DummyModule()

    orchestrator = Orchestrator([dummy_mod], mock_config)
    orchestrator.run()

    assert dummy_mod.pre_flight_called
    mock_execute.assert_called_once()


def test_orchestrator_evaluate_collisions_headless_aborts_by_default(
    mocker, mock_config
):
    """Test that a headless environment safely aborts on collision without the force flag."""
    # Assuming DummyModule is defined in your test file
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    # Simulate the marker existing and a headless environment by mocking the property
    marker = mocker.MagicMock()
    marker.exists.return_value = True
    marker.__str__.return_value = "dummy_marker.txt"
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )
    mocker.patch("protostar.orchestrator.is_interactive", return_value=False)

    # The orchestrator should raise a ProtostarError directly instead of printing/exiting
    with pytest.raises(ProtostarError, match="--force"):
        orchestrator._evaluate_collisions()


def test_orchestrator_evaluate_collisions_headless_with_force_merges(
    mocker, mock_config
):
    """Test that a headless environment respects the --force flag and defaults to MERGE."""
    dummy_mod = DummyModule()

    # Initialize with the force flag enabled
    orchestrator = Orchestrator([dummy_mod], mock_config, force_merge=True)

    marker = mocker.MagicMock()
    marker.exists.return_value = True
    marker.__str__.return_value = "dummy_marker.txt"
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )
    mocker.patch("protostar.orchestrator.is_interactive", return_value=False)

    orchestrator._evaluate_collisions()

    assert orchestrator.manifest.collision_strategy == CollisionStrategy.MERGE


def test_orchestrator_evaluate_collisions_interactive_abort(mocker, mock_config):
    """Test that selecting ABORT in the collision TUI triggers a safe exit."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    marker = mocker.MagicMock()
    marker.exists.return_value = True
    marker.__str__.return_value = "dummy_marker.txt"
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )
    mocker.patch("protostar.orchestrator.is_interactive", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    # Mock questionary to return ABORT
    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.ABORT

    with pytest.raises(
        ExecutionAbortedError, match=r"Environment initialization cancelled by user\."
    ):
        orchestrator._evaluate_collisions()


def test_orchestrator_evaluate_collisions_interactive_cancellation(mocker, mock_config):
    """Test that cancelling the collision prompt (Ctrl+C / Esc) raises ExecutionAbortedError."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    marker = mocker.MagicMock()
    marker.exists.return_value = True
    marker.__str__.return_value = "dummy_marker.txt"
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )
    mocker.patch("protostar.orchestrator.is_interactive", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Environment initialization cancelled by user\."
    ):
        orchestrator._evaluate_collisions()


def test_orchestrator_evaluate_collisions_interactive_overwrite(mocker, mock_config):
    """Test that selecting OVERWRITE correctly updates the manifest strategy."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod], mock_config)

    marker = mocker.MagicMock()
    marker.exists.return_value = True
    marker.__str__.return_value = "dummy_marker.txt"
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )
    mocker.patch("protostar.orchestrator.is_interactive", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.OVERWRITE

    orchestrator._evaluate_collisions()
    assert orchestrator.manifest.collision_strategy == CollisionStrategy.OVERWRITE


def test_orchestrator_run_global_injections(mocker, mock_config):
    mock_bp = TemplateBlueprint(dev_dependencies=["test-global-dep"])
    mock_bp.pyproject_injections = {"custom_key": "custom_payload"}

    orchestrator = Orchestrator([], mock_config, blueprint=mock_bp)

    # Mock evaluation to prevent aborts and SystemExecutor to prevent execution
    mocker.patch.object(orchestrator, "_evaluate_collisions")
    mocker.patch("protostar.orchestrator.SystemExecutor.execute")

    orchestrator.run()

    assert "test-global-dep" in orchestrator.manifest.dev_dependencies


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


def test_orchestrator_runs_cleanly_without_warnings(mocker) -> None:
    """Test that the orchestrator evaluates a valid configuration without raising diagnostics."""
    # 1. Create a pristine config instance
    config = UserConfig()

    # 2. Mock execution boundaries to isolate the test
    mocker.patch("protostar.orchestrator.SystemExecutor")

    orchestrator = Orchestrator(modules=[], user_config=config)

    # Mock collision evaluation so it doesn't try to prompt or abort in the sandbox
    mocker.patch.object(orchestrator, "_evaluate_collisions")

    # 3. Run the orchestrator
    orchestrator.run()

    # 4. Verify no diagnostic events were generated, confirming strict evaluation passed
    assert len(orchestrator.manifest.diagnostics) == 0


def test_orchestrator_panel_rendering(mocker, capsys) -> None:
    # 1. Inject a diagnostic event directly into an empty orchestrator
    config = UserConfig()
    orchestrator = Orchestrator(modules=[], user_config=config)

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


def test_orchestrator_injects_files_from_config(mocker):
    blueprint = TemplateBlueprint(files={"src/main.py": "print('hello')"})

    # Patch the method directly on the source class to guarantee interception,
    # preventing the real SystemExecutor from polluting the host disk.
    mocker.patch("protostar.executor.SystemExecutor.execute")

    orchestrator = Orchestrator(
        modules=[], user_config=UserConfig(), blueprint=blueprint
    )
    orchestrator.run()

    assert "src/main.py" in orchestrator.manifest.file_injections
