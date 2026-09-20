"""Opinionated templates and template discovery for Protostar."""

from .discovery import (
    TemplateInfo,
    TemplateType,
    builtin_template_aliases,
    discover_templates,
)

__all__ = [
    "TemplateInfo",
    "TemplateType",
    "builtin_template_aliases",
    "discover_templates",
]
