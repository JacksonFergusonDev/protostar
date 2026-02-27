"""Preset modules for domain-specific environment scaffolding."""

from .astro import AstroPreset
from .base import PresetModule
from .dsp import DspPreset
from .embedded import EmbeddedPreset
from .scientific import ScientificPreset

PRESETS: tuple[PresetModule, ...] = (
    ScientificPreset(),
    AstroPreset(),
    DspPreset(),
    EmbeddedPreset(),
)

__all__ = [
    "PresetModule",
    "PRESETS",
]
