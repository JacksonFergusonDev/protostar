"""Preset modules for domain-specific environment scaffolding."""

from .api import ApiPreset
from .astro import AstroPreset
from .base import PresetModule
from .cli import CliPreset
from .dsp import DspPreset
from .embedded import EmbeddedPreset
from .ml import MLPreset
from .scientific import ScientificPreset

PRESETS: tuple[PresetModule, ...] = (
    ScientificPreset(),
    AstroPreset(),
    DspPreset(),
    EmbeddedPreset(),
    MLPreset(),
    ApiPreset(),
    CliPreset(),
)

__all__ = [
    "PresetModule",
    "PRESETS",
]
