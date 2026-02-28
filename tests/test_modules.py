import pytest

from protostar.config import ProtostarConfig
from protostar.modules import (
    DirenvModule,
    MacOSModule,
    MarkdownLintModule,
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


def test_python_module_uv_with_version(manifest, mocker):
    """Test Python manifest includes the specific python version flag for uv."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="uv", python_version="3.12")
    mod.build(manifest)

    assert ["uv", "init", "--no-workspace", "--python", "3.12"] in manifest.system_tasks


def test_python_module_pip_build(manifest, mocker):
    """Test Python manifest correctly initializes standard library venv for pip."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="pip")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ["python3", "-m", "venv", ".venv"] in manifest.system_tasks


def test_python_module_pip_with_version(manifest, mocker):
    """Test Python manifest formats the python executable correctly for pip venvs."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="pip", python_version="3.11")
    mod.build(manifest)

    assert ["python3.11", "-m", "venv", ".venv"] in manifest.system_tasks


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


def test_direnv_module_pre_flight_fails(mocker):
    """Test that direnv preflight fails loudly if direnv is missing from PATH."""
    mocker.patch("protostar.modules.tooling_layer.shutil.which", return_value=None)
    mod = DirenvModule()

    with pytest.raises(RuntimeError, match="direnv is not installed"):
        mod.pre_flight()


def test_direnv_module_build_uv(manifest, mocker):
    """Test that direnv queue correctly formats .envrc files prioritizing uv."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    mod = DirenvModule()
    mod.build(manifest)

    assert ".envrc.local" in manifest.vcs_ignores
    assert ".envrc" in manifest.file_injections
    assert "uv sync" in manifest.file_injections[".envrc"]
    assert ["direnv", "allow"] in manifest.system_tasks


def test_markdownlint_module_build(manifest, mocker):
    """Test that MarkdownLint injects the configured ruleset."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = MarkdownLintModule()
    mod.build(manifest)

    assert ".markdownlint.yaml" in manifest.file_injections
    assert "MD013: false" in manifest.file_injections[".markdownlint.yaml"]
