"""Recipe-driven, headless project inspection using shared reconciliation."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .config import TemplateSource, UserConfig
from .errors import (
    ConfigurationError,
    ExecutionInterruptedError,
    NetworkFetchError,
    ProtostarError,
    TemplateRefNotFoundError,
    UnversionedTemplateError,
)
from .executor import SystemExecutor
from .intent import TemplateOrigin, TemplateReference
from .journal import TransactionState
from .manifest import CollisionStrategy, EnvironmentManifest
from .merge import Resolutions
from .migrations import rename_variables, select_migrations
from .models import ExecutionResult, InitRequest, RollbackContext
from .modules import PythonCore, SystemWorkspaceModule
from .network import RefKind, RefListing, list_refs
from .options import OptionValue, resolve_options
from .orchestrator import Orchestrator
from .preparation import ExecutionPolicy, PreparedReview, prepare_review
from .progress import ProgressStep, no_progress
from .recipe import ProjectRecipe, read_recipe, select_tooling
from .registry import resolve_hook_revisions
from .secret_guard import check_variable_values
from .sync_state import STATE_FILE, SyncState, read_workspace_state

LATEST = "latest"
"""The ``sync --to`` value that names the newest release."""


@dataclass(frozen=True)
class TemplateUpstream:
    """What a forge template's repository offers beyond the applied revision.

    Attributes:
        ref: The ref the project applies.
        revision: The commit the project applies.
        kind: What ``ref`` names now, or None when the repository could not be
            listed or no longer has it.
        newer: The newest release after ``ref``, when ``ref`` is a release.
        moved: The commit ``ref`` names now, when that is not ``revision``.
        reachable: Whether the repository's refs could be listed.
    """

    ref: str
    revision: str
    kind: RefKind | None = None
    newer: str | None = None
    moved: str | None = None
    reachable: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serializes the upstream facts."""
        return {
            "ref": self.ref,
            "revision": self.revision,
            "kind": self.kind.value if self.kind else None,
            "newer": self.newer,
            "moved": self.moved,
            "reachable": self.reachable,
        }


def _upstream(
    reference: TemplateReference, listing: RefListing | None
) -> TemplateUpstream | None:
    if reference.ref is None or reference.revision is None:
        return None
    if listing is None:
        return TemplateUpstream(reference.ref, reference.revision, reachable=False)
    kind = listing.kind(reference.ref)
    current = (
        listing.resolve(reference.ref, reference.locator).revision
        if kind in (RefKind.TAG, RefKind.BRANCH)
        else reference.revision
    )
    return TemplateUpstream(
        reference.ref,
        reference.revision,
        kind,
        listing.newer(reference.ref) if kind is RefKind.TAG else None,
        current if current != reference.revision else None,
    )


@dataclass(frozen=True)
class PreparedProject:
    """One captured source revision and the decisions to review or apply."""

    manifest: EnvironmentManifest
    config: UserConfig
    review: PreparedReview
    upstream: TemplateUpstream | None = None

    def resolve(self, resolutions: Resolutions) -> "PreparedProject":
        """Reviews the same revision again with conflicts settled.

        The registry snapshot is reused, so the new review differs from this
        one only by the resolutions.

        Args:
            resolutions: Choices keyed by conflict identity.

        Returns:
            The project with a review of the resolved decisions.
        """
        return replace(
            self,
            review=prepare_review(
                self.manifest,
                self.config,
                hook_revisions=self.review.hook_revisions,
                resolutions=resolutions,
            ),
        )

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


@dataclass(frozen=True)
class LocatedProject:
    """A tracked project's recipe, ledger, and template, before rendering.

    The CLI reads the template's variables to learn which to ask for before
    ``prepare_project`` renders it.

    Attributes:
        recipe: The recipe, with its source at the ref this run applies.
        state: The committed ownership ledger.
        template: The template, acquired at that ref, or None.
        upstream: What the template's repository offers, for a forge template.
    """

    recipe: ProjectRecipe
    state: SyncState
    template: TemplateSource | None
    upstream: TemplateUpstream | None = None


