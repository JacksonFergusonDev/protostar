from pathlib import Path

import pytest

from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import (
    ConfigurationError,
    ExecutionInterruptedError,
    WorkspaceCollisionError,
)
from protostar.intent import PyprojectPayload
from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    EnvironmentManifest,
    Severity,
)
from protostar.models import ExecutionResult, InitRequest
from protostar.modules import (
    BootstrapModule,
    CommitizenModule,
    PreCommitModule,
    PrekModule,
    PythonCore,
    ReadTheDocsModule,
    RuffModule,
    ZensicalModule,
)
from protostar.orchestrator import Orchestrator


@pytest.fixture
def mock_config() -> UserConfig:
    return UserConfig()


class DummyModule(BootstrapModule):
    @property
    def name(self):
        return "Dummy"

    def pre_flight(self):
        self.pre_flight_called = True

    def build(self, manifest):
        manifest.filesystem.add_vcs_ignore("dummy_file.txt")
        manifest.filesystem.add_file_injection("dummy_marker.txt", "dummy payload")
        manifest.tasks.add_system_task(["echo", "dummy"])
        manifest.dependencies.add("dummy-pkg")


# ---------------------------------------------------------------------------
# plan() tests
# ---------------------------------------------------------------------------


def test_plan_calls_pre_flight_and_build(tmp_path, monkeypatch, mock_config):
    """plan() should invoke pre_flight and build on each module."""
    monkeypatch.chdir(tmp_path)
    dummy_mod = DummyModule()
    engine = Orchestrator([dummy_mod], mock_config)

    manifest = engine.plan()

    assert dummy_mod.pre_flight_called
    assert "dummy-pkg" in manifest.dependencies.dependencies


def test_plan_raises_on_collision_without_force_flag(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError when markers exist and no force flag is set."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dummy_marker.txt").write_text("existing content")
    dummy_mod = DummyModule()
    engine = Orchestrator([dummy_mod], mock_config)

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("dummy_marker.txt") in exc_info.value.paths


