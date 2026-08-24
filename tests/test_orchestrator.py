from pathlib import Path

import pytest

from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import PartialExecutionAbortedError, WorkspaceCollisionError
from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    EnvironmentManifest,
    Severity,
)
from protostar.models import ExecutionResult, InitRequest
from protostar.modules import BootstrapModule
from protostar.orchestrator import Orchestrator


@pytest.fixture
def mock_config() -> UserConfig:
    return UserConfig()


class DummyModule(BootstrapModule):
    @property
    def name(self):
        return "Dummy"

    @property
    def collision_markers(self):
        return [Path("dummy_marker.txt")]

    def pre_flight(self):
        self.pre_flight_called = True

    def build(self, manifest):
        manifest.filesystem.add_vcs_ignore("dummy_file.txt")
        manifest.tasks.add_system_task(["echo", "dummy"])
        manifest.dependencies.add("dummy-pkg")


# ---------------------------------------------------------------------------
# plan() tests
# ---------------------------------------------------------------------------


def test_plan_calls_pre_flight_and_build(mocker, mock_config):
    """plan() should invoke pre_flight and build on each module."""
    dummy_mod = DummyModule()
    engine = Orchestrator([dummy_mod], mock_config)

    # No collision markers exist — plan should succeed
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert dummy_mod.pre_flight_called
    assert "dummy-pkg" in manifest.dependencies.dependencies


def test_plan_raises_on_collision_without_force_flag(mocker, mock_config):
    """plan() raises WorkspaceCollisionError when markers exist and no force flag is set."""
    dummy_mod = DummyModule()
    engine = Orchestrator([dummy_mod], mock_config)

    marker = mocker.MagicMock(spec=Path)
    marker.exists.return_value = True
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert marker in exc_info.value.paths


def test_plan_force_replace_sets_overwrite_strategy(mocker, mock_config):
    """plan() resolves collisions to OVERWRITE when force_replace=True."""
    dummy_mod = DummyModule()
    engine = Orchestrator(
        [dummy_mod], mock_config, request=InitRequest(force_replace=True)
    )

    marker = mocker.MagicMock(spec=Path)
    marker.exists.return_value = True
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.OVERWRITE


def test_plan_force_merge_sets_merge_strategy(mocker, mock_config):
    """plan() resolves collisions to MERGE when force_merge=True."""
    dummy_mod = DummyModule()
    engine = Orchestrator(
        [dummy_mod], mock_config, request=InitRequest(force_merge=True)
    )

    marker = mocker.MagicMock(spec=Path)
    marker.exists.return_value = True
    mocker.patch.object(
        DummyModule,
        "collision_markers",
        new_callable=mocker.PropertyMock,
        return_value=[marker],
    )

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_plan_returns_fresh_manifest_on_each_call(mocker, mock_config):
    """Calling plan() twice must return independent EnvironmentManifest instances."""
    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)

    m1 = engine.plan()
    m2 = engine.plan()

    assert m1 is not m2


def test_plan_injects_blueprint_fields(mocker, mock_config):
    """plan() injects dependencies, directories, and file injections from the blueprint."""
    blueprint = TemplateBlueprint(
        dependencies=["fastapi"],
        dev_dependencies=["pytest"],
        files={"src/main.py": "print('hello')"},
    )
    engine = Orchestrator(
        [], mock_config, request=InitRequest(template_blueprint=blueprint)
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert "fastapi" in manifest.dependencies.dependencies
    assert "pytest" in manifest.dependencies.dev_dependencies
    assert "src/main.py" in manifest.filesystem.file_injections


def test_plan_injects_pyproject_injections_from_blueprint(mocker, mock_config):
    """plan() injects pyproject.toml payloads from blueprint.pyproject_injections."""
    blueprint = TemplateBlueprint(dev_dependencies=["test-global-dep"])
    blueprint.pyproject_injections = {"custom_key": "custom_payload"}

    engine = Orchestrator(
        [], mock_config, request=InitRequest(template_blueprint=blueprint)
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert "test-global-dep" in manifest.dependencies.dev_dependencies
    assert "custom_payload" in manifest.filesystem.file_appends.get(
        "pyproject.toml", []
    )


def test_plan_produces_clean_blueprint(mocker, mock_config):
    """plan() produces a pure declarative blueprint with no runtime diagnostic state."""
    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert not hasattr(manifest, "diagnostics")


# ---------------------------------------------------------------------------
# execute() tests
# ---------------------------------------------------------------------------


def test_execute_calls_system_executor(mocker, mock_config):
    """execute() invokes SystemExecutor.execute() exactly once."""
    mock_executor = mocker.patch("protostar.orchestrator.SystemExecutor")

    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)
    manifest = engine.plan()

    result = engine.execute(manifest)

    mock_executor.return_value.execute.assert_called_once()
    assert isinstance(result, ExecutionResult)


def test_execute_returns_touched_paths_and_diagnostics(mocker, mock_config):
    """execute() wraps touched_paths and diagnostics into an ExecutionResult."""
    mock_executor_cls = mocker.patch("protostar.orchestrator.SystemExecutor")
    mock_executor_instance = mock_executor_cls.return_value
    mock_executor_instance.touched_paths = {"pyproject.toml"}
    mock_executor_instance.diagnostics = [
        DiagnosticEvent(phase="Test", message="something", severity=Severity.INFO)
    ]

    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)
    manifest = engine.plan()

    result = engine.execute(manifest)

    assert "pyproject.toml" in result.touched_paths
    assert result.diagnostics[0].message == "something"


