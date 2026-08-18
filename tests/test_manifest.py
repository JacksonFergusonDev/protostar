from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    EnvironmentManifest,
    Severity,
)


def test_manifest_initialization(manifest):
    """Test that the manifest initializes with empty, correct data structures."""
    assert isinstance(manifest.filesystem.vcs_ignores, set)
    assert isinstance(manifest.filesystem.workspace_hides, set)
    assert isinstance(manifest.ide_settings, dict)
    assert isinstance(manifest.dependencies.dependencies, list)
    assert isinstance(manifest.dependencies.dev_dependencies, list)
    assert isinstance(manifest.tasks.system_tasks, list)
    assert isinstance(manifest.filesystem.directories, set)
    assert isinstance(manifest.filesystem.file_injections, dict)
    assert isinstance(manifest.filesystem.file_appends, dict)
    assert manifest.tooling.wants_pre_commit is False
    assert isinstance(manifest.tooling.pre_commit_hooks, list)
    assert isinstance(manifest.tooling.pre_commit_local_hooks, list)
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_add_vcs_ignore(manifest):
    """Test that VCS ignore patterns are correctly added and deduplicated."""
    manifest.filesystem.add_vcs_ignore(".DS_Store")
    manifest.filesystem.add_vcs_ignore(".DS_Store")  # Should not duplicate
    manifest.filesystem.add_vcs_ignore("node_modules/")

    assert len(manifest.filesystem.vcs_ignores) == 2
    assert ".DS_Store" in manifest.filesystem.vcs_ignores


def test_add_workspace_hide(manifest):
    """Test that workspace hides are correctly added and deduplicated."""
    manifest.filesystem.add_workspace_hide(".venv/")
    manifest.filesystem.add_workspace_hide(".venv/")  # Should not duplicate
    manifest.filesystem.add_workspace_hide("build/")

    assert len(manifest.filesystem.workspace_hides) == 2
    assert ".venv/" in manifest.filesystem.workspace_hides


def test_add_ide_setting(manifest):
    """Test that IDE settings are stored correctly."""
    manifest.add_ide_setting("python.formatting.provider", "ruff")
    assert manifest.ide_settings["python.formatting.provider"] == "ruff"


def test_add_system_task(manifest):
    """Test that system tasks are queued sequentially as SystemTask dataclasses."""
    manifest.tasks.add_system_task(["uv", "init"])
    manifest.tasks.add_system_task(["cargo", "init"], timeout=45)

    assert len(manifest.tasks.system_tasks) == 2
    assert manifest.tasks.system_tasks[0].command == ["uv", "init"]
    assert manifest.tasks.system_tasks[0].timeout == 30
    assert manifest.tasks.system_tasks[1].command == ["cargo", "init"]
    assert manifest.tasks.system_tasks[1].timeout == 45


def test_add_system_task_with_description():
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(
        ["git", "init"], timeout=10, description="Initializing git repository"
    )

    assert len(manifest.tasks.system_tasks) == 1
    task = manifest.tasks.system_tasks[0]
    assert task.command == ["git", "init"]
    assert task.timeout == 10
    assert task.description == "Initializing git repository"


def test_add_post_install_task_with_description():
    manifest = EnvironmentManifest()
    manifest.tasks.add_post_install_task(
        ["direnv", "allow"], description="Authorizing direnv workspace"
    )

    assert len(manifest.tasks.post_install_tasks) == 1
    task = manifest.tasks.post_install_tasks[0]
    assert task.command == ["direnv", "allow"]
    assert task.description == "Authorizing direnv workspace"


def test_add_post_install_task(manifest):
    """Test that post-install tasks are queued sequentially with explicit timeout bindings."""
    manifest.tasks.add_post_install_task(["direnv", "allow"])
    manifest.tasks.add_post_install_task(["pre-commit", "autoupdate"], timeout=300)

    assert len(manifest.tasks.post_install_tasks) == 2
    assert manifest.tasks.post_install_tasks[0].command == ["direnv", "allow"]
    assert manifest.tasks.post_install_tasks[0].timeout == 30
    assert manifest.tasks.post_install_tasks[1].command == ["pre-commit", "autoupdate"]
    assert manifest.tasks.post_install_tasks[1].timeout == 300


def test_add_dependency_deduplication(manifest):
    """Test that dependencies are queued and deduplicated."""
    manifest.dependencies.add("numpy")
    manifest.dependencies.add("pandas")
    manifest.dependencies.add("numpy")  # Should not duplicate

    assert len(manifest.dependencies.dependencies) == 2
    assert manifest.dependencies.dependencies == ["numpy", "pandas"]


