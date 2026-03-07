"""Preset module for digital signal processing and audio analysis."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class DspPreset(PresetModule):
    """Injects waveform, MIDI, and spectral analysis dependencies."""

    cli_flags = ("-d", "--dsp")
    cli_help = "Inject digital signal processing dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Digital Signal Processing"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["librosa", "soundfile", "mido", "mutagen", "pydub"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["data/raw_audio", "data/processed"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return ["*.wav", "*.mp3", "*.flac", "*.mid", "*.midi", "*.ogg"]
