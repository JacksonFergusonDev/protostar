"""Codecov configuration merge spec."""

from ..merge import MergePolicy
from ..yaml_ast import YamlDocumentSpec

TARGET = ".github/codecov.yml"
SPEC = YamlDocumentSpec("Codecov", policy=MergePolicy(frozenset({("ignore",)})))
