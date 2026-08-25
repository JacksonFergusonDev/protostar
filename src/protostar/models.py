"""Public boundary types for the Protostar engine/CLI interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import TemplateBlueprint
from .manifest import DiagnosticEvent

__all__ = ["ExecutionResult", "InitRequest"]


@dataclass
class InitRequest:
    """Declarative intent from the caller for a scaffolding run.

    Attributes:
        template_blueprint: An optional pre-loaded template blueprint to apply.
        python_version: An optional Python version string (e.g. '3.13'). Informational;
            the modules list is already constructed with the resolved version.
        docker: If True, scaffolds container artifacts (.dockerignore, Dockerfile).
        force_merge: If True, bypasses collision prompts and forces a merge strategy.
        force_replace: If True, bypasses collision prompts and forces an overwrite strategy.
        metadata: Pre-resolved metadata dictionary to inject into the manifest.
        is_external: If True, the template was loaded from an external (untrusted) source.
        is_user_aliased: If True, the template was resolved via a trusted global config alias.
    """

    template_blueprint: TemplateBlueprint | None = None
    python_version: str | None = None
    docker: bool = False
    force_merge: bool = False
    force_replace: bool = False
    metadata: dict[str, Any] | None = field(default=None)
    is_external: bool = False
    is_user_aliased: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    """Observed outcome returned by Orchestrator.execute().

    Attributes:
        touched_paths: Immutable set of relative paths written or created on disk.
        diagnostics: Ordered tuple of non-fatal diagnostic events emitted during execution.
    """

    touched_paths: frozenset[str]
    diagnostics: tuple[DiagnosticEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serializes the execution result to a JSON-safe dictionary.

        The ``touched_paths`` frozenset is emitted as a sorted list for deterministic
        output. Each diagnostic event is emitted as an explicit dict; the optional
        ``detail`` field is omitted when absent to keep payloads compact.

        Returns:
            A JSON-serializable dictionary representation.
        """
        diagnostics: list[dict[str, Any]] = []
        for event in self.diagnostics:
            entry: dict[str, Any] = {
                "phase": str(event.phase),
                "message": event.message,
                "severity": event.severity.value,
            }
            if event.detail is not None:
                entry["detail"] = event.detail
            diagnostics.append(entry)

        return {
            "touched_paths": sorted(self.touched_paths),
            "diagnostics": diagnostics,
        }