def test_add_dev_dependency_deduplication(manifest):
    """Test that dev dependencies are queued and deduplicated independently."""
    manifest.dependencies.add_dev("pytest")
    manifest.dependencies.add_dev("ruff")
    manifest.dependencies.add_dev("pytest")  # Should not duplicate

    assert len(manifest.dependencies.dev_dependencies) == 2
    assert manifest.dependencies.dev_dependencies == ["pytest", "ruff"]


def test_manifest_directories_initialization(manifest):
    """Test that the manifest initializes the directories set."""
    assert isinstance(manifest.filesystem.directories, set)


def test_add_directory(manifest):
    """Test that directories are correctly queued and deduplicated."""
    manifest.filesystem.add_directory("data")
    manifest.filesystem.add_directory("data")  # Should not duplicate
    manifest.filesystem.add_directory("src")

    assert len(manifest.filesystem.directories) == 2
    assert "data" in manifest.filesystem.directories
    assert "src" in manifest.filesystem.directories


def test_add_file_injection(manifest):
    """Test that file injections are queued and deduplicated correctly."""
    manifest.filesystem.add_file_injection(".envrc", "export FOO=bar")
    manifest.filesystem.add_file_injection(
        ".envrc", "export FOO=baz"
    )  # Should not overwrite

    assert len(manifest.filesystem.file_injections) == 1
    assert manifest.filesystem.file_injections[".envrc"] == "export FOO=bar"


def test_add_file_append(manifest):
    """Test that file appends queue successfully to the target path list."""
    manifest.filesystem.add_file_append("pyproject.toml", "[tool.ruff]")
    manifest.filesystem.add_file_append("pyproject.toml", "[tool.mypy]")

    assert len(manifest.filesystem.file_appends) == 1
    assert len(manifest.filesystem.file_appends["pyproject.toml"]) == 2
    assert manifest.filesystem.file_appends["pyproject.toml"] == [
        "[tool.ruff]",
        "[tool.mypy]",
    ]


def test_add_pre_commit_hook(manifest):
    """Test that pre-commit hooks are queued and deduplicated correctly."""
    manifest.tooling.add_pre_commit_hook("- id: ruff")
    manifest.tooling.add_pre_commit_hook("- id: ruff")  # Should not duplicate
    manifest.tooling.add_pre_commit_hook("- id: mypy")

    assert len(manifest.tooling.pre_commit_hooks) == 2
    assert "- id: ruff" in manifest.tooling.pre_commit_hooks
    assert "- id: mypy" in manifest.tooling.pre_commit_hooks


def test_add_pre_commit_local_hook(manifest):
    """Test that local pre-commit hooks are queued and deduplicated correctly."""
    manifest.tooling.add_pre_commit_local_hook("- id: ruff-check")
    manifest.tooling.add_pre_commit_local_hook(
        "- id: ruff-check"
    )  # Should not duplicate
    manifest.tooling.add_pre_commit_local_hook("- id: mypy")

    assert len(manifest.tooling.pre_commit_local_hooks) == 2
    assert "- id: ruff-check" in manifest.tooling.pre_commit_local_hooks
    assert "- id: mypy" in manifest.tooling.pre_commit_local_hooks


def test_manifest_diagnostic_collection() -> None:
    manifest = EnvironmentManifest()
    assert len(manifest.diagnostics) == 0

    manifest.add_diagnostic(
        phase="TestPhase",
        message="A test warning occurred.",
        severity=Severity.WARNING,
        detail="Some traceback or detail",
    )

    assert len(manifest.diagnostics) == 1
    event = manifest.diagnostics[0]
    assert isinstance(event, DiagnosticEvent)
    assert event.phase == "TestPhase"
    assert event.message == "A test warning occurred."
    assert event.severity == Severity.WARNING
    assert event.detail == "Some traceback or detail"


def test_add_ide_extension_aggregates_uniquely():
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("charliermarsh.ruff")
    manifest.tooling.add_ide_extension("ms-python.mypy-type-checker")

    # Attempt to add a duplicate
    manifest.tooling.add_ide_extension("charliermarsh.ruff")

    assert len(manifest.tooling.ide_extensions) == 2
    assert "charliermarsh.ruff" in manifest.tooling.ide_extensions
    assert "ms-python.mypy-type-checker" in manifest.tooling.ide_extensions


def test_manifest_accepts_mixed_ide_extensions():
    """Verifies the manifest correctly stores both strings and tuples for extensions."""
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("charliermarsh.ruff")
    manifest.tooling.add_ide_extension(
        ("ms-python.mypy-type-checker", "matangover.mypy")
    )

    assert len(manifest.tooling.ide_extensions) == 2
    assert "charliermarsh.ruff" in manifest.tooling.ide_extensions
    assert (
        "ms-python.mypy-type-checker",
        "matangover.mypy",
    ) in manifest.tooling.ide_extensions
