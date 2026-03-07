from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.manifest import CollisionStrategy
from protostar.modules import BootstrapModule
from protostar.orchestrator import Orchestrator
from protostar.presets.base import PresetModule


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


def test_orchestrator_lifecycle(mocker):
    """Test that the orchestrator calls pre_flight, build, and executes tasks."""
    mock_execute = mocker.patch("protostar.orchestrator.SystemExecutor.execute")
    mocker.patch("protostar.orchestrator.Orchestrator._evaluate_collisions")

    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig()

    dummy_mod = DummyModule()
    dummy_preset = DummyPreset()

    orchestrator = Orchestrator([dummy_mod], presets=[dummy_preset])
    orchestrator.run()

    assert dummy_mod.pre_flight_called is True
    assert "dummy_file.txt" in orchestrator.manifest.vcs_ignores
    assert "dummy-pkg" in orchestrator.manifest.dependencies
    assert "dummy-preset-pkg" in orchestrator.manifest.dependencies

    # Verify execution handoff
    mock_execute.assert_called_once()


def test_orchestrator_evaluate_collisions_headless_aborts_by_default(mocker):
    """Test that a headless environment safely aborts on collision without the force flag."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Simulate the marker existing and a headless environment by patching the base pathlib object
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=False)

    # Configure the mock to actually raise SystemExit, preventing fall-through
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit", side_effect=SystemExit)
    mock_console = mocker.patch("protostar.orchestrator.console.print")

    # Catch the exit to prevent it from failing the test
    with pytest.raises(SystemExit):
        orchestrator._evaluate_collisions()

    # Verify it halted the process with code 1
    mock_exit.assert_called_once_with(1)

    # Verify the warning instructs the user to use the --force flag
    printed_output = " ".join(
        call.args[0] for call in mock_console.call_args_list if call.args
    )
    assert "--force" in printed_output


def test_orchestrator_evaluate_collisions_headless_with_force_merges(mocker):
    """Test that a headless environment respects the --force flag and defaults to MERGE."""
    dummy_mod = DummyModule()

    # Initialize with the force flag enabled
    orchestrator = Orchestrator([dummy_mod], force=True)

    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=False)

    orchestrator._evaluate_collisions()

    assert orchestrator.manifest.collision_strategy == CollisionStrategy.MERGE


def test_orchestrator_evaluate_collisions_interactive_abort(mocker):
    """Test that selecting ABORT in the collision TUI triggers a safe exit."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    # Mock questionary to return ABORT
    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.ABORT

    mock_exit = mocker.patch("protostar.orchestrator.sys.exit")

    orchestrator._evaluate_collisions()
    mock_exit.assert_called_once_with(1)


def test_orchestrator_evaluate_collisions_interactive_overwrite(mocker):
    """Test that selecting OVERWRITE correctly updates the manifest strategy."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)
    mocker.patch.dict("os.environ", clear=True)

    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.OVERWRITE

    orchestrator._evaluate_collisions()
    assert orchestrator.manifest.collision_strategy == CollisionStrategy.OVERWRITE


def test_orchestrator_run_global_injections(mocker):
    """Test that global dev dependencies and pyproject injections are added in Phase 3."""
    orchestrator = Orchestrator([])

    # Mock evaluation to prevent aborts and SystemExecutor to prevent execution
    mocker.patch.object(orchestrator, "_evaluate_collisions")
    mocker.patch("protostar.orchestrator.SystemExecutor.execute")

    # Mock the global configuration
    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value.global_dev_dependencies = ["test-global-dep"]
    mock_config.return_value.pyproject_injections = {"custom_key": "custom_payload"}

    orchestrator.run()

    assert "test-global-dep" in orchestrator.manifest.dev_dependencies
    assert "custom_payload" in orchestrator.manifest.file_appends["pyproject.toml"]


def test_orchestrator_run_known_exception(mocker):
    """Test that known exceptions (e.g. FileExistsError) abort cleanly without stack traces."""
    orchestrator = Orchestrator([])
    mocker.patch.object(
        orchestrator, "_evaluate_collisions", side_effect=FileExistsError("Known error")
    )
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.orchestrator.console.print")

    with pytest.raises(SystemExit):
        orchestrator.run()

    mock_exit.assert_called_once_with(1)
    printed = " ".join(
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], str)
    )
    assert "ABORTED" in printed
    assert "Known error" in printed


def test_orchestrator_run_unknown_exception(mocker):
    """Test that unknown exceptions trigger the telemetry generation URL and full traceback."""
    orchestrator = Orchestrator([])
    mocker.patch.object(
        orchestrator, "_evaluate_collisions", side_effect=KeyError("Unknown crash")
    )
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.orchestrator.console.print")

    with pytest.raises(SystemExit):
        orchestrator.run()

    mock_exit.assert_called_once_with(1)
    printed = " ".join(
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], str)
    )
    assert "CRITICAL FAILURE" in printed
    assert "https://github.com/" in printed


def test_orchestrator_run_partial_success(mocker):
    """Test that populated warnings trigger the PARTIAL SUCCESS terminal output."""
    orchestrator = Orchestrator([])
    mocker.patch.object(orchestrator, "_evaluate_collisions")

    # Mock SystemExecutor to simulate warnings surfaced during execution
    mock_executor_class = mocker.patch("protostar.orchestrator.SystemExecutor")
    mock_executor_instance = mock_executor_class.return_value
    mock_executor_instance.warnings = ["Mocked resolution failure"]

    mock_print = mocker.patch("protostar.orchestrator.console.print")

    orchestrator.run()

    printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
    assert "PARTIAL SUCCESS" in printed_text
    assert "Mocked resolution failure" in printed_text
