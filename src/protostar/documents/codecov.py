"""Codecov configuration merge spec and the locations Codecov reads it from."""

from ..merge import MergePolicy
from ..yaml_ast import YamlDocumentSpec
from .locations import DocumentLocations

TARGET = ".github/codecov.yml"
SPEC = YamlDocumentSpec("Codecov", policy=MergePolicy(frozenset({("ignore",)})))
_NAMES = ("codecov.yml", ".codecov.yml", "codecov.yaml", ".codecov.yaml")
# Codecov reads one of these names at the repository root, else in dev/ or
# .github/, and uses the first it finds.
LOCATIONS = DocumentLocations(
    TARGET,
    aliases=tuple(
        path
        for folder in ("", ".github/", "dev/")
        for name in _NAMES
        if (path := folder + name) != TARGET
    ),
)
