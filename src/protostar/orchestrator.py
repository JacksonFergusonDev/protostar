"""Orchestrator for the Protostar scaffolding engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .errors import PartialExecutionAbortedError, WorkspaceCollisionError
from .executor import SystemExecutor
from .manifest import CollisionStrategy, EnvironmentManifest, ProjectMetadata
from .models import ExecutionResult, InitRequest
from .modules import BootstrapModule

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

    def plan(self) -> EnvironmentManifest:
        """Evaluates workspace state and assembles a declarative EnvironmentManifest.

        A fresh EnvironmentManifest is instantiated on every call, guaranteeing
        that retries (e.g. after a collision resolution) start from a clean slate.

        Raises:
            WorkspaceCollisionError: If collision markers exist on disk and no
                force flag (force_merge / force_replace) was provided in the request.
            MissingDependencyError: If a module pre-flight check fails.

        Returns:
            A populated EnvironmentManifest ready to be passed to execute().
        """
        req = self.request

        # Phase 1: Instantiate a fresh manifest for every plan() call
        manifest = EnvironmentManifest(
            force_merge=req.force_merge,
            force_replace=req.force_replace,
        )

        # Phase 2: Collision intercept (raises instead of prompting)
        collision_targets: set[Path] = set()
        for mod in self.modules:
            for marker in mod.collision_markers:
                if marker.exists():
                    collision_targets.add(marker)

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

        # Phase 3: Pre-flight verification
        for mod in self.modules:
            mod.pre_flight()

        # Phase 4: Manifest aggregation
        if req.metadata:
            manifest.metadata.update(cast(ProjectMetadata, req.metadata))

        for mod in self.modules:
            mod.build(manifest)

        # Phase 5: Blueprint injection
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

        return manifest

    def execute(self, manifest: EnvironmentManifest) -> ExecutionResult:
        """Realizes the pre-built manifest on disk.

        Takes an already-built manifest from plan() and executes it. Performs no
        planning, collision detection, template resolution, or user interaction.

        Args:
            manifest: The populated EnvironmentManifest to execute.

        Raises:
            PartialExecutionAbortedError: If the user interrupts execution after
                disk mutations have already begun.

        Returns:
            An ExecutionResult describing what was touched and any diagnostics.
        """
        executor = SystemExecutor(manifest, self.user_config, self.request.docker)
        try:
            executor.execute()
        except KeyboardInterrupt:
            raise PartialExecutionAbortedError(
                frozenset(executor.touched_paths)
            ) from None

        return ExecutionResult(
            touched_paths=frozenset(executor.touched_paths),
            diagnostics=tuple(executor.diagnostics),
        )
