from protostar.modules import (
    MacOSModule,
    NodeModule,
    PythonModule,
    VSCodeModule,
)


def test_macos_module(manifest):
    """Test that the macOS layer appends correct system ignores."""
    mod = MacOSModule()
    mod.build(manifest)
    assert ".DS_Store" in manifest.vcs_ignores


def test_python_module_build(manifest, mocker):
    """Test Python manifest mutation (ignores and init task)."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule()
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ".venv/" in manifest.workspace_hides
    assert ["uv", "init", "--no-workspace"] in manifest.system_tasks


def test_node_module_custom_manager(manifest, mocker):
    """Test that NodeModule respects custom package managers like pnpm."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = NodeModule(package_manager="pnpm")
    mod.build(manifest)

    assert ["pnpm", "init"] in manifest.system_tasks
    assert "node_modules/" in manifest.vcs_ignores


def test_vscode_module_build(manifest):
    """Test that VS Code successfully translates hides into workspace exclusions."""
    # Seed the manifest with some raw hides
    manifest.add_workspace_hide(".venv/")
    manifest.add_workspace_hide("build/")

    mod = VSCodeModule()
    mod.build(manifest)

    assert "files.exclude" in manifest.ide_settings
    exclusions = manifest.ide_settings["files.exclude"]

    assert exclusions["**/.venv"] is True
    assert exclusions["**/build"] is True
