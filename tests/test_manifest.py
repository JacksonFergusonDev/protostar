def test_manifest_initialization(manifest):
    """Test that the manifest initializes with empty, correct data structures."""
    assert isinstance(manifest.ignored_paths, set)
    assert isinstance(manifest.ide_settings, dict)
    assert isinstance(manifest.dependencies, list)
    assert isinstance(manifest.system_tasks, list)


def test_add_ignore(manifest):
    """Test that ignore patterns are correctly added and deduplicated."""
    manifest.add_ignore(".DS_Store")
    manifest.add_ignore(".DS_Store")  # Should not duplicate
    manifest.add_ignore("node_modules/")

    assert len(manifest.ignored_paths) == 2
    assert ".DS_Store" in manifest.ignored_paths


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