def test_plan_force_replace_sets_overwrite_strategy(tmp_path, monkeypatch, mock_config):
    """plan() resolves collisions to OVERWRITE when force_replace=True."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dummy_marker.txt").write_text("existing content")
    dummy_mod = DummyModule()
    engine = Orchestrator(
        [dummy_mod], mock_config, request=InitRequest(force_replace=True)
    )

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.OVERWRITE


def test_plan_force_merge_sets_merge_strategy(tmp_path, monkeypatch, mock_config):
    """plan() resolves collisions to MERGE when force_merge=True."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dummy_marker.txt").write_text("existing content")
    dummy_mod = DummyModule()
    engine = Orchestrator(
        [dummy_mod], mock_config, request=InitRequest(force_merge=True)
    )

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_plan_returns_fresh_manifest_on_each_call(tmp_path, monkeypatch, mock_config):
    """Calling plan() twice must return independent EnvironmentManifest instances."""
    monkeypatch.chdir(tmp_path)
    engine = Orchestrator([], mock_config)

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
    blueprint.pyproject_injections = {
        "custom_key": PyprojectPayload("[tool.custom]\nvalue = true")
    }

    engine = Orchestrator(
        [], mock_config, request=InitRequest(template_blueprint=blueprint)
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert "test-global-dep" in manifest.dependencies.dev_dependencies
    assert any(
        "[tool.custom]" in c.content
        for c in manifest.filesystem.structured["pyproject.toml"]
    )


def _gated_payload_blueprint() -> TemplateBlueprint:
    blueprint = TemplateBlueprint()
    blueprint.pyproject_injections = {
        "always": PyprojectPayload("[tool.always]\nvalue = true"),
        "lint": PyprojectPayload("[tool.ruff.lint]\nextend-select = ['D']", "ruff"),
    }
    return blueprint


def _injected_payloads(manifest):
    return {
        c.producer.rsplit(":", 1)[-1]: c
        for c in manifest.filesystem.structured.get("pyproject.toml", [])
        if c.producer.startswith("template:")
    }


def test_plan_injects_a_tool_bound_payload_while_its_tool_is_active(
    mocker, mock_config
):
    engine = Orchestrator(
        [RuffModule()],
        mock_config,
        request=InitRequest(template_blueprint=_gated_payload_blueprint()),
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    assert {"always", "lint"} <= _injected_payloads(manifest).keys()


def test_plan_skips_a_tool_bound_payload_when_its_tool_is_inactive(mocker, mock_config):
    """`--no-ruff` must not leave ruff configuration behind."""
    engine = Orchestrator(
        [],
        mock_config,
        request=InitRequest(template_blueprint=_gated_payload_blueprint()),
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    payloads = _injected_payloads(manifest)
    assert "always" in payloads
    assert "lint" not in payloads
    assert "[tool.ruff" not in "".join(
        c.content for c in manifest.filesystem.structured["pyproject.toml"]
    )


def test_plan_attributes_a_tool_bound_payload_to_its_tool(mocker, mock_config):
    from protostar.recipe import Tool

    engine = Orchestrator(
        [RuffModule()],
        mock_config,
        request=InitRequest(template_blueprint=_gated_payload_blueprint()),
    )
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    def contributions(identity):
        return [
            c
            for c in manifest.producer_contributions
            if c.path[:3] == ("filesystem", "structured", "pyproject.toml")
            and c.path[-1].endswith(f":{identity}")
        ]

    lint, always = contributions("lint"), contributions("always")

    assert lint
    assert all(c.tool is Tool.RUFF for c in lint)
    assert always
    assert all(c.tool is None for c in always)


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
    mock_executor_instance.journal.created_paths = frozenset({"pyproject.toml"})
    mock_executor_instance.journal.mutated_paths = frozenset()
    mock_executor_instance.diagnostics = [
        DiagnosticEvent(phase="Test", message="something", severity=Severity.INFO)
    ]

    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)
    manifest = engine.plan()

    result = engine.execute(manifest)

    assert "pyproject.toml" in result.touched_paths
    assert result.diagnostics[0].message == "something"


def test_execute_raises_interrupted_error_on_keyboard_interrupt(mocker, mock_config):
    """execute() converts KeyboardInterrupt to ExecutionInterruptedError."""
    mock_executor_cls = mocker.patch("protostar.orchestrator.SystemExecutor")
    mock_executor_instance = mock_executor_cls.return_value
    mock_executor_instance.journal.created_paths = frozenset({"pyproject.toml"})
    mock_executor_instance.journal.mutated_paths = frozenset()
    mock_executor_instance.execute.side_effect = KeyboardInterrupt
    mock_executor_instance.journal.touched_paths = {"some_file.py"}

    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)
    manifest = engine.plan()

    with pytest.raises(ExecutionInterruptedError) as exc_info:
        engine.execute(manifest)

    ctx = exc_info.value.rollback_context
    assert ctx is not None
    assert "some_file.py" in ctx.touched_paths


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


def test_plan_does_not_mutate_filesystem(mocker, mock_config):
    """plan() must produce a purely declarative blueprint without disk writes."""
    engine = Orchestrator([], mock_config)
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = engine.plan()

    # plan() generates declarative structures without execution tracking or side effects
    assert isinstance(manifest, EnvironmentManifest)
    assert not hasattr(manifest.filesystem, "touched_paths")
    assert not hasattr(manifest, "diagnostics")


def test_plan_raises_on_conflicting_hook_runners(mock_config, mocker):
    """plan() must raise ConfigurationError if both PreCommitModule and PrekModule are passed."""
    mocker.patch.object(Path, "exists", return_value=False)
    engine = Orchestrator([PreCommitModule(), PrekModule()], mock_config)

    with pytest.raises(
        ConfigurationError,
        match=r"Cannot use both '--pre-commit' and '--prek' simultaneously",
    ):
        engine.plan()


def test_plan_raises_on_readthedocs_without_zensical(mock_config, mocker):
    """plan() must raise ConfigurationError if ReadTheDocsModule is passed without ZensicalModule."""
    mocker.patch.object(Path, "exists", return_value=False)
    engine = Orchestrator([ReadTheDocsModule()], mock_config)

    with pytest.raises(
        ConfigurationError,
        match=r"Read the Docs scaffolding requires the Zensical module to be enabled",
    ):
        engine.plan()


def test_plan_allows_readthedocs_with_zensical_order_independent(mock_config, mocker):
    """plan() succeeds when both ReadTheDocsModule and ZensicalModule are enabled, regardless of order."""
    mocker.patch.object(Path, "exists", return_value=False)
    # Register ReadTheDocsModule before ZensicalModule to verify order independence
    engine = Orchestrator([ReadTheDocsModule(), ZensicalModule()], mock_config)
    manifest = engine.plan()

    assert ".readthedocs.yaml" in manifest.filesystem.file_injections


def test_plan_detects_docker_collision_without_force_flag(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError when req.docker is True and Dockerfile exists."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Dockerfile").touch()
    engine = Orchestrator([], mock_config, request=InitRequest(docker=True))

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("Dockerfile") in exc_info.value.paths


def test_plan_detects_dockerignore_collision_without_force_flag(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError when req.docker is True and .dockerignore exists."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".dockerignore").touch()
    engine = Orchestrator([], mock_config, request=InitRequest(docker=True))

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path(".dockerignore") in exc_info.value.paths


def test_plan_ignores_docker_collision_when_docker_disabled(
    tmp_path, monkeypatch, mock_config
):
    """plan() ignores Dockerfile collision when req.docker is False."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Dockerfile").touch()
    engine = Orchestrator([], mock_config, request=InitRequest(docker=False))

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_plan_resolves_docker_collision_with_force_merge(
    tmp_path, monkeypatch, mock_config
):
    """plan() resolves Docker collision to MERGE when force_merge=True."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Dockerfile").touch()
    engine = Orchestrator(
        [], mock_config, request=InitRequest(docker=True, force_merge=True)
    )

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_plan_detects_license_collision_from_python_core(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError when LICENSE exists and an active license is configured."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "LICENSE").touch()
    engine = Orchestrator(
        [PythonCore(project_license="MIT")],
        mock_config,
        request=InitRequest(metadata={"license": "MIT"}),
    )

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("LICENSE") in exc_info.value.paths


def test_plan_ignores_license_collision_when_license_none(
    tmp_path, monkeypatch, mock_config
):
    """plan() does not raise WorkspaceCollisionError when LICENSE exists but license is None."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "LICENSE").touch()
    engine = Orchestrator(
        [PythonCore(project_license=None)],
        mock_config,
        request=InitRequest(metadata={"license": "None"}),
    )

    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_plan_ignores_docs_directory_collision_when_index_absent(
    tmp_path, monkeypatch, mock_config
):
    """plan() does not treat existing docs/ directory as collision if docs/index.md is absent."""
    monkeypatch.chdir(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "unrelated.md").touch()

    engine = Orchestrator([ZensicalModule()], mock_config)
    manifest = engine.plan()
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_plan_detects_docs_index_collision_from_zensical(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError when docs/index.md exists and Zensical is enabled."""
    monkeypatch.chdir(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").touch()

    engine = Orchestrator([ZensicalModule()], mock_config)
    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("docs/index.md") in exc_info.value.paths


def test_plan_detects_commitizen_changelog_collision(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError when CHANGELOG.md exists and Commitizen is enabled."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").touch()

    engine = Orchestrator([CommitizenModule()], mock_config)
    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("CHANGELOG.md") in exc_info.value.paths


def test_plan_detects_blueprint_files_collision(tmp_path, monkeypatch, mock_config):
    """plan() raises WorkspaceCollisionError when template blueprint files exist on disk."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Old Readme")

    blueprint = TemplateBlueprint(
        name="test",
        description="test",
        files={"README.md": "# New Readme"},
    )
    engine = Orchestrator(
        [], mock_config, request=InitRequest(template_blueprint=blueprint)
    )

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("README.md") in exc_info.value.paths


def test_plan_detects_blueprint_files_collision_with_interpolation(
    tmp_path, monkeypatch, mock_config
):
    """plan() raises WorkspaceCollisionError for interpolated template blueprint filepaths."""
    monkeypatch.chdir(tmp_path)
    pkg_file = tmp_path / "src" / "my_pkg" / "main.py"
    pkg_file.parent.mkdir(parents=True, exist_ok=True)
    pkg_file.touch()

    blueprint = TemplateBlueprint(
        name="test",
        description="test",
        files={"src/<% PACKAGE_NAME %>/main.py": "print('hello')"},
    )
    engine = Orchestrator(
        [],
        mock_config,
        request=InitRequest(
            template_blueprint=blueprint, metadata={"package_name": "my_pkg"}
        ),
    )

    with pytest.raises(WorkspaceCollisionError) as exc_info:
        engine.plan()

    assert Path("src/my_pkg/main.py") in exc_info.value.paths
