"""Preset module for digital signal processing and audio analysis."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class DspPreset(PresetModule):
    """Injects waveform, MIDI, and spectral analysis dependencies."""

    cli_flags = ("-d", "--dsp")
    cli_help = "Inject digital signal processing dependencies"

    @property
    def name(self) -> str:
        return "Digital Signal Processing"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends audio processing packages, directories, and audio file ignores."""
        logger.debug("Building DSP preset layer.")

        packages = [
            "librosa",
            "soundfile",
            "mido",
            "mutagen",
            "pydub",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)

        # Scaffold directories for sample management and track processing
        for directory in ["data/raw_audio", "data/processed"]:
            manifest.add_directory(directory)

        # Ignore standard audio and metadata artifacts to keep the VCS tree clean
        for artifact in ["*.wav", "*.mp3", "*.flac", "*.mid", "*.midi", "*.ogg"]:
            manifest.add_vcs_ignore(artifact)
