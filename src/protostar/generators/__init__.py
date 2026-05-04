from .base import TargetGenerator
from .embedded import CircuitPythonGenerator, PlatformIOGenerator

# O(1) dynamic dispatch registry for the CLI
GENERATOR_REGISTRY: dict[str, TargetGenerator] = {}


def _register_generators() -> None:
    """Instantiates and registers all concrete generator classes."""
    # Instantiate directly to satisfy mypy's strict type inference
    instances: tuple[TargetGenerator, ...] = (
        CircuitPythonGenerator(),
        PlatformIOGenerator(),
    )

    for instance in instances:
        GENERATOR_REGISTRY[instance.target_name] = instance


_register_generators()

__all__ = ["GENERATOR_REGISTRY", "TargetGenerator"]
