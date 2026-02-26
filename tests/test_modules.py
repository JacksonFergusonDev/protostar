import pytest

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
    assert ".DS_Store" in manifest.ignored_paths


def test_python_module_pre_flight_success(mocker):
    """Test that Python pre-flight passes if uv is available."""
    mocker.patch("shutil.which", return_value="/usr/local/bin/uv")
    mod = PythonModule()
    mod.pre_flight()  # Should not raise


def test_python_module_pre_flight_missing_uv(mocker):
    """Test that Python pre-flight hard aborts if uv is missing."""
    mocker.patch("shutil.which", return_value=None)
    mod = PythonModule()

    with pytest.raises(RuntimeError, match="Missing dependency: 'uv'"):
        mod.pre_flight()


def test_python_module_build(manifest, mocker):
    """Test Python manifest mutation (ignores and init task)."""
    # Simulate pyproject.toml NOT existing so the init task triggers
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule()
    mod.build(manifest)

    assert ".venv/" in manifest.ignored_paths
    assert ["uv", "init", "--no-workspace"] in manifest.system_tasks


def test_node_module_custom_manager(manifest, mocker):
    """Test that NodeModule respects custom package managers like pnpm."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = NodeModule(package_manager="pnpm")
    mod.build(manifest)

    assert ["pnpm", "init"] in manifest.system_tasks
    assert "node_modules/" in manifest.ignored_paths


def test_vscode_module_build(manifest):
    """Test that VS Code successfully translates ignores into workspace exclusions."""
    # Seed the manifest with some raw ignores
    manifest.add_ignore(".venv/")
    manifest.add_ignore("build/")

    mod = VSCodeModule()
    mod.build(manifest)

    assert "files.exclude" in manifest.ide_settings
    exclusions = manifest.ide_settings["files.exclude"]

    # Notice how it strips the trailing slashes and prepends **/
    assert exclusions["**/.venv"] is True
    assert exclusions["**/build"] is True
