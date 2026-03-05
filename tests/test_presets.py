from protostar.presets import (
    ApiPreset,
    AstroPreset,
    CliPreset,
    DspPreset,
    EmbeddedPreset,
    MLPreset,
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


def test_astro_preset_build(manifest):
    """Test that the Astro preset injects observational formats."""
    preset = AstroPreset()
    preset.build(manifest)

    assert "photutils" in manifest.dependencies
    assert "data/fits" in manifest.directories
    assert "*.fits" in manifest.vcs_ignores


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
    """Test that the CLI preset injects terminal frameworks and source bounds."""
    preset = CliPreset()
    preset.build(manifest)

    assert "typer" in manifest.dependencies
    assert "rich" in manifest.dependencies
    assert "src" in manifest.directories
    assert "tests" in manifest.directories


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
