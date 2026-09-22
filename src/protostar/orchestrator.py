"""Orchestrator for the Protostar scaffolding engine."""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .errors import (
    AggregatedDependencyError,
    ConfigurationError,
    ExecutionInterruptedError,
    MissingDependencyError,
    WorkspaceCollisionError,
)
from .manifest import CollisionStrategy, EnvironmentManifest, ProjectMetadata
from .models import ExecutionResult, InitRequest
from .modules import (
    AgentsModule,
    BootstrapModule,
    PreCommitModule,
    PrekModule,
    PythonCore,
    ReadTheDocsModule,
    ZensicalModule,
)
from .preparation import ExecutionPolicy
from .system_deps import GlobalExecutable
from .workflows import AgentsSpec, HookRunner, generate_agents_md

if TYPE_CHECKING:
    from .config import UserConfig
    from .executor import SystemExecutor

logger = logging.getLogger("protostar")

__all__ = ["AGENTS_REGION_ID", "AGENTS_TARGET", "Orchestrator"]

AGENTS_TARGET = "AGENTS.md"
AGENTS_REGION_ID = "agents"


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
        return manifest.colliding_files()

    def plan(
        self, *, policy: ExecutionPolicy = ExecutionPolicy.INITIALIZATION
    ) -> EnvironmentManifest:
        """Evaluates workspace state and assembles a declarative EnvironmentManifest.

        A fresh EnvironmentManifest is instantiated on every call, guaranteeing
        that retries (e.g. after a collision resolution) start from a clean slate.

        Args:
            policy: Lifecycle reviews skip execution prerequisite checks.

        Raises:
            WorkspaceCollisionError: If collision targets exist on disk and no
                force flag (force_merge / force_replace) was provided in the request.
            ConfigurationError: If conflicting modules or missing prerequisites are detected.
            AggregatedDependencyError: If a module pre-flight check fails.

        Returns:
            A populated EnvironmentManifest ready to be passed to execute().
        """
        req = self.request

        # Phase 1: Manifest instantiation & recipe selection
        manifest = EnvironmentManifest(
            template_reference=req.template_reference
            or (req.template_blueprint.reference if req.template_blueprint else None),
            force_merge=req.force_merge,
            force_replace=req.force_replace,
        )
        if req.metadata:
            manifest.metadata.update(cast(ProjectMetadata, req.metadata))

        if req.docker:
            manifest.tooling.wants_docker = True

        from .recipe import RecipeIntent, decode_recipe, establish_recipe

        manifest.recipe = req.recipe or establish_recipe(
            self.user_config,
            RecipeIntent(
                manifest.template_reference,
                manifest.metadata,
                req.docker,
                req.python_version,
            ),
        )

        manifest.recipe = decode_recipe(manifest.recipe.to_dict())

        # Phase 2: Resolve the diversion ledger before module validation/build
        from .recipe import ProducerContribution, Tool

        opinions = (
            req.template_blueprint.tooling_overrides if req.template_blueprint else {}
        )
        manifest.selections = manifest.recipe.selections(opinions)
        enabled_tools = {
            selection.tool for selection in manifest.selections if selection.enabled
        }
        active_modules = [
            module
            for module in self.modules
            if req.recipe is None
            or not module.config_key
            or Tool(module.config_key) in enabled_tools
        ]
        # Pre-flight verification of effective producers only
        has_pre_commit = any(isinstance(m, PreCommitModule) for m in active_modules)
        has_prek = any(isinstance(m, PrekModule) for m in active_modules)
        if has_pre_commit and has_prek:
            raise ConfigurationError(
                "Cannot use both '--pre-commit' and '--prek' simultaneously. Please choose one git hook manager.",
                hint="Remove either --pre-commit or --prek from your selection.",
            )

        has_readthedocs = any(isinstance(m, ReadTheDocsModule) for m in active_modules)
        has_zensical = any(isinstance(m, ZensicalModule) for m in active_modules)
        if has_readthedocs and not has_zensical:
            raise ConfigurationError(
                "Read the Docs scaffolding requires the Zensical module to be enabled.",
                hint="Enable the Zensical documentation module (--zensical or [tooling] zensical = true) or remove the Read the Docs module.",
            )

        missing_deps: dict[GlobalExecutable, MissingDependencyError] = {}
        for mod in active_modules if policy is ExecutionPolicy.INITIALIZATION else []:
            try:
                mod.pre_flight()
            except MissingDependencyError as e:
                missing_deps[e.dependency] = e

        if missing_deps:
            raise AggregatedDependencyError(tuple(missing_deps.values()))

        producer = ""
        tool: Tool | None = None
        contributions: list[ProducerContribution] = []
        if req.docker:
            contributions.append(
                ProducerContribution("request", None, ("tooling", "wants_docker"))
            )

        def observe(scope: str, path: tuple[str, ...]) -> None:
            contributions.append(ProducerContribution(producer, tool, (scope, *path)))

        manifest.dependencies.observe = lambda path: observe("dependencies", path)
        manifest.filesystem.observe = lambda path: observe("filesystem", path)
        manifest.tasks.observe = lambda path: observe("tasks", path)
        manifest.tooling.observe = lambda path: observe("tooling", path)
        for mod in active_modules:
            producer = f"module:{type(mod).__name__}"
            tool = Tool(mod.config_key) if mod.config_key else None
            if isinstance(mod, PythonCore):
                mod.python_version = manifest.recipe.python
            # These command lists remain additive; capture every producer even
            # when another module declares the same command.
            command_fields = (
                "just_format_commands",
                "just_lint_commands",
                "just_typecheck_commands",
                "just_clean_paths",
            )
            lengths = {
                key: len(getattr(manifest.tooling, key)) for key in command_fields
            }
            before_ide = dict(manifest.ide_settings)
            mod.build(manifest)
            for key in command_fields:
                for command in getattr(manifest.tooling, key)[lengths[key] :]:
                    observe(
                        "tooling", (key, hashlib.sha256(command.encode()).hexdigest())
                    )
            if mod.config_key in {"ci", "release", "just", "agents"}:
                observe("tooling", (f"wants_{mod.config_key}",))
            for key, value in manifest.ide_settings.items():
                if before_ide.get(key) != value:
                    observe("ide_settings", (key,))

        # Phase 3b: Documents and tasks derived from the aggregated tooling state.
        # Rendered after every module builds so no module inspects its siblings,
        # and before template appends so a template's own AGENTS.md regions follow it.
        if manifest.tooling.wants_hooks:
            runner = manifest.tooling.hook_runner
            runner_module = PrekModule if runner is HookRunner.PREK else PreCommitModule
            producer = f"module:{runner_module.__name__}"
            tool = Tool(runner_module.config_key)
            # Every hook type is known only now, so each installed script is owned.
            hook_types = {"pre-commit", *manifest.tooling.pre_commit_install_hook_types}
            manifest.tasks.add_post_install_task(
                ["uv", "run", runner.value, "install"],
                description=f"Installing {runner.value} git hooks",
                owned_files=[f".git/hooks/{kind}" for kind in sorted(hook_types)],
            )
        if manifest.tooling.wants_agents:
            producer = f"module:{AgentsModule.__name__}"
            tool = Tool.AGENTS
            tooling = manifest.tooling
            manifest.filesystem.add_region(
                AGENTS_TARGET,
                generate_agents_md(
                    AgentsSpec(
                        python_version=manifest.recipe.python,
                        hook_runner=tooling.hook_runner,
                        wants_just=tooling.wants_just,
                        format_commands=tooling.just_format_commands,
                        lint_commands=tooling.just_lint_commands,
                        typecheck_commands=tooling.just_typecheck_commands,
                        ci_flags=tooling.ci_flags,
                    )
                ),
                identity=AGENTS_REGION_ID,
            )

        # Phase 4: Blueprint injection
        blueprint = req.template_blueprint
        if blueprint:
            template_id = (
                manifest.template_reference.identity
                if manifest.template_reference
                else "unresolved"
            )
            producer = f"template:{template_id}"
            tool = None
            logger.debug("Injecting blueprint structural fields into manifest.")

            for edge in blueprint.dependency_includes:
                manifest.dependencies.add_include(edge.group, edge.include)

            for dep in blueprint.dependencies:
                manifest.dependencies.add(dep)

            active_tools = {m.config_key for m in active_modules if m.config_key}
            for dep in blueprint.dev_dependencies:
                manifest.dependencies.add_dev(dep)

            for tool_key, packages in blueprint.tool_dev_dependencies.items():
                if tool_key not in active_tools:
                    logger.debug(f"Skipping {tool_key} dev dependencies: disabled.")
                    continue
                # Attribute the packages to their tool, like module output.
                tool = Tool(tool_key)
                for dep in packages:
                    manifest.dependencies.add_dev(dep)
            tool = None

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
                for identity, payload in blueprint.pyproject_injections.items():
                    if payload.requires and payload.requires not in active_tools:
                        logger.debug(
                            f"Skipping payload '{identity}': {payload.requires} is disabled."
                        )
                        continue
                    # Attribute a tool-bound payload to its tool, like module output.
                    tool = Tool(payload.requires) if payload.requires else None
                    manifest.filesystem.add_structured(
                        "pyproject.toml",
                        payload.content,
                        producer=f"template:{template_id}:{identity}",
                    )
                tool = None

            if blueprint.appends:
                logger.debug("Injecting generic file appends from configuration.")
                for filepath, payloads in blueprint.appends.items():
                    for identity, record in payloads.items():
                        manifest.filesystem.add_region(
                            filepath,
                            record.content,
                            identity=f"template:{template_id}:{identity}",
                        )

            if blueprint.files:
                logger.debug("Injecting static files from configuration.")
                for filepath, content in blueprint.files.items():
                    manifest.filesystem.add_file_injection(filepath, content)

        manifest.producer_contributions = tuple(contributions)
        from .manifest import _ignore_contribution

        manifest.dependencies.observe = _ignore_contribution
        manifest.filesystem.observe = _ignore_contribution
        manifest.tasks.observe = _ignore_contribution
        manifest.tooling.observe = _ignore_contribution

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
        from .errors import ProtostarError
        from .journal import TransactionState
        from .models import RollbackContext

        if (
            self.request.template_blueprint
            and self.request.template_blueprint.custom_variables
            and (
                manifest.recipe is None
                or not self.request.template_blueprint.custom_variables
                <= set(dict(manifest.recipe.bindings))
            )
        ):
            raise ConfigurationError(
                "Custom interpolation requires environment bindings.",
                hint="Enroll using init --bind VARIABLE=ENVIRONMENT for each custom template variable.",
            )

        executor_cls: type[SystemExecutor] = sys.modules[__name__].SystemExecutor
        executor = executor_cls(manifest, self.user_config, self.request.docker)

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


def __getattr__(name: str) -> Any:
    """Lazy evaluation for heavy executor dependencies."""
    if name == "SystemExecutor":
        from .executor import SystemExecutor

        globals()["SystemExecutor"] = SystemExecutor
        return SystemExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
