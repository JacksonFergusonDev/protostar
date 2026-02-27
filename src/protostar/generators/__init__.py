from .base import TargetGenerator
from .cpp import CMakeGenerator, CppClassGenerator
from .embedded import CircuitPythonGenerator, PlatformIOGenerator
from .latex import LatexGenerator

# O(1) dynamic dispatch registry for the CLI
GENERATOR_REGISTRY: dict[str, TargetGenerator] = {}


def _register_generators() -> None:
    """Instantiates and registers all concrete generator classes."""
    # Instantiate directly to satisfy mypy's strict type inference
    instances: tuple[TargetGenerator, ...] = (
        LatexGenerator(),
        CppClassGenerator(),
        CMakeGenerator(),
        CircuitPythonGenerator(),
        PlatformIOGenerator(),
    )

    for instance in instances:
        GENERATOR_REGISTRY[instance.target_name] = instance


_register_generators()

__all__ = ["GENERATOR_REGISTRY", "TargetGenerator"]
