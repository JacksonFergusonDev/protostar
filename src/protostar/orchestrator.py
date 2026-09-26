"""Orchestrator for the Protostar scaffolding engine."""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from . import system_deps
from .documents import community
from .errors import ExecutionInterruptedError, WorkspaceCollisionError
from .manifest import EnvironmentManifest, MissingTool, ProjectMetadata
from .merge import NO_RESOLUTIONS, Resolutions
from .models import ExecutionResult, InitRequest
from .modules import (
    AGENTS_TARGET,
    AgentsModule,
    BootstrapModule,
    CommunityModule,
    PreCommitModule,
    PrekModule,
    PythonCore,
)
from .options import Condition, resolve_options
from .progress import ProgressStep, no_progress
from .sync_state import check_one_shot_workspace, check_workspace_identity
from .workflows import (
    GuideSpec,
    HookRunner,
    generate_agents_md,
    generate_contributing_md,
    generate_pull_request_template,
)

if TYPE_CHECKING:
    from .config import UserConfig
    from .executor import SystemExecutor
    from .recipe import Tool
    from .registry import ResolvedHookRevision

logger = logging.getLogger("protostar")

__all__ = [
    "AGENTS_REGION_ID",
    "AGENTS_TARGET",
    "CONTRIBUTING_REGION_ID",
    "Orchestrator",
]

