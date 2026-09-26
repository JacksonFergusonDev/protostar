"""Transactional application of prepared byte and resolver decisions."""

import shlex
from pathlib import Path

from .config import UserConfig
from .dependencies import install_dependencies
from .errors import ConfigurationError, FileSystemError, StaleReviewError
from .fs_transaction import TransactionAwareFS
from .ide import check_ide_extensions
from .intent import ResolverFootprint
from .journal import MutationJournal
from .manifest import (
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
    SystemTask,
)
from .merge import NO_RESOLUTIONS, MergeConflict, Resolutions
from .preparation import (
    ExecutionPolicy,
    PreparationPhase,
    PreparedReview,
    manifest_digest,
    prepare_review,
)
from .progress import ProgressStep, no_progress
from .reconciliation import Reconciliation
from .registry import ResolvedHookRevision, resolve_hook_revisions
from .review_workspace import LiveWorkspace
from .security import enforce_binary_safelist, enforce_path_jail
from .sync_state import SyncState, check_one_shot_workspace, serialize_state
from .system import ProcessRunner, shield_sigint
from .workspace import validate_resolver_workspace

__all__ = ["SystemExecutor"]


class SystemExecutor(Reconciliation):
    """Applies prepared decisions and manages transactional process execution."""

    journal: MutationJournal
    fs: TransactionAwareFS
    workspace: LiveWorkspace

    def __init__(
        self,
        manifest: EnvironmentManifest,
        config: UserConfig,
        docker: bool = False,
        *,
        review: PreparedReview | None = None,
        hook_revisions: tuple[ResolvedHookRevision, ...] | None = None,
        progress: ProgressStep = no_progress,
        resolutions: Resolutions = NO_RESOLUTIONS,
    ) -> None:
        """Initializes the executor with the target manifest state.

        Args:
            manifest: The centralized state object containing all execution directives.
            config: The active Protostar configuration instance.
            docker: If True, scaffolds a .dockerignore from the manifest ignores.
            review: Captured lifecycle decisions; consumes their frozen registry snapshot.
            hook_revisions: The registry snapshot a caller already reviewed. Without
                one or a review, the executor takes its own when hooks are wanted.
            progress: Brackets each subprocess and the initial scaffold for a presenter.
            resolutions: Choices a change review made for the decisions of the
                batches it could show: the first, and the one before the
                resolver when no initializer creates its inputs.
        """
        self.workspace = LiveWorkspace()
        self.manifest = manifest
        self.review = review
        self.progress = progress
        if review is not None:
            hook_revisions = review.hook_revisions
        elif hook_revisions is None:
            hook_revisions = (
                resolve_hook_revisions() if manifest.tooling.wants_hooks else ()
            )
        self.hook_revisions = hook_revisions
        self.config = config
        self.docker = docker or manifest.tooling.wants_docker
        if self.docker:
            manifest.tooling.wants_docker = True
        self.journal = MutationJournal()
        self.fs = TransactionAwareFS(self.journal)
        self.process_runner = ProcessRunner()
        self.diagnostics: list[DiagnosticEvent] = list(manifest.diagnostics)
        self.proposals: list[MergeConflict] = []
        self.preserved: list[MergeConflict] = []
        self._owned_on_disk: frozenset[str] = frozenset()
        self.completed_tasks: list[SystemTask] = []
        self.interrupted_task: SystemTask | None = None
        from . import __version__

        self.candidate_state = SyncState(__version__, manifest.template_reference)
        self._state_bytes: bytes | None = None
        self._batch_applied = False
        self._resolution_dirty = False
        self._preserve_deleted_pyproject = False
        # Conflicts are settled in the reviews execution applies, never here.
        self.resolutions = NO_RESOLUTIONS
        self.reviewed_resolutions = resolutions
        self._used_resolutions: set[str] = set()

    def execute(
        self,
        *,
        policy: ExecutionPolicy = ExecutionPolicy.INITIALIZATION,
    ) -> None:
        """Applies captured decisions with initialization-specific materialization."""
        try:
            if self.manifest.one_shot:
                check_one_shot_workspace(Path.cwd())
            review = self.review
            if review is not None:
                policy = review.policy
            if policy is ExecutionPolicy.LIFECYCLE:
                prepared = review or prepare_review(
                    self.manifest,
                    self.config,
                    hook_revisions=self.hook_revisions,
                    policy=policy,
                )
                self._apply_review(prepared)
                self._resolve_review(prepared)
            else:
                if review is not None:
                    raise ConfigurationError(
                        "Initialization requires phased preparation.",
                        hint="Execute initialization without a lifecycle review.",
                    )
                with self.progress("Writing project files"):
                    early = self._prepare(PreparationPhase.BEFORE_INITIALIZERS)
                    self._apply_review(early)
                self._run_tasks(self.manifest.tasks.system_tasks)
                resolver = self._prepare(PreparationPhase.BEFORE_RESOLVER)
                if self._used_resolutions != set(self.reviewed_resolutions):
                    # A reviewed choice that names nothing left to decide was made
                    # for content that changed since.
                    raise StaleReviewError("change review choices")
                self._apply_review(resolver)
                self._resolve_review(resolver)
                artifacts = self._prepare(PreparationPhase.AFTER_RESOLVER)
                self._apply_review(artifacts)
                self._run_tasks(self.manifest.tasks.post_install_tasks)
                self._check_ide_extensions()
                if not self.manifest.one_shot:
                    recipe = self._prepare(PreparationPhase.RECIPE)
                    self._apply_review(recipe)
            if not self.manifest.one_shot:
                self._write_state()
            self.journal.commit()
        except BaseException as original_error:
            self.process_runner.terminate_active_process_tree()
            with shield_sigint():
                rollback_result = self.journal.rollback()
            if not rollback_result.succeeded:
                from .errors import RollbackFailedError

                raise RollbackFailedError(
                    rollback_result, original_error
                ) from original_error
            raise

    def _check_ide_extensions(self) -> None:
        """Verifies that the configured IDE has the recommended extensions installed.

        Fails silently if the IDE CLI is unavailable or execution fails. Appends a warning
        diagnostic only on a successful check that uncovers missing extensions.
        """
        check_ide_extensions(
            ide=self.manifest.recipe.ide if self.manifest.recipe else self.config.ide,
            ide_extensions=self.manifest.tooling.ide_extensions,
            on_diagnostic=lambda msg, sev: self.add_diagnostic(
                phase=DiagnosticPhase.IDE,
                message=msg,
                severity=sev,
            ),
            progress=self.progress,
        )

    def _run_tasks(self, tasks: list[SystemTask]) -> None:
        """Runs a sequence of system tasks (e.g., initialization or post-install commands)."""
        for task in tasks:
            if self._preserve_deleted_pyproject and task.command[:2] == ["uv", "init"]:
                self.add_diagnostic(
                    DiagnosticPhase.EXECUTOR,
                    "Skipping uv initialization; tracked pyproject.toml was deleted.",
                    Severity.SKIP,
                )
                continue
            for f in task.owned_files:
                self.journal.record_mutation(Path(f))
            for t in task.owned_trees:
                self.journal.record_tree_creation(Path(t))

            enforce_binary_safelist(task.command)

            # Prerequisite guards for post-install commands
            is_hook_install = (
                any(tool in task.command for tool in ("pre-commit", "prek"))
                and "install" in task.command
            )
            if is_hook_install and not (Path.cwd() / ".git").exists():
                self.add_diagnostic(
                    phase=DiagnosticPhase.PRE_COMMIT,
                    message="Skipping git hook installation; workspace is not a Git repository.",
                    severity=Severity.SKIP,
                )
                continue

            try:
                with self.progress(
                    task.description or f"Running {shlex.join(task.command)}"
                ):
                    self.process_runner.run(task.command, timeout=task.timeout)
                self.completed_tasks.append(task)
            except BaseException:
                self.interrupted_task = task
                raise

    def _validate_resolver_project(self) -> None:
        """Prevents uv from discovering an undeclared ancestor project."""
        if not Path("pyproject.toml").is_file():
            raise ConfigurationError(
                "No local resolver project exists.",
                hint="Declare a local pyproject.toml or uv init task before resolving dependencies.",
            )
        if not {"pyproject.toml", "uv.lock"}.issubset(
            self.manifest.dependencies.resolver_footprint.paths
        ):
            raise ConfigurationError(
                "Incomplete resolver footprint.",
                hint="Declare pyproject.toml and uv.lock before resolver execution.",
            )

    def _run_lock(self, footprint: ResolverFootprint) -> None:
        """Journals declared resolver files before a conditional lock-only action."""
        validate_resolver_workspace(self.journal.workspace_root)
        self._validate_resolver_project()
        for path in footprint.paths:
            enforce_path_jail(Path(path), Path.cwd())
            self.journal.record_mutation(Path(path))
        with self.progress("Refreshing uv.lock"):
            self.process_runner.run(["uv", "lock"], timeout=600)
        self._resolution_dirty = False

    def _write_state(self) -> None:
        """Writes candidate ownership last, before committing the journal."""
        content = serialize_state(self.candidate_state)
        if content.encode("utf-8") != self._state_bytes:
            try:
                self.fs.write_text(Path("protostar.lock"), content)
            except OSError as e:
                raise FileSystemError(
                    "write reconciliation state", "protostar.lock", e
                ) from e

    def _prepare(self, phase: PreparationPhase) -> PreparedReview:
        """Prepares the next initializer/resolver-dependent batch without mutation.

        The reviewed choices span the first two batches, so each batch takes
        the ones naming its own decisions, and the executor checks that every
        choice was used: one that settled nothing, including a choice its
        decision no longer offers, was made for content that changed since.
        """
        reviewed = phase in (
            PreparationPhase.BEFORE_INITIALIZERS,
            PreparationPhase.BEFORE_RESOLVER,
        )
        prepared = prepare_review(
            self.manifest,
            self.config,
            hook_revisions=self.hook_revisions,
            policy=ExecutionPolicy.INITIALIZATION,
            phase=phase,
            # Later batches continue the ownership earlier ones decided, which
            # can change without a write (an adopted file keeps its bytes).
            candidate_state=self.candidate_state if self._batch_applied else None,
            presence=self.journal,
            preserve_deleted_pyproject=self._preserve_deleted_pyproject,
            resolutions=self.reviewed_resolutions if reviewed else NO_RESOLUTIONS,
            partial_resolutions=reviewed,
        )
        if reviewed:
            self._used_resolutions.update(
                decision.id
                for decision in (*prepared.resolved, *prepared.proposals)
                if decision.resolution is not None
            )
        return prepared

    def _apply_review(self, review: PreparedReview) -> None:
        """Revalidates captured inputs before applying exact accepted bytes."""
        if manifest_digest(self.manifest) != review.manifest_digest:
            raise StaleReviewError("desired manifest")
        review.validate_inputs()
        self._batch_applied = True
        self.candidate_state = review.candidate_state
        self._state_bytes = review.state_before
        self._preserve_deleted_pyproject = review.preserve_deleted_pyproject
        self.diagnostics.extend(review.diagnostics)
        for path in review.directories:
            self.fs.ensure_directory(Path(path))
        for edit in review.edits:
            try:
                if edit.after is None:
                    self.fs.remove_file(Path(edit.path))
                else:
                    self.fs.write_bytes(Path(edit.path), edit.after)
            except OSError as error:
                raise FileSystemError(
                    "apply prepared edit", edit.path, error
                ) from error

    def _resolve_review(self, review: PreparedReview) -> None:
        """Executes only accepted resolver requests and records actual outputs."""
        action = review.resolver
        accepted = action.dependency_manifest()
        if any(packages for _, packages in action.requirements):
            validate_resolver_workspace(self.journal.workspace_root)
            self._validate_resolver_project()
            for path in action.footprint.paths:
                self.journal.record_mutation(Path(path))
            install_dependencies(accepted, self.process_runner, self.progress)
        elif action.lock_required:
            self._run_lock(action.footprint)
        self._materialize_dependencies(accepted, set(action.blocked))