def test_execute_raises_partial_abort_on_keyboard_interrupt(mocker, mock_config):
    """execute() converts KeyboardInterrupt to PartialExecutionAbortedError."""
    mock_executor_cls = mocker.patch("protostar.orchestrator.SystemExecutor")
    mock_executor_instance = mock_executor_cls.return_value
    mock_executor_instance.execute.side_effect = KeyboardInterrupt
    mock_executor_instance.touched_paths = {"some_file.py"}

    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)
    manifest = engine.plan()

    with pytest.raises(PartialExecutionAbortedError) as exc_info:
        engine.execute(manifest)

    assert "some_file.py" in exc_info.value.touched_paths


def test_execute_does_not_rebuild_manifest(mocker, mock_config):
    """execute() must not call pre_flight or build — it takes the manifest as-is."""
    dummy_mod = DummyModule()
    mocker.patch("protostar.orchestrator.SystemExecutor")
    mocker.patch.object(Path, "exists", return_value=False)

    engine = Orchestrator([dummy_mod], mock_config)
    manifest = engine.plan()

    # Remove the task that plan() added, then verify execute doesn't re-add it
    manifest.tasks.system_tasks.clear()

    engine.execute(manifest)

    assert len(manifest.tasks.system_tasks) == 0


# ---------------------------------------------------------------------------
# InitRequest defaults
# ---------------------------------------------------------------------------


def test_init_request_defaults():
    """InitRequest initializes with safe, no-op defaults."""
    req = InitRequest()
    assert req.template_blueprint is None
    assert req.python_version is None
    assert req.docker is False
    assert req.force_merge is False
    assert req.force_replace is False
    assert req.metadata is None
    assert req.is_external is False
    assert req.is_user_aliased is False


def test_orchestrator_defaults_to_empty_request(mock_config):
    """Orchestrator initialized without a request defaults to a no-op InitRequest."""
    engine = Orchestrator([], mock_config)
    assert isinstance(engine.request, InitRequest)
    assert engine.request.docker is False


# ---------------------------------------------------------------------------
# Trust boundary (now belongs in CLI; verified absent from Orchestrator)
# ---------------------------------------------------------------------------


def test_orchestrator_has_no_trust_method(mock_config):
    """Verify that _prompt_remote_trust no longer exists on Orchestrator."""
    engine = Orchestrator([], mock_config)
    assert not hasattr(engine, "_prompt_remote_trust")


def test_orchestrator_has_no_run_method(mock_config):
    """Verify that the monolithic run() method no longer exists on Orchestrator."""
    engine = Orchestrator([], mock_config)
    assert not hasattr(engine, "run")


def test_workspace_collision_error_carries_paths():
    """WorkspaceCollisionError exposes the conflicting paths as a frozenset."""
    paths = frozenset([Path("pyproject.toml"), Path(".python-version")])
    err = WorkspaceCollisionError(paths=paths)
    assert err.paths == paths
    assert "pyproject.toml" in str(err)


def test_plan_metadata_injected_into_manifest(mocker, mock_config):
    """plan() merges request.metadata into the manifest's metadata dict."""
    engine = Orchestrator(
        [],
        mock_config,
        request=InitRequest(metadata={"author_name": "Ada Lovelace"}),
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert manifest.metadata.get("author_name") == "Ada Lovelace"


def test_plan_does_not_mutate_filesystem(mocker, tmp_path, mock_config):
    """plan() must produce a purely declarative blueprint without disk writes."""
    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    # plan() generates declarative structures without execution tracking or side effects
    assert isinstance(manifest, EnvironmentManifest)
    assert not hasattr(manifest.filesystem, "touched_paths")
    assert not hasattr(manifest, "diagnostics")