AGENTS_REGION_ID = "agents"
CONTRIBUTING_REGION_ID = "contributing"


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

    def plan(self, *, check_executables: bool = True) -> EnvironmentManifest:
        """Evaluates workspace state and assembles a declarative EnvironmentManifest.

        A fresh EnvironmentManifest is instantiated on every call, guaranteeing
        that retries (e.g. after a collision resolution) start from a clean slate.

        An enabled tool's executable missing from ``PATH`` never fails planning:
        it is recorded in ``missing_tools``, and the tool's module skips the
        steps that run it.

        Args:
            check_executables: Whether to require the executables Protostar
                itself runs. Only callers that never execute the plan, such
                as a read-only review, skip the check.

        Raises:
            ConfigurationError: If conflicting modules or missing prerequisites are
                detected, or the project's state records another template.
            MissingDependencyError: If an executable Protostar itself runs is
                missing.

        Returns:
            A populated EnvironmentManifest ready to be passed to execute().
        """
        req = self.request

        # Phase 1: Manifest instantiation & recipe selection
        manifest = EnvironmentManifest(
            template_reference=req.template_reference
            or (req.template_blueprint.reference if req.template_blueprint else None),
            collision_strategy=req.collision_strategy,
            one_shot=req.one_shot,
        )
        if req.one_shot:
            check_one_shot_workspace(Path.cwd())
        # A project never switches template, so no caller gets as far as
        # asking the user anything about one it can't apply.
        check_workspace_identity(Path.cwd(), manifest.template_reference)
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
        from .recipe import ProducerContribution, Tool, validate_tools

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
        validate_tools({Tool(m.config_key) for m in active_modules if m.config_key})
        if check_executables:
            system_deps.check_required_executables()
        # Recorded before any module builds, so each can skip what it can't run.
        manifest.missing_tools = frozenset(
            MissingTool(executable, Tool(mod.config_key))
            for mod in active_modules
            if mod.config_key
            for executable in mod.executables
            if not system_deps.installed(executable)
        )

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
            if mod.config_key in {"ci", "release", "just", "agents", "community"}:
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
        tooling = manifest.tooling
        guide = GuideSpec(
            python_version=manifest.recipe.python,
            hook_runner=tooling.hook_runner,
            wants_just=tooling.wants_just,
            format_commands=tooling.just_format_commands,
            lint_commands=tooling.just_lint_commands,
            typecheck_commands=tooling.just_typecheck_commands,
            ci_flags=tooling.ci_flags,
            conventional_commits=tooling.conventional_commits,
            wants_ci=tooling.wants_ci,
            one_shot=manifest.one_shot,
        )
        if tooling.wants_agents:
            producer = f"module:{AgentsModule.__name__}"
            tool = Tool.AGENTS
            manifest.filesystem.add_region(
                AGENTS_TARGET, generate_agents_md(guide), identity=AGENTS_REGION_ID
            )
        if tooling.wants_community:
            producer = f"module:{CommunityModule.__name__}"
            tool = Tool.COMMUNITY
            manifest.filesystem.add_region(
                community.CONTRIBUTING_TARGET,
                generate_contributing_md(guide),
                identity=CONTRIBUTING_REGION_ID,
            )
            manifest.filesystem.add_file_injection(
                community.PULL_REQUEST_TARGET, generate_pull_request_template(guide)
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
            manifest.migrations = tuple(blueprint.migrations)
            logger.debug("Injecting blueprint structural fields into manifest.")

            for edge in blueprint.dependency_includes:
                manifest.dependencies.add_include(edge.group, edge.include)

            for dep in blueprint.dependencies:
                manifest.dependencies.add(dep)

            active_tools = {m.config_key for m in active_modules if m.config_key}
            options = resolve_options(
                blueprint.options, dict(req.recipe.options) if req.recipe else {}
            )

            def holds(condition: Condition | None) -> bool:
                return condition is None or condition.holds(active_tools, options)

            for dep in blueprint.dev_dependencies:
                manifest.dependencies.add_dev(dep)

            for dep in blueprint.docs_dependencies:
                manifest.dependencies.add_docs(dep)

            for block in blueprint.optional:
                if not holds(block.requires):
                    logger.debug(f"Skipping content that requires {block.requires}.")
                    continue
                # Attribute a block bound to one tool to it, like module output.
                tool = _bound_tool(block.requires)
                for dep in block.dependencies:
                    manifest.dependencies.add(dep)
                for dep in block.dev_dependencies:
                    manifest.dependencies.add_dev(dep)
                for dep in block.docs_dependencies:
                    manifest.dependencies.add_docs(dep)
            tool = None

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
                    if not holds(payload.requires):
                        logger.debug(
                            f"Skipping payload '{identity}': it requires {payload.requires}."
                        )
                        continue
                    # Attribute a tool-bound payload to its tool, like module output.
                    tool = _bound_tool(payload.requires)
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
                        if not holds(record.requires):
                            continue
                        manifest.filesystem.add_region(
                            filepath,
                            record.content,
                            identity=f"template:{template_id}:{identity}",
                        )

            if blueprint.files:
                logger.debug("Injecting static files from configuration.")
                for filepath, content in blueprint.files.items():
                    gates = blueprint.gated(filepath)
                    # A file several blocks list ships while any of them holds.
                    if gates and not any(holds(gate.requires) for gate in gates):
                        continue
                    manifest.filesystem.add_file_injection(filepath, content)

        manifest.producer_contributions = tuple(contributions)
        from .manifest import _ignore_contribution

        manifest.dependencies.observe = _ignore_contribution
        manifest.filesystem.observe = _ignore_contribution
        manifest.tasks.observe = _ignore_contribution
        manifest.tooling.observe = _ignore_contribution

        # Phase 5: Manifest-First Collision Intercept
        manifest.collisions = frozenset(self._detect_collisions(manifest))

        return manifest

    def execute(
        self,
        manifest: EnvironmentManifest,
        *,
        hook_revisions: tuple[ResolvedHookRevision, ...] | None = None,
        progress: ProgressStep = no_progress,
        resolutions: Resolutions = NO_RESOLUTIONS,
    ) -> ExecutionResult:
        """Realizes the pre-built manifest on disk.

        Takes an already-built manifest from plan() and executes it. Performs no
        planning, collision detection, template resolution, or user interaction.

        Args:
            manifest: The populated EnvironmentManifest to execute.
            hook_revisions: The registry snapshot a review showed, so execution
                writes the same hook pins. Without one, execution takes its own.
            progress: Brackets each presentable execution step for the caller.
            resolutions: Choices the change review made for the conflicts it
                showed, keyed by conflict identity.

        Raises:
            ExecutionInterruptedError: If the user interrupts execution after
                disk mutations have already begun.

        Returns:
            An ExecutionResult describing what was touched and any diagnostics.
        """
        from .errors import ProtostarError
        from .journal import TransactionState
        from .models import RollbackContext

        if manifest.collisions and manifest.collision_strategy is None:
            raise WorkspaceCollisionError(paths=manifest.collisions)

        executor_cls: type[SystemExecutor] = sys.modules[__name__].SystemExecutor
        executor = executor_cls(
            manifest,
            self.user_config,
            self.request.docker,
            hook_revisions=hook_revisions,
            progress=progress,
            resolutions=resolutions,
        )

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
            missing_tools=manifest.missing_tools,
        )


def _bound_tool(condition: Condition | None) -> Tool | None:
    """Returns the one tool a condition names, which its content belongs to."""
    from .recipe import Tool

    names = condition.names if condition else frozenset()
    tools = [Tool(name) for name in sorted(names & {tool.value for tool in Tool})]
    return tools[0] if len(tools) == 1 else None


def __getattr__(name: str) -> Any:
    """Lazy evaluation for heavy executor dependencies."""
    if name == "SystemExecutor":
        from .executor import SystemExecutor

        globals()["SystemExecutor"] = SystemExecutor
        return SystemExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
