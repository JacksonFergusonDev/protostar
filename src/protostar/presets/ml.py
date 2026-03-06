"""Preset module for machine learning and deep learning workflows."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class MLPreset(PresetModule):
    """Injects core deep learning dependencies and model training directories."""

    cli_flags = ("--ml",)
    cli_help = "Inject machine learning and deep learning dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "Machine Learning"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends ML packages, training directories, and telemetry ignores.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Machine Learning preset layer.")

        if self._apply_overrides(manifest):
            return

        packages = [
            "torch",
            "scikit-learn",
            "huggingface_hub",
            "tqdm",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)

        # Scaffold standard directories for training loops and EDA
        for directory in ["models", "data", "notebooks", "src"]:
            manifest.add_directory(directory)

        # Ignore serialized weights and telemetry bloat
        for artifact in [
            "*.pt",
            "*.pth",
            "*.safetensors",
            "*.onnx",
            "*.log",
            "wandb/",
            "mlruns/",
            "runs/",
        ]:
            manifest.add_vcs_ignore(artifact)
