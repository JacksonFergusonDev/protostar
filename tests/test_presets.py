from protostar.presets import (
    AstroPreset,
    DspPreset,
    EmbeddedPreset,
    ScientificPreset,
)


def test_scientific_preset_build(manifest):
    """Test that the Scientific preset injects data pipelines."""
    preset = ScientificPreset()
    preset.build(manifest)

    assert "astropy" in manifest.dependencies
    assert "numpy" in manifest.dependencies
    assert "notebooks" in manifest.directories
    assert "*.parquet" in manifest.vcs_ignores


def test_astro_preset_build(manifest):
    """Test that the Astro preset injects observational formats."""
    preset = AstroPreset()
    preset.build(manifest)

    assert "gwpy" in manifest.dependencies
    assert "data/fits" in manifest.directories
    assert "*.fits" in manifest.vcs_ignores


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
