"""Orchestrator for the Protostar scaffolding engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .errors import (
    AggregatedDependencyError,
    ConfigurationError,
    ExecutionInterruptedError,
    MissingDependencyError,
    WorkspaceCollisionError,
)
from .executor import SystemExecutor
from .manifest import CollisionStrategy, EnvironmentManifest, ProjectMetadata
from .models import ExecutionResult, InitRequest
from .modules import (
    BootstrapModule,
    PreCommitModule,
    PrekModule,
    ReadTheDocsModule,
    ZensicalModule,
)
from .system_deps import GlobalExecutable

if TYPE_CHECKING:
    from .config import UserConfig

logger = logging.getLogger("protostar")

__all__ = ["Orchestrator"]


class Orchestrator:
    """Manages the lifecycle of the Python environment scaffolding process.

    The orchestrator provides a strict two-phase API:
    - plan(): Evaluates the workspace state and assembles a declarative
      EnvironmentManifest without mutating the filesystem.
    - execute(): Takes an already-built manifest and realizes it on disk.

    This separation guarantees that plan() is always safe to retry (it
    instantiates a fresh manifest on every call), and that execute() never
    performs planning, collision detection, or user interaction.
    """

    def __init__(
        self,
        modules: list[BootstrapModule],
        user_config: UserConfig,
        request: InitRequest | None = None,
    ) -> None:
        """Initializes the orchestrator with the requested modules and intent.

        Args:
            modules: The ordered stack of bootstrap layers to apply.
            user_config: The active UserConfig instance.
            request: Optional InitRequest describing caller intent. Defaults to a
                no-op InitRequest if omitted.
        """
        self.modules = modules
        self.user_config = user_config
        self.request = request or InitRequest()

    def _detect_collisions(self, manifest: EnvironmentManifest) -> set[Path]:
        """Detects workspace collision targets declared by the populated manifest.

        Args:
            manifest: The populated EnvironmentManifest.

        Returns:
            A set of existing Path objects that collide with planned files.
        """
        return {target for target in manifest.target_files() if target.exists()}

    def plan(self) -> EnvironmentManifest:
        """Evaluates workspace state and assembles a declarative EnvironmentManifest.

        A fresh EnvironmentManifest is instantiated on every call, guaranteeing
        that retries (e.g. after a collision resolution) start from a clean slate.

        Raises:
            WorkspaceCollisionError: If collision targets exist on disk and no
                force flag (force_merge / force_replace) was provided in the request.
            ConfigurationError: If conflicting modules or missing prerequisites are detected.
            AggregatedDependencyError: If a module pre-flight check fails.

        Returns:
            A populated EnvironmentManifest ready to be passed to execute().
        """
        req = self.request

        # Phase 1: Pre-flight verification
        has_pre_commit = any(isinstance(m, PreCommitModule) for m in self.modules)
        has_prek = any(isinstance(m, PrekModule) for m in self.modules)
        if has_pre_commit and has_prek:
            raise ConfigurationError(
                "Cannot use both '--pre-commit' and '--prek' simultaneously. Please choose one git hook manager.",
                hint="Remove either --pre-commit or --prek from your selection.",
            )

        has_readthedocs = any(isinstance(m, ReadTheDocsModule) for m in self.modules)
        has_zensical = any(isinstance(m, ZensicalModule) for m in self.modules)
        if has_readthedocs and not has_zensical:
            raise ConfigurationError(
                "Read the Docs scaffolding requires the Zensical module to be enabled.",
                hint="Enable the Zensical documentation module (--zensical or [tooling] zensical = true) or remove the Read the Docs module.",
            )

        missing_deps: dict[GlobalExecutable, MissingDependencyError] = {}
        for mod in self.modules:
            try:
                mod.pre_flight()
            except MissingDependencyError as e:
                missing_deps[e.dependency] = e

        if missing_deps:
            raise AggregatedDependencyError(tuple(missing_deps.values()))

        # Phase 2: Manifest instantiation & initialization
        manifest = EnvironmentManifest(
            force_merge=req.force_merge,
            force_replace=req.force_replace,
        )
        if req.metadata:
            manifest.metadata.update(cast(ProjectMetadata, req.metadata))

        if req.docker:
            manifest.tooling.wants_docker = True

        # Phase 3: Module aggregation
        for mod in self.modules:
            mod.build(manifest)

        # Phase 4: Blueprint injection
        blueprint = req.template_blueprint
        if blueprint:
            logger.debug("Injecting blueprint structural fields into manifest.")

            for dep in blueprint.dependencies:
                manifest.dependencies.add(dep)

            for dep in blueprint.dev_dependencies:
                manifest.dependencies.add_dev(dep)

            for dep in blueprint.docs_dependencies:
                manifest.dependencies.add_docs(dep)

            for d in blueprint.directories:
                manifest.filesystem.add_directory(d)

            for ig in blueprint.vcs_ignores:
                manifest.filesystem.add_vcs_ignore(ig)

            for cmd in blueprint.system_tasks:
                manifest.tasks.add_system_task(cmd)

            for cmd in blueprint.post_install_tasks:
                manifest.tasks.add_post_install_task(cmd)

            if blueprint.pyproject_injections:
                logger.debug("Injecting pyproject.toml payloads from configuration.")
                for payload in blueprint.pyproject_injections.values():
                    manifest.filesystem.add_file_append("pyproject.toml", payload)

            if blueprint.appends:
                logger.debug("Injecting generic file appends from configuration.")
                for filepath, payloads in blueprint.appends.items():
                    for payload in payloads:
                        manifest.filesystem.add_file_append(filepath, payload)

            if blueprint.files:
                logger.debug("Injecting static files from configuration.")
                for filepath, content in blueprint.files.items():
                    manifest.filesystem.add_file_injection(filepath, content)

        # Phase 5: Manifest-First Collision Intercept
        collision_targets = self._detect_collisions(manifest)
        if collision_targets:
            if req.force_replace:
                logger.debug(
                    "--force-replace flag provided. Defaulting to OVERWRITE collision strategy."
                )
                manifest.collision_strategy = CollisionStrategy.OVERWRITE
            elif req.force_merge:
                logger.debug(
                    "--force-merge flag provided. Defaulting to MERGE collision strategy."
                )
                manifest.collision_strategy = CollisionStrategy.MERGE
            else:
                raise WorkspaceCollisionError(
                    paths=frozenset(collision_targets),
                )

        return manifest

    def execute(self, manifest: EnvironmentManifest) -> ExecutionResult:
        """Realizes the pre-built manifest on disk.

        Takes an already-built manifest from plan() and executes it. Performs no
        planning, collision detection, template resolution, or user interaction.

        Args:
            manifest: The populated EnvironmentManifest to execute.

        Raises:
            ExecutionInterruptedError: If the user interrupts execution after
                disk mutations have already begun.

        Returns:
            An ExecutionResult describing what was touched and any diagnostics.
        """
        executor = SystemExecutor(manifest, self.user_config, self.request.docker)

        from .errors import ProtostarError
        from .journal import TransactionState
        from .models import RollbackContext

        try:
            executor.execute()
        except KeyboardInterrupt:
            raise ExecutionInterruptedError(
                RollbackContext(
                    touched_paths=frozenset(executor.journal.touched_paths),
                    completed_tasks=tuple(executor.completed_tasks),
                    interrupted_task=executor.interrupted_task,
                    is_external=self.request.is_external,
                )
            ) from None
        except ProtostarError as e:
            if getattr(executor.journal, "state", None) == TransactionState.ROLLED_BACK:
                e.rollback_context = RollbackContext(
                    touched_paths=frozenset(executor.journal.touched_paths),
                    completed_tasks=tuple(executor.completed_tasks),
                    interrupted_task=executor.interrupted_task,
                    is_external=self.request.is_external,
                )
            raise

        return ExecutionResult(
            created_paths=executor.journal.created_paths,
            mutated_paths=executor.journal.mutated_paths,
            diagnostics=tuple(executor.diagnostics),
        )
