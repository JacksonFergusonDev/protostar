"""Public boundary types for the Protostar engine/CLI interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import TemplateBlueprint
from .intent import TemplateReference
from .manifest import DiagnosticEvent, SystemTask
from .recipe import ProjectRecipe

__all__ = ["ExecutionResult", "InitRequest", "RollbackContext"]


@dataclass(frozen=True)
class RollbackContext:
    """Structured data payload describing a successful transactional rollback."""

    touched_paths: frozenset[str]
    completed_tasks: tuple[SystemTask, ...]
    interrupted_task: SystemTask | None
    is_external: bool

    def to_dict(self) -> dict[str, Any]:
        """Serializes the rollback context to a JSON-safe dictionary."""
        return {
            "touched_paths": sorted(self.touched_paths),
            "completed_tasks": [t.to_dict() for t in self.completed_tasks],
            "interrupted_task": self.interrupted_task.to_dict()
            if self.interrupted_task
            else None,
            "is_external": self.is_external,
        }


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
        is_external: If True, the template was loaded from an external source.
        is_user_aliased: If True, the template was resolved via a global config alias.
        is_trusted: If True, the template source is explicitly trusted to execute tasks.
    """

    recipe: ProjectRecipe | None = None
    template_blueprint: TemplateBlueprint | None = None
    template_reference: TemplateReference | None = None
    python_version: str | None = None
    docker: bool = False
    force_merge: bool = False
    force_replace: bool = False
    metadata: dict[str, Any] | None = field(default=None)
    is_external: bool = False
    is_user_aliased: bool = False
    is_trusted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializes caller intent without trust or secret metadata."""
        reference = self.template_reference or (
            self.template_blueprint.reference if self.template_blueprint else None
        )
        return {
            "template_reference": reference.to_dict() if reference else None,
            "python_version": self.python_version,
            "docker": self.docker,
            "force_merge": self.force_merge,
            "force_replace": self.force_replace,
        }


@dataclass(frozen=True)
class ExecutionResult:
    """Observed outcome returned by Orchestrator.execute().

    Attributes:
        created_paths: Immutable set of relative paths created on disk.
        mutated_paths: Immutable set of relative paths modified on disk.
        diagnostics: Ordered tuple of non-fatal diagnostic events emitted during execution.
    """

    created_paths: frozenset[str]
    mutated_paths: frozenset[str]
    diagnostics: tuple[DiagnosticEvent, ...]

    @property
    def touched_paths(self) -> frozenset[str]:
        """Returns the union of created and mutated paths."""
        return self.created_paths | self.mutated_paths

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
            if event.conflict is not None:
                location = event.conflict.location
                entry["conflict"] = {
                    "file": location.file,
                    "keys": list(location.keys),
                    "identity": location.identity,
                    "reason": event.conflict.reason.value,
                }
            diagnostics.append(entry)

        return {
            "created_paths": sorted(self.created_paths),
            "mutated_paths": sorted(self.mutated_paths),
            "touched_paths": sorted(self.touched_paths),
            "diagnostics": diagnostics,
        }
