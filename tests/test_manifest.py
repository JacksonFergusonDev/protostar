def test_manifest_initialization(manifest):
    """Test that the manifest initializes with empty, correct data structures."""
    assert isinstance(manifest.vcs_ignores, set)
    assert isinstance(manifest.workspace_hides, set)
    assert isinstance(manifest.ide_settings, dict)
    assert isinstance(manifest.dependencies, list)
    assert isinstance(manifest.dev_dependencies, list)
    assert isinstance(manifest.system_tasks, list)
    assert isinstance(manifest.directories, set)
    assert isinstance(manifest.file_injections, dict)
    assert isinstance(manifest.file_appends, dict)
    assert manifest.wants_pre_commit is False
    assert isinstance(manifest.pre_commit_hooks, list)


def test_add_vcs_ignore(manifest):
    """Test that VCS ignore patterns are correctly added and deduplicated."""
    manifest.add_vcs_ignore(".DS_Store")
    manifest.add_vcs_ignore(".DS_Store")  # Should not duplicate
    manifest.add_vcs_ignore("node_modules/")

    assert len(manifest.vcs_ignores) == 2
    assert ".DS_Store" in manifest.vcs_ignores


def test_add_workspace_hide(manifest):
    """Test that workspace hides are correctly added and deduplicated."""
    manifest.add_workspace_hide(".venv/")
    manifest.add_workspace_hide(".venv/")  # Should not duplicate
    manifest.add_workspace_hide("build/")

    assert len(manifest.workspace_hides) == 2
    assert ".venv/" in manifest.workspace_hides


def test_add_ide_setting(manifest):
    """Test that IDE settings are stored correctly."""
    manifest.add_ide_setting("python.formatting.provider", "ruff")
    assert manifest.ide_settings["python.formatting.provider"] == "ruff"


def test_add_system_task(manifest):
    """Test that system tasks are queued sequentially."""
    manifest.add_system_task(["uv", "init"])
    manifest.add_system_task(["cargo", "init"])

    assert len(manifest.system_tasks) == 2
    assert manifest.system_tasks[0] == ["uv", "init"]


def test_add_dependency_deduplication(manifest):
    """Test that dependencies are queued and deduplicated."""
    manifest.add_dependency("numpy")
    manifest.add_dependency("pandas")
    manifest.add_dependency("numpy")  # Should not duplicate

    assert len(manifest.dependencies) == 2
    assert manifest.dependencies == ["numpy", "pandas"]


def test_add_dev_dependency_deduplication(manifest):
    """Test that dev dependencies are queued and deduplicated independently."""
    manifest.add_dev_dependency("pytest")
    manifest.add_dev_dependency("ruff")
    manifest.add_dev_dependency("pytest")  # Should not duplicate

    assert len(manifest.dev_dependencies) == 2
    assert manifest.dev_dependencies == ["pytest", "ruff"]


def test_manifest_directories_initialization(manifest):
    """Test that the manifest initializes the directories set."""
    assert isinstance(manifest.directories, set)


def test_add_directory(manifest):
    """Test that directories are correctly queued and deduplicated."""
    manifest.add_directory("data")
    manifest.add_directory("data")  # Should not duplicate
    manifest.add_directory("src")

    assert len(manifest.directories) == 2
    assert "data" in manifest.directories
    assert "src" in manifest.directories


def test_add_file_injection(manifest):
    """Test that file injections are queued and deduplicated correctly."""
    manifest.add_file_injection(".envrc", "export FOO=bar")
    manifest.add_file_injection(".envrc", "export FOO=baz")  # Should not overwrite

    assert len(manifest.file_injections) == 1
    assert manifest.file_injections[".envrc"] == "export FOO=bar"


def test_add_file_append(manifest):
    """Test that file appends queue successfully to the target path list."""
    manifest.add_file_append("pyproject.toml", "[tool.ruff]")
    manifest.add_file_append("pyproject.toml", "[tool.mypy]")

    assert len(manifest.file_appends) == 1
    assert len(manifest.file_appends["pyproject.toml"]) == 2
    assert manifest.file_appends["pyproject.toml"] == ["[tool.ruff]", "[tool.mypy]"]


def test_add_pre_commit_hook(manifest):
    """Test that pre-commit hooks are queued and deduplicated correctly."""
    manifest.add_pre_commit_hook("- id: ruff")
    manifest.add_pre_commit_hook("- id: ruff")  # Should not duplicate
    manifest.add_pre_commit_hook("- id: mypy")

    assert len(manifest.pre_commit_hooks) == 2
    assert "- id: ruff" in manifest.pre_commit_hooks
    assert "- id: mypy" in manifest.pre_commit_hooks
