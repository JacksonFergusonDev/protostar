"""Recipe-driven, headless project inspection using shared reconciliation."""

from dataclasses import dataclass, replace
from pathlib import Path

from .config import UserConfig
from .errors import (
    ConfigurationError,
    ExecutionInterruptedError,
    ProtostarError,
    TemplateResolutionError,
)
from .executor import SystemExecutor
from .intent import TemplateOrigin
from .journal import TransactionState
from .manifest import EnvironmentManifest
from .models import ExecutionResult, InitRequest, RollbackContext
from .modules import PythonCore, SystemWorkspaceModule
from .orchestrator import Orchestrator
from .preparation import ExecutionPolicy, PreparedReview, prepare_review
from .progress import ProgressStep, no_progress
from .recipe import read_recipe, select_tooling
from .registry import resolve_hook_revisions
from .review_workspace import capture_node
from .sync_state import check_template_identity, deserialize_state


@dataclass(frozen=True)
class PreparedProject:
    """One captured source revision and the decisions to review or apply."""

    manifest: EnvironmentManifest
    config: UserConfig
    review: PreparedReview

    def apply(self, *, progress: ProgressStep = no_progress) -> ExecutionResult:
        """Applies lifecycle decisions atomically, with structured rollback reporting.

        Args:
            progress: Brackets each resolver subprocess for the caller.
        """
        executor = SystemExecutor(
            self.manifest, self.config, review=self.review, progress=progress
        )
        try:
            executor.execute()
        except (KeyboardInterrupt, ProtostarError) as error:
            context = RollbackContext(
                touched_paths=frozenset(executor.journal.touched_paths),
                completed_tasks=tuple(executor.completed_tasks),
                interrupted_task=executor.interrupted_task,
                is_external=bool(
                    self.manifest.template_reference
                    and self.manifest.template_reference.origin
                    is not TemplateOrigin.BUILT_IN
                ),
            )
            if isinstance(error, KeyboardInterrupt):
                raise ExecutionInterruptedError(context) from error
            if executor.journal.state is TransactionState.ROLLED_BACK:
                error.rollback_context = context
            raise
        return ExecutionResult(
            created_paths=executor.journal.created_paths,
            mutated_paths=executor.journal.mutated_paths,
            diagnostics=tuple(executor.diagnostics),
        )


def inspect_project() -> PreparedReview:
    """Reviews the explicit current project without prompts or subprocesses."""
    return prepare_project().review


def prepare_project() -> PreparedProject:
    """Captures a project once for shared inspection and lifecycle application."""
    root = Path.cwd().resolve()
    recipe = read_recipe(root / "pyproject.toml")
    if recipe is None:
        raise ConfigurationError(
            "Project recipe is missing.",
            hint="Rerun your original explicit selection with init --force-merge to establish [tool.protostar].",
        )
    state_input = capture_node(root / ".protostar.lock.toml")
    if state_input.file_content is None:
        raise ConfigurationError(
            "Project ownership state is missing.",
            hint="Rerun your original explicit selection with init --force-merge to establish .protostar.lock.toml.",
        )
    try:
        state = deserialize_state(state_input.file_content.decode())
    except UnicodeError as error:
        raise ConfigurationError(
            "Invalid project ownership state.",
            hint="Correct .protostar.lock.toml encoding.",
        ) from error
    context = recipe.rendering_context()

    try:
        blueprint = recipe.source.inspect(root, context) if recipe.source else None
    except ProtostarError as error:
        # Template parsing can mention rendered values; recipe bindings must
        # never appear in diagnostic messages, even for invalid rendered input.
        if isinstance(
            error, TemplateResolutionError
        ) and "Template requires variables:" in str(error):
            raise ConfigurationError(
                "Template variables lack environment bindings.",
                hint="Add variable-to-environment-name entries under [tool.protostar.bindings].",
            ) from error
        if recipe.bindings:
            raise ConfigurationError(
                "Cannot load the recorded template with its environment bindings.",
                hint="Verify the recorded source, [tool.protostar.bindings], and environment values.",
            ) from error
        raise
    except (OSError, UnicodeError) as error:
        raise ConfigurationError(
            "Cannot read the recorded template source.",
            hint="Verify its locator and UTF-8 source files.",
        ) from error
    if blueprint and not blueprint.custom_variables <= set(dict(recipe.bindings)):
        raise ConfigurationError(
            "Template variables lack environment bindings.",
            hint="Add variable-to-environment-name entries under [tool.protostar.bindings].",
        )
    check_template_identity(state, blueprint.reference if blueprint else None)
    if blueprint and blueprint.reference and state.template:
        blueprint.reference = replace(
            blueprint.reference, display_name=state.template.display_name
        )
    config = UserConfig(python_version=recipe.python, ide=recipe.ide)
    modules = [
        SystemWorkspaceModule(),
        PythonCore(python_version=recipe.python),
        *select_tooling(recipe, blueprint.tooling_overrides if blueprint else {}),
    ]
    request = InitRequest(
        recipe=recipe,
        template_blueprint=blueprint,
        python_version=recipe.python,
        docker=recipe.docker,
        force_merge=True,
        metadata={
            key: list(value) if isinstance(value, tuple) else value
            for key, value in recipe.metadata
        },
    )
    manifest = Orchestrator(modules, config, request).plan(
        policy=ExecutionPolicy.LIFECYCLE
    )
    revisions = resolve_hook_revisions()
    return PreparedProject(
        manifest, config, prepare_review(manifest, config, hook_revisions=revisions)
    )
