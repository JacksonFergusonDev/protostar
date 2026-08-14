from protostar.presets import (
    ApiPreset,
    AstroPreset,
    CliPreset,
    DspPreset,
    EmbeddedPreset,
    MLPreset,
    PresetModule,
    ScientificPreset,
)


def test_scientific_preset_build(manifest):
    """Test that the Scientific preset injects data pipelines."""
    preset = ScientificPreset()
    preset.build(manifest)

    assert "scikit-learn" in manifest.dependencies
    assert "numpy" in manifest.dependencies
    assert "notebooks" in manifest.directories
    assert "*.parquet" in manifest.vcs_ignores


def test_astro_preset_build(manifest, mocker):
    """Test that the Astro preset injects observational formats and uv nbdime."""
    mocker.patch("protostar.presets.astro.Path.exists", return_value=True)

    preset = AstroPreset()
    preset.build(manifest)

    assert "photutils" in manifest.dependencies
    assert "numpy" in manifest.dependencies
    assert "nbdime" in manifest.dependencies
    assert "data/fits" in manifest.directories
    assert "*.fits" in manifest.vcs_ignores
    assert ".gitattributes" in manifest.file_injections

    assert any(
        t.command == ["uv", "run", "nbdime", "config-git", "--enable"]
        for t in manifest.post_install_tasks
    )
    assert not any(t.command == ["git", "init"] for t in manifest.system_tasks)

    # Verify nbdime post-install task
    nbdime_task = next(t for t in manifest.post_install_tasks if "nbdime" in t.command)
    assert nbdime_task.description == "Configuring nbdime git integration"


def test_ml_preset_build(manifest):
    """Test that the ML preset injects deep learning frameworks and telemetry ignores."""
    preset = MLPreset()
    preset.build(manifest)

    assert "torch" in manifest.dependencies
    assert "huggingface_hub" in manifest.dependencies
    assert "models" in manifest.directories
    assert "*.pt" in manifest.vcs_ignores
    assert "wandb/" in manifest.vcs_ignores


def test_api_preset_build(manifest):
    """Test that the API preset injects web frameworks and security ignores."""
    preset = ApiPreset()
    preset.build(manifest)

    assert "fastapi" in manifest.dependencies
    assert "pydantic" in manifest.dependencies
    assert "api/routers" in manifest.directories
    assert ".env" in manifest.vcs_ignores


def test_cli_preset_build(manifest):
    """Test that the CLI preset injects terminal frameworks, package directory, starter code, and entrypoints."""
    manifest.metadata = {
        "project_name": "my-cli-tool",
        "description": "My awesome CLI tool.",
    }
    preset = CliPreset()
    preset.build(manifest)

    assert "typer" in manifest.dependencies
    assert "rich" in manifest.dependencies
    assert "src/my_cli_tool" in manifest.directories
    assert "tests" in manifest.directories

    # Verify injected boilerplate files
    init_file = manifest.file_injections["src/my_cli_tool/__init__.py"]
    assert '"""My awesome CLI tool."""' in init_file
    assert "import contextlib" in init_file
    assert "import importlib.metadata" in init_file
    assert '__version__ = "unknown"' in init_file
    assert 'importlib.metadata.version("my-cli-tool")' in init_file

    assert "src/my_cli_tool/cli.py" in manifest.file_injections
    cli_file = manifest.file_injections["src/my_cli_tool/cli.py"]
    assert "from my_cli_tool import __version__" in cli_file
    assert 'help="My awesome CLI tool."' in cli_file
    assert "def version_callback(value: bool) -> None:" in cli_file
    assert "@app.callback()" in cli_file

    assert "tests/test_cli.py" in manifest.file_injections
    test_file = manifest.file_injections["tests/test_cli.py"]
    assert "from my_cli_tool.cli import app" in test_file
    assert "def test_version() -> None:" in test_file
    assert "def test_help() -> None:" in test_file

    assert "README.md" in manifest.file_injections
    assert "# my-cli-tool" in manifest.file_injections["README.md"]

    # Verify [project.scripts] entry point
    assert "pyproject.toml" in manifest.file_appends
    pyproject_appends = manifest.file_appends["pyproject.toml"]
    assert any(
        'my-cli-tool = "my_cli_tool.cli:app"' in append for append in pyproject_appends
    )


def test_cli_preset_build_without_description(manifest):
    """Test that __init__.py has no docstring if description metadata is omitted."""
    manifest.metadata = {"project_name": "dark-matter"}
    preset = CliPreset()
    preset.build(manifest)

    init_file = manifest.file_injections["src/dark_matter/__init__.py"]
    assert not init_file.startswith('"""')
    assert init_file.startswith("import contextlib")
    assert 'importlib.metadata.version("dark-matter")' in init_file


def test_dsp_preset_build(manifest):
    """Test that the DSP preset injects audio processing pipelines."""
    preset = DspPreset()
    preset.build(manifest)

    assert "librosa" in manifest.dependencies
    assert "mutagen" in manifest.dependencies
    assert "data/raw_audio" in manifest.directories
    assert "*.wav" in manifest.vcs_ignores


def test_embedded_preset_build(manifest):
    """Test that the Embedded preset injects host-side hardware libraries."""
    preset = EmbeddedPreset()
    preset.build(manifest)

    assert "pyserial" in manifest.dependencies
    assert "esptool" in manifest.dependencies
    # Embedded preset doesn't currently require specific directories or ignores
    assert len(manifest.directories) == 0
    assert len(manifest.vcs_ignores) == 0


def test_preset_apply_overrides(manifest, mocker):
    """Test that a preset dynamically drops its default payload if a configuration override exists."""
    mock_config = mocker.patch("protostar.config.ProtostarConfig.load")

    # Mock the global config to return an override for the ML preset
    mock_config.return_value.presets = {
        "ml": {
            "dependencies": ["custom-torch"],
            "dev_dependencies": ["pytest-ml"],
            "directories": ["custom_models/"],
        }
    }

    preset = MLPreset()
    preset.build(manifest)

    # Verify defaults were bypassed
    assert "torch" not in manifest.dependencies
    assert "models" not in manifest.directories
    assert "*.pt" not in manifest.vcs_ignores

    # Verify custom payload was injected
    assert "custom-torch" in manifest.dependencies
    assert "pytest-ml" in manifest.dev_dependencies
    assert "custom_models/" in manifest.directories


def test_preset_metadata_declarations():
    """Test that PresetModule subclasses support required_metadata and optional_metadata."""

    class CustomPreset(PresetModule):
        required_metadata = ("required_field",)
        optional_metadata = ("optional_field",)

        @property
        def name(self) -> str:
            return "Custom"

    preset = CustomPreset()
    assert preset.required_metadata == ("required_field",)
    assert preset.optional_metadata == ("optional_field",)
