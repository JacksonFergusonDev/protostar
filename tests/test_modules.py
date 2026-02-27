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


def test_python_module_uv_build(manifest, mocker):
    """Test Python manifest mutation prioritizes uv by default."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="uv")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ["uv", "init", "--no-workspace"] in manifest.system_tasks


def test_python_module_pip_build(manifest, mocker):
    """Test Python manifest correctly initializes standard library venv for pip."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)
    mock_touch = mocker.patch("protostar.modules.lang_layer.Path.touch")

    mod = PythonModule(package_manager="pip")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ["python3", "-m", "venv", ".venv"] in manifest.system_tasks
    mock_touch.assert_called_once()


def test_node_module_custom_manager(manifest, mocker):
    """Test that NodeModule respects custom package managers like pnpm."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = NodeModule(package_manager="pnpm")
    mod.build(manifest)

    assert ["pnpm", "init"] in manifest.system_tasks
    assert "node_modules/" in manifest.vcs_ignores


def test_vscode_module_aliases():
    """Test that IDE aliases expose the correct mapping strings."""
    mod = VSCodeModule()
    assert "vscode" in mod.aliases
    assert "cursor" in mod.aliases


def test_vscode_module_build(manifest):
    """Test that VS Code successfully translates hides into workspace exclusions."""
    manifest.add_workspace_hide(".venv/")
    manifest.add_workspace_hide("build/")

    mod = VSCodeModule()
    mod.build(manifest)

    assert "files.exclude" in manifest.ide_settings
    exclusions = manifest.ide_settings["files.exclude"]

    assert exclusions["**/.venv"] is True
    assert exclusions["**/build"] is True
