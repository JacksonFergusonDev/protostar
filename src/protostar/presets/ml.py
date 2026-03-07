"""Preset module for machine learning and deep learning workflows."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class MLPreset(PresetModule):
    """Injects core deep learning dependencies and model training directories."""

    cli_flags = ("--ml",)
    cli_help = "Inject machine learning and deep learning dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Machine Learning"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["torch", "scikit-learn", "huggingface_hub", "tqdm"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["models", "data", "notebooks", "src"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return [
            "*.pt",
            "*.pth",
            "*.safetensors",
            "*.onnx",
            "*.log",
            "wandb/",
            "mlruns/",
            "runs/",
        ]