def locate_project(to: str | None = None) -> LocatedProject:
    """Reads the current project and acquires its template, without prompts.

    A forge template's repository is listed once: to resolve a new ref, and
    to report what it offers. A listing failure only makes that report
    unavailable while the recorded commit can still be downloaded.

    Args:
        to: A tag, branch, commit, or ``latest``, to move the template to.

    Raises:
        ConfigurationError: If the recipe or ledger is missing or invalid.
        UnversionedTemplateError: If ``to`` is given for a template with no
            revisions.
        NetworkFetchError: If the template, or refs it needs, can't be fetched.
        TemplateRefNotFoundError: If ``to`` names nothing in the repository.
    """
    root = Path.cwd().resolve()
    recipe = read_recipe(root / "pyproject.toml")
    if recipe is None:
        raise ConfigurationError(
            "Project recipe is missing.",
            hint="Rerun your original explicit selection with init --force-merge to establish [tool.protostar].",
        )
    state = read_workspace_state(root)
    if state is None:
        raise ConfigurationError(
            "Project ownership state is missing.",
            hint=f"Rerun your original explicit selection with init --force-merge to establish {STATE_FILE}.",
        )
    source = recipe.source
    remote = source.remote if source else None
    if to is not None and (source is None or remote is None or not remote.versioned):
        raise UnversionedTemplateError()
    listing: RefListing | None = None
    if remote is not None and remote.versioned:
        try:
            listing = list_refs(remote)
        except NetworkFetchError:
            if to is not None:
                raise
    if source is not None and to is not None and listing is not None:
        ref = to
        if to == LATEST:
            latest = listing.latest(source.ref)
            if latest is None:
                raise TemplateRefNotFoundError(source.locator, LATEST, ())
            ref = latest
        listing.resolve(ref, source.locator)
        recipe = replace(recipe, source=replace(source, ref=ref))
        source = recipe.source
    try:
        # --to resolves its ref afresh, so naming the applied ref follows it.
        recorded = None if to is not None else state.template
        template = source.inspect(root, recorded, listing) if source else None
    except (OSError, UnicodeError) as error:
        raise ConfigurationError(
            "Cannot read the recorded template source.",
            hint="Verify its locator and UTF-8 source files.",
        ) from error
    if template is not None:
        recipe = replace(
            recipe,
            variables=tuple(
                sorted(
                    migrate_variables(template, state, dict(recipe.variables)).items()
                )
            ),
        )
    upstream = _upstream(template.reference, listing) if template else None
    return LocatedProject(recipe, state, template, upstream)


def migrate_variables(
    template: TemplateSource, state: SyncState | None, values: Mapping[str, str]
) -> dict[str, str]:
    """Moves recorded variable values to the names the template's migrations gave.

    Args:
        template: The template being applied.
        state: The project's committed ledger, whose template version the
            migrations run from; None for a project without one.
        values: The recorded variable values.

    Raises:
        ConfigurationError: If the template moves back across a migration.
    """
    if state is None or state.template is None:
        return dict(values)
    selected = select_migrations(
        template.migrations,
        state.template.version,
        template.version,
        state.template.migrated,
    )
    return rename_variables(values, selected)


def inspect_project() -> PreparedReview:
    """Reviews the explicit current project without prompts or subprocesses."""
    return prepare_project().review


def prepare_project(
    located: LocatedProject | None = None,
    *,
    variables: Mapping[str, str] | None = None,
    allowed_secrets: frozenset[str] = frozenset(),
    options: Mapping[str, OptionValue] | None = None,
) -> PreparedProject:
    """Captures a project once for shared inspection and lifecycle application.

    Args:
        located: The located project; the current one when None.
        variables: Values for template variables, over the recorded ones.
        allowed_secrets: Variables whose flagged values the user confirmed
            are not secrets.
        options: Values for template options, over the recorded ones.

    Raises:
        MissingTemplateVariablesError: If a template variable still has no
            value; sync never prompts.
        SecretDetectedError: If a new value looks like a credential.
        InvalidOptionValueError: If an option's value is one it doesn't offer.
    """
    located = located or locate_project()
    recipe, template = located.recipe, located.template
    if template is not None:
        recorded = dict(recipe.variables)
        given = dict(variables or {})
        # Only new values are checked; a recorded value was accepted when entered.
        check_variable_values(
            {
                name: value
                for name, value in given.items()
                if recorded.get(name) != value
            },
            allowed=allowed_secrets,
        )
        values = {
            name: value
            for name, value in {**recorded, **given}.items()
            if name in template.variables
        }
        # Values for options the template no longer offers are dropped.
        chosen = {
            name: value
            for name, value in {**dict(recipe.options), **dict(options or {})}.items()
            if name in template.options
        }
        resolve_options(template.options, chosen)
        recipe = replace(
            recipe,
            variables=tuple(sorted(values.items())),
            options=tuple(sorted(chosen.items())),
        )
    blueprint = template.render(recipe.rendering_context()) if template else None
    state = located.state
    # plan() rejects a template other than the recorded one.
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
        collision_strategy=CollisionStrategy.MERGE,
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
        manifest,
        config,
        prepare_review(manifest, config, hook_revisions=revisions),
        located.upstream,
    )
