"""Shared ownership decisions over workspace reads and accepted byte sinks."""

import datetime
import hashlib
import logging
import stat
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from .appends import append_marker_blocks
from .config import UserConfig
from .dependencies import (
    normalized_requirement,
    requirement_entries,
    requirement_identity,
    retract_requirements,
    select_dependencies,
)
from .documents import (
    YAML_CONTRIBUTION_TARGETS,
    YAML_DOCUMENTS,
    YAML_GUARDS,
    github_workflows,
    pre_commit,
    pyproject,
    renovate,
    toml_spec,
    vscode,
    yaml_spec,
)
from .documents.locations import Resolution, resolve_location
from .errors import (
    ConfigurationError,
    FileSystemError,
    UnsupportedFilesystemNodeError,
)
from .intent import (
    AppendContribution,
    DependencyGroup,
    DependencyInclude,
    StructuredFormat,
    region_tag,
    validate_target,
)
from .interpolation import render_template
from .jsonc_ast import (
    JsoncReconciliation,
    decode_jsonc,
    decode_jsonc_baseline,
    dumps_jsonc,
    encode_jsonc_baseline,
    parse_jsonc,
    reconcile_jsonc,
)
from .manifest import (
    CollisionStrategy,
    DependencyManifest,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from .merge import (
    MISSING,
    NO_RESOLUTIONS,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
    Resolutions,
    Value,
    describe_location,
)
from .migrations import MigrationOutcome, MigrationStep, select_migrations
from .registry import ResolvedHookRevision
from .review_workspace import ByteSink, PresenceReader, ReviewWorkspace, WorkspaceReader
from .security import enforce_path_jail
from .sync_state import (
    DependencyState,
    FilePolicy,
    FileState,
    RegionState,
    SyncState,
    check_producer_version,
    check_template_identity,
    decode_toml_baseline,
    deserialize_state,
    encode_toml_baseline,
)
from .text_merge import reconcile_text
from .toml_ast import (
    TomlDocumentSpec,
    TomlReconciliation,
    aggregate_toml,
    aggregate_toml_document,
    reconcile_toml,
)
from .workflows import (
    DOCKERFILE,
    CIWorkflowSpec,
    DockerfileSpec,
    JustfileSpec,
    generate_ci_workflow,
    generate_dockerfile,
    generate_dockerignore,
    generate_gitignore,
    generate_justfile,
    generate_pre_commit_config,
    generate_release_workflow,
)
from .workspace import (
    resolve_package_name,
    resolve_project_name,
    resolve_python_version,
    validate_resolver_workspace,
)
from .yaml_ast import (
    NO_GUARD,
    YamlDocumentSpec,
    YamlGuardPolicy,
    YamlReconciliation,
    decode_yaml_baseline,
    encode_yaml_baseline,
    reconcile_yaml,
)

logger = logging.getLogger("protostar")

__all__ = ["Reconciliation"]


@dataclass(frozen=True)
class _Located:
    """The workspace file that holds one managed document in this run.

    Attributes:
        target: The document's canonical path, which keys its spec and guard.
        path: The file to reconcile, possibly an alias of ``target``.
        record: The ownership record the baseline comes from, which may name the
            path a renamed document was followed from.
    """

    target: str
    path: Path
    record: FileState | None


class Reconciliation:
    """Shared semantic decisions over a workspace reader and a byte sink.

    Preparation supplies an in-memory sink; execution alone supplies the
    transaction-aware filesystem. No method here invokes a process or registry.
    """

    def __init__(
        self,
        manifest: EnvironmentManifest,
        config: UserConfig,
        workspace: WorkspaceReader,
        fs: ByteSink,
        journal: PresenceReader,
        hook_revisions: tuple[ResolvedHookRevision, ...] = (),
        resolutions: Resolutions = NO_RESOLUTIONS,
    ) -> None:
        """Binds workspace inputs, an accepted-byte sink, and frozen hook pins."""
        self.resolutions = resolutions
        self.manifest = manifest
        self.config = config
        self.workspace = workspace
        self.fs = fs
        self.journal = journal
        self.hook_revisions = hook_revisions
        self.docker = manifest.tooling.wants_docker
        self.diagnostics: list[DiagnosticEvent] = []
        self.proposals: list[MergeConflict] = []
        self.preserved: list[MergeConflict] = []
        self._owned_on_disk: frozenset[str] = frozenset()
        self._committed: SyncState | None = None
        self.migration_steps: list[MigrationStep] = []
        from . import __version__

        self.candidate_state = SyncState(__version__, manifest.template_reference)
        self._state_bytes: bytes | None = None
        self._resolution_dirty = False
        self._preserve_deleted_pyproject = False

    def add_diagnostic(
        self,
        phase: DiagnosticPhase | str,
        message: str,
        severity: Severity = Severity.INFO,
        detail: str | None = None,
    ) -> None:
        """Queues a diagnostic event for the post-execution summary panel."""
        self.diagnostics.append(
            DiagnosticEvent(
                phase=phase, message=message, severity=severity, detail=detail
            )
        )

    @property
    def interpolation_context(self) -> dict[str, str]:
        """Dynamically generates the context for template interpolation."""
        if self.manifest.recipe:
            return self.manifest.recipe.rendering_context()
        return {
            "PROJECT_NAME": resolve_project_name(self.manifest.metadata),
            "PACKAGE_NAME": resolve_package_name(self.manifest.metadata),
            "PYTHON_VERSION": resolve_python_version(self.manifest.metadata)
            or self.config.python_version
            or "3.13",
            "CURRENT_YEAR": str(datetime.date.today().year),
            "AUTHOR_NAME": self.manifest.metadata.get("author_name") or "your-name",
        }

    def _validate_targets(self) -> None:
        """Validates the syntax of existing target files before disk I/O begins.

        Uses the C-optimized tomllib to quickly evaluate target workspace files,
        ensuring that subsequent tomlkit operations will not fail mid-execution
        and leave the environment fragmented.

        Raises:
            ConfigurationError: If an existing target TOML file contains syntax errors.
        """
        for path in (
            self.manifest.filesystem.file_injections.keys()
            | self.manifest.filesystem.structured.keys()
            | self.manifest.filesystem.regions.keys()
            | self.manifest.filesystem.directories
        ):
            validate_target(render_template(path, self.interpolation_context))
            self._validate_node(
                Path(render_template(path, self.interpolation_context)),
                directory=path in self.manifest.filesystem.directories,
            )
        for path in self.manifest.filesystem.file_injections:
            if Path(render_template(path, self.interpolation_context)) == Path(
                pyproject.TARGET
            ):
                raise ConfigurationError(
                    "Free-form pyproject.toml replacement is unsupported.",
                    hint="Declare structured contributions; tool.protostar is reserved.",
                )
        for filepath, content in self.manifest.filesystem.file_injections.items():
            if Path(render_template(filepath, self.interpolation_context)) == (
                Path(renovate.TARGET)
            ):
                decode_jsonc(render_template(content, self.interpolation_context))
                existing = self._existing(renovate.TARGET)
                if existing is not None:
                    try:
                        decode_jsonc(
                            self.workspace.read_bytes(existing).decode("utf-8")
                        )
                    except (OSError, UnicodeError) as error:
                        raise FileSystemError(
                            "read JSONC configuration", str(existing), error
                        ) from error
        for filepath, contributions in self.manifest.filesystem.structured.items():
            if any(c.format is StructuredFormat.YAML for c in contributions):
                if len(contributions) != 1 or filepath not in YAML_CONTRIBUTION_TARGETS:
                    raise ConfigurationError(
                        "Unsupported YAML contributions.",
                        hint="Declare exactly one producer for a supported YAML target.",
                    )
                decode_yaml_baseline(contributions[0].content)
                if (target := self._existing(filepath)) is not None:
                    try:
                        decode_yaml_baseline(
                            self.workspace.read_bytes(target).decode("utf-8")
                        )
                    except (OSError, UnicodeError) as error:
                        raise FileSystemError(
                            "read YAML configuration", str(target), error
                        ) from error
                continue
            aggregate_toml(
                [
                    replace(
                        c,
                        content=render_template(c.content, self.interpolation_context),
                    )
                    for c in contributions
                ]
            )
        deps = self.manifest.dependencies
        if (
            deps.dependencies
            or deps.dev_dependencies
            or deps.docs_dependencies
            or deps.includes
            or any(
                c.resolver_footprint
                for cs in self.manifest.filesystem.structured.values()
                for c in cs
            )
        ):
            validate_resolver_workspace(self.journal.workspace_root)
        toml_targets = {
            *self.manifest.filesystem.structured.keys(),
        }
        if (
            deps.includes
            or deps.dependencies
            or deps.dev_dependencies
            or deps.docs_dependencies
        ):
            toml_targets.add(pyproject.TARGET)
        for _group, packages in (
            (DependencyGroup.MAIN, deps.dependencies),
            (DependencyGroup.DEV, deps.dev_dependencies),
            (DependencyGroup.DOCS, deps.docs_dependencies),
        ):
            for package in packages:
                requirement_identity(package)
        for filepath in sorted(toml_targets):
            rendered = render_template(filepath, self.interpolation_context)
            resolved = self._resolve(rendered).path
            if resolved is None:
                continue
            target = Path(resolved)
            self._validate_node(target)
            if target.suffix == ".toml" and self.workspace.exists(target):
                try:
                    tomllib.loads(self.workspace.read_text(target))
                except tomllib.TOMLDecodeError as e:
                    raise ConfigurationError(
                        f"Syntax error in existing workspace file: {filepath}\n"
                        f"Details: {e}\n"
                        "Protostar cannot safely merge configurations into a malformed file. "
                        "Please fix the syntax error and re-run the command."
                    ) from e

    def _write_pre_commit_config(self) -> None:
        """Assembles and writes the pre-commit configuration."""
        if not self.manifest.tooling.wants_hooks:
            return

        full_yaml = generate_pre_commit_config(
            local_hooks=self.manifest.tooling.pre_commit_local_hooks,
            remote_hooks=self.manifest.tooling.pre_commit_hooks,
            dependencies=self.manifest.dependencies.dependencies,
            hook_runner=self.manifest.tooling.hook_runner,
            install_hook_types=self.manifest.tooling.pre_commit_install_hook_types,
        )
        # Hooks that validate a managed document name the file this run edits.
        full_yaml = pre_commit.resolve_document_files(
            full_yaml,
            lambda target: self._resolve(target).path,
            self.manifest.document_locations,
        )

        located = self._locate(pre_commit.TARGET, FilePolicy.YAML)
        if located is None:
            return
        plan = pre_commit.plan_hook_pins(
            full_yaml,
            self.hook_revisions,
            self.candidate_state.hook_pins,
            located.path.as_posix(),
            located.record.path if located.record else None,
        )
        result = self._reconcile_document(
            located, plan.desired, FilePolicy.YAML, guard=lambda *_: plan.guard
        )
        self.candidate_state = replace(
            self.candidate_state,
            hook_pins=plan.advance(result.content, result.baseline),
        )

    def _write_injected_files(self) -> None:
        """Writes all queued boilerplate files to the local workspace."""
        if not self.manifest.filesystem.file_injections:
            return

        for filepath, content in self.manifest.filesystem.file_injections.items():
            interpolated_filepath = render_template(
                filepath, self.interpolation_context
            )
            content = render_template(content, self.interpolation_context)
            target = Path(interpolated_filepath)
            enforce_path_jail(target, Path.cwd())
            if target == Path(renovate.TARGET):
                if located := self._locate(renovate.TARGET, FilePolicy.JSONC):
                    self._reconcile_document(located, content, FilePolicy.JSONC)
                continue
            # A seed an alias already holds is that file, never a second one.
            resolved = self._follow(target.as_posix(), set())
            if resolved is None:
                continue
            target = Path(resolved)
            enforce_path_jail(target, Path.cwd())
            record = self._file_record(target, FilePolicy.SEED)
            overwrite = self.manifest.collision_strategy is CollisionStrategy.OVERWRITE
            if (
                not overwrite
                and record is not None
                and not self.workspace.exists(target)
            ):
                # A deleted seed stays deleted unless its restoration is chosen.
                deleted = MergeConflict(
                    MergeLocation(target.as_posix()),
                    ConflictReason.PRESERVED,
                    ConflictSides(MISSING, MISSING, content, line=0),
                )
                settled = deleted.settle(self.resolutions)
                if settled is None:
                    self._report((), (), preserved=(deleted,))
                    continue
                self._report((), (settled,))
                if settled.resolution is ResolutionChoice.LOCAL:
                    continue
            elif not overwrite and (
                self.workspace.exists(target) or record is not None
            ):
                self.add_diagnostic(
                    DiagnosticPhase.EXECUTOR,
                    f"Skipping {target.name} generation; existing or deleted seed.",
                    Severity.SKIP,
                )
                continue
            try:
                self.fs.write_text(target, content)
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        FilePolicy.SEED,
                        digest=hashlib.sha256(content.encode()).hexdigest(),
                    )
                )
            except OSError as e:
                raise FileSystemError("inject boilerplate file", str(target), e) from e
            logger.debug(f"Injected configuration file: {interpolated_filepath}")

    def _migrate(self) -> None:
        """Applies the template's migrations between the applied and new version.

        Only a project with committed state has an applied version to migrate
        from. Every step is guarded by ownership, so repeating one is a no-op.

        Raises:
            ConfigurationError: If the template moves back across a migration.
        """
        committed = self._committed.template if self._committed else None
        reference = self.candidate_state.template
        if committed is None or reference is None:
            return
        selected = select_migrations(
            self.manifest.migrations,
            committed.version,
            reference.version,
            committed.migrated,
        )
        if selected:
            self.candidate_state = replace(
                self.candidate_state,
                template=replace(reference, migrated=selected[-1].version),
            )
        for migration in selected:
            for rename in migration.rename:
                self._rename_seed(
                    migration.version,
                    render_template(rename.source, self.interpolation_context),
                    render_template(rename.target, self.interpolation_context),
                )
            for path in migration.remove:
                self._remove_seed(
                    migration.version,
                    render_template(path, self.interpolation_context),
                )

    def _seed(self, path: str) -> FileState | None:
        """Returns the live ownership of a seed, or None for anything else."""
        record = next((r for r in self.candidate_state.files if r.path == path), None)
        if record is None or record.policy is not FilePolicy.SEED or record.retired:
            return None
        return record

    def _migrated(
        self, version: str, path: str, target: str | None, outcome: MigrationOutcome
    ) -> None:
        self.migration_steps.append(MigrationStep(version, path, target, outcome))

    def _rename_seed(self, version: str, source: str, target: str) -> None:
        """Moves an owned seed, local edits included, and its ownership."""
        for path in (source, target):
            validate_target(path)
            enforce_path_jail(Path(path), Path.cwd())
            self._validate_node(Path(path))
        record = self._seed(source)
        if record is None:
            self._migrated(version, source, target, MigrationOutcome.NOT_OWNED)
            return
        if self.workspace.exists(Path(target)) or any(
            r.path == target for r in self.candidate_state.files
        ):
            # The file stays where it is as the user's own, since nothing
            # declares it there any more.
            self.candidate_state = self.candidate_state.without_file(source)
            self._migrated(version, source, target, MigrationOutcome.TARGET_EXISTS)
            return
        if self.workspace.exists(Path(source)):
            self.fs.write_bytes(Path(target), self.workspace.read_bytes(Path(source)))
            self.fs.remove_file(Path(source))
        # A seed deleted before the move stays deleted at its new path.
        self.candidate_state = self.candidate_state.without_file(source).with_file(
            replace(record, path=target)
        )
        self._migrated(version, source, target, MigrationOutcome.MOVED)

    def _remove_seed(self, version: str, path: str) -> None:
        """Removes an owned seed the template no longer ships.

        An unedited seed is deleted. One with local edits, or one written
        before seeds recorded their digest, is retired: it stays, and a
        ``retracted`` conflict asks whether to keep or delete it.
        """
        validate_target(path)
        enforce_path_jail(Path(path), Path.cwd())
        self._validate_node(Path(path))
        record = self._seed(path)
        outcome = (
            MigrationOutcome.NOT_OWNED if record is None else self._release_seed(record)
        )
        self._migrated(version, path, None, outcome)

    def _release_seed(self, record: FileState) -> MigrationOutcome:
        """Lets go of an owned seed: deleted when unedited, retired when edited."""
        target = Path(record.path)
        if not self.workspace.exists(target):
            self.candidate_state = self.candidate_state.without_file(record.path)
            return MigrationOutcome.FORGOTTEN
        local = self.workspace.read_bytes(target)
        if record.digest == hashlib.sha256(local).hexdigest():
            self.fs.remove_file(target)
            self.candidate_state = self.candidate_state.without_file(record.path)
            return MigrationOutcome.REMOVED
        self.candidate_state = self.candidate_state.with_file(
            replace(record, retired=True)
        )
        return MigrationOutcome.RETIRED

    def _release_undeclared_seeds(self) -> None:
        """Lets go of each owned seed that no producer declares any more.

        A tool or template option that is switched off stops declaring its
        files, and a template can stop shipping one. Each goes the way a
        migration's removal does: deleted when unedited, and otherwise kept as
        a ``retracted`` conflict until settled. A seed a migration already
        decided on this run keeps that outcome.
        """
        declared = {
            Path(render_template(path, self.interpolation_context)).as_posix()
            for path in self.manifest.filesystem.file_injections
        } | {step.path for step in self.migration_steps}
        for record in self.candidate_state.files:
            if (
                record.policy is FilePolicy.SEED
                and not record.retired
                and record.path not in declared
            ):
                enforce_path_jail(Path(record.path), Path.cwd())
                self._validate_node(Path(record.path))
                self._release_seed(record)

    def _settle_retired(self) -> None:
        """Reports each retired seed as a ``retracted`` conflict until settled.

        Keeping the local file lets go of it, so it becomes the user's own;
        taking the update deletes it. Either way Protostar stops owning it.
        """
        for record in [r for r in self.candidate_state.files if r.retired]:
            target = Path(record.path)
            if not self.workspace.exists(target):
                self.candidate_state = self.candidate_state.without_file(record.path)
                continue
            local = self.workspace.read_bytes(target).decode("utf-8", "replace")
            conflict = MergeConflict(
                MergeLocation(record.path),
                ConflictReason.RETRACTED,
                ConflictSides(MISSING, local, MISSING),
            )
            settled = conflict.settle(self.resolutions)
            if settled is None:
                self._report((conflict,), ())
                continue
            self._report((), (settled,))
            if settled.resolution is ResolutionChoice.DESIRED:
                self.fs.remove_file(target)
            self.candidate_state = self.candidate_state.without_file(record.path)

    def _release_undeclared_documents(self) -> None:
        """Retracts each owned structured document that nothing declares any more.

        A tool or template option that is switched off stops declaring its
        documents, and a template can stop contributing to one. Each is
        reconciled against an empty complete declaration under its own spec:
        an unedited owned unit is removed, an edited one is kept with a
        ``retracted`` conflict, and foreign content stays. Seeds and retained
        paths are retracted too, and guards are off, because nothing is wanted.
        A file left with nothing once its owned content is removed is deleted;
        one the user already deleted is forgotten. Explicit overwrite covers
        declared targets only, so it removes no edited content here.
        """
        declared = self.manifest.declared_documents()
        for record in [
            r
            for r in self.candidate_state.files
            if r.policy in (FilePolicy.TOML, FilePolicy.YAML, FilePolicy.JSONC)
            and r.path not in declared
        ]:
            target = Path(record.path)
            enforce_path_jail(target, Path.cwd())
            self._validate_node(target)
            if not self.workspace.exists(target):
                self._release_document(record.path)
                continue
            try:
                original = self.workspace.read_bytes(target).decode("utf-8")
            except (OSError, UnicodeError) as error:
                raise FileSystemError(
                    "read retracted configuration", record.path, error
                ) from error
            location = MergeLocation(record.path)
            baseline = record.baseline or ""
            decode: Callable[[str], dict[str, Value]]
            encode: Callable[[dict[str, Value]], str]
            result: TomlReconciliation | YamlReconciliation | JsoncReconciliation
            if record.policy is FilePolicy.TOML:
                spec = toml_spec(record.path)
                decode, encode = tomllib.loads, encode_toml_baseline
                result = reconcile_toml(
                    replace(
                        spec,
                        seed_paths=frozenset(),
                        policy=replace(
                            spec.policy, complete=True, retained_paths=frozenset()
                        ),
                    ),
                    original,
                    {},
                    decode_toml_baseline(baseline),
                    location,
                    resolutions=self.resolutions,
                )
            elif record.policy is FilePolicy.YAML:
                yaml = yaml_spec(record.path) or YamlDocumentSpec(record.path)
                decode, encode = decode_yaml_baseline, encode_yaml_baseline
                result = reconcile_yaml(
                    replace(
                        yaml,
                        policy=replace(
                            yaml.policy, complete=True, retained_paths=frozenset()
                        ),
                    ),
                    original,
                    "{}\n",
                    decode_yaml_baseline(baseline),
                    location,
                    resolutions=self.resolutions,
                )
            else:
                decode, encode = decode_jsonc, encode_jsonc_baseline
                result = reconcile_jsonc(
                    original,
                    "{}",
                    decode_jsonc_baseline(baseline),
                    location,
                    resolutions=self.resolutions,
                    complete=True,
                )
            self._report(
                result.conflicts, result.resolved, result.proposals, result.preserved
            )
            owned = result.baseline if isinstance(result.baseline, dict) else {}
            if result.conflicts or owned:
                self.candidate_state = self.candidate_state.with_file(
                    FileState(record.path, record.policy, encode(owned))
                )
            else:
                self._release_document(record.path)
            if result.content == original:
                continue
            try:
                if not result.conflicts and not decode(result.content):
                    self.fs.remove_file(target)
                else:
                    self.fs.write_text(target, result.content)
            except OSError as error:
                raise FileSystemError(
                    "retract configuration", record.path, error
                ) from error

    def _release_document(self, path: str) -> None:
        """Forgets a structured document's ownership and the hook pins it held."""
        self.candidate_state = replace(
            self.candidate_state.without_file(path),
            hook_pins=tuple(
                pin for pin in self.candidate_state.hook_pins if pin.path != path
            ),
        )

    def _create_directories(self) -> None:
        """Scaffolds all queued directories in the local workspace."""
        if not self.manifest.filesystem.directories:
            return

        for dir_path in self.manifest.filesystem.directories:
            interpolated_path = render_template(dir_path, self.interpolation_context)
            path = Path(interpolated_path)
            enforce_path_jail(path, Path.cwd())
            try:
                self.fs.ensure_directory(path)
            except OSError as e:
                raise FileSystemError(
                    "create scaffolding directory", str(path), e
                ) from e
            logger.debug(f"Scaffolded directory: {path}")

    def _write_ci_workflow(self) -> None:
        """Assembles and reconciles the .github/workflows/ci.yml file if requested."""
        if not self.manifest.tooling.wants_ci:
            return
        workflow = generate_ci_workflow(
            CIWorkflowSpec(
                supported_os=self.manifest.metadata.get("supported_os", ["Linux"]),
                min_python=self.manifest.metadata.get("minimum_python", "3.13"),
                ci_flags=self.manifest.tooling.ci_flags,
                ci_steps=self.manifest.tooling.ci_steps,
            )
        )
        self._write_workflow(github_workflows.CI_TARGET, workflow)

    def _write_release_workflow(self) -> None:
        """Assembles and reconciles the .github/workflows/release.yml file if requested."""
        if not self.manifest.tooling.wants_release:
            return
        self._write_workflow(
            github_workflows.RELEASE_TARGET, generate_release_workflow()
        )

    def _write_workflow(self, target: str, workflow: str) -> None:
        """Merges a generated workflow into the workspace by job and step."""
        if located := self._locate(target, FilePolicy.YAML):
            self._reconcile_document(
                located, workflow, FilePolicy.YAML, guard=YAML_GUARDS[target]
            )

    def _write_justfile(self) -> None:
        """Assembles and writes the justfile if requested."""
        if not self.manifest.tooling.wants_just:
            return

        target = Path("justfile")
        enforce_path_jail(target, Path.cwd())
        full_content = generate_justfile(
            JustfileSpec(
                format_commands=self.manifest.tooling.just_format_commands,
                lint_commands=self.manifest.tooling.just_lint_commands,
                typecheck_commands=self.manifest.tooling.just_typecheck_commands,
                ci_flags=self.manifest.tooling.ci_flags,
                clean_paths=self.manifest.tooling.just_clean_paths,
            )
        )
        self._write_generated(target, full_content)

    def _reconcile_document(
        self,
        located: _Located,
        desired: str,
        policy: FilePolicy,
        *,
        indent: str = "  ",
        guard: YamlGuardPolicy | None = None,
    ) -> YamlReconciliation | JsoncReconciliation:
        """Applies a YAML or JSONC document through the transaction and candidate state.

        Args:
            located: The file that holds the document and the ownership it continues.
            desired: Desired contribution text.
            policy: ``FilePolicy.YAML`` or ``FilePolicy.JSONC``.
            indent: Indentation unit for JSONC edits when none can be inferred.
            guard: The YAML document's policy for holding user-owned content.

        Returns:
            The applied reconciliation.
        """
        decode_baseline: Callable[[str], dict[str, Value]]
        encode_baseline: Callable[[dict[str, Value]], str]
        if policy is FilePolicy.YAML:
            decode_baseline = decode_yaml_baseline
            encode_baseline = encode_yaml_baseline
        else:
            decode_baseline = decode_jsonc_baseline
            encode_baseline = encode_jsonc_baseline
        target = located.path
        record = located.record
        try:
            exists = self.workspace.exists(target)
            original = (
                self.workspace.read_bytes(target).decode("utf-8") if exists else ""
            )
            base = (
                decode_baseline(record.baseline)
                if record and record.baseline is not None
                else MISSING
            )
            location = MergeLocation(target.as_posix())
            overwrite = self.manifest.collision_strategy is CollisionStrategy.OVERWRITE
            proposing = not overwrite and self._proposing(target, record)
            if policy is FilePolicy.YAML:
                result: YamlReconciliation | JsoncReconciliation = reconcile_yaml(
                    YAML_DOCUMENTS[located.target],
                    original,
                    desired,
                    base,
                    location,
                    guard=guard(
                        target.as_posix(),
                        decode_yaml_baseline(desired),
                        decode_yaml_baseline(original) if exists else {},
                        base,
                    )
                    if guard is not None
                    else NO_GUARD,
                    missing_file=not exists,
                    overwrite=overwrite,
                    resolutions=self.resolutions,
                    proposing=proposing,
                )
            else:
                result = reconcile_jsonc(
                    original,
                    desired,
                    base,
                    location,
                    missing_file=not exists,
                    overwrite=overwrite,
                    default_indent=indent,
                    resolutions=self.resolutions,
                    proposing=proposing,
                )
            self._report(
                result.conflicts, result.resolved, result.proposals, result.preserved
            )
            if result.baseline is not MISSING:
                self._own(
                    located,
                    FileState(
                        target.as_posix(),
                        policy,
                        encode_baseline(cast(dict[str, Value], result.baseline)),
                    ),
                )
            if result.content != original:
                self.fs.write_text(target, result.content)
            return result
        except (OSError, UnicodeError) as error:
            raise FileSystemError(
                f"reconcile {target.name} configuration", str(target), error
            ) from error

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        is_overwrite = self.manifest.collision_strategy == CollisionStrategy.OVERWRITE
        for filepath, contributions in self.manifest.filesystem.structured.items():
            if contributions[0].format is StructuredFormat.YAML:
                if located := self._locate(filepath, FilePolicy.YAML):
                    self._reconcile_document(
                        located,
                        contributions[0].content,
                        FilePolicy.YAML,
                        guard=YAML_GUARDS.get(filepath),
                    )
                continue
            rendered = render_template(filepath, self.interpolation_context)
            validate_target(rendered)
            toml_located = self._locate(rendered, FilePolicy.TOML)
            if toml_located is None:
                continue
            target = toml_located.path
            record = toml_located.record
            try:
                original = (
                    self.workspace.read_bytes(target).decode("utf-8")
                    if self.workspace.exists(target)
                    else ""
                )
            except (OSError, UnicodeError) as e:
                raise FileSystemError(
                    "read structured configuration", str(target), e
                ) from e
            deleted_project = (
                target == Path(pyproject.TARGET) and self._preserve_deleted_pyproject
            )
            initializing = (
                not self.journal.was_present(target)
                and record is None
                and not deleted_project
            )
            spec = toml_spec(rendered)
            if self._outside_root_table(spec, original):
                self._merge_warning(
                    MergeConflict(
                        MergeLocation(target.as_posix()), ConflictReason.UNOWNED
                    )
                )
                continue
            aggregated = aggregate_toml_document(
                [
                    replace(
                        c,
                        content=render_template(c.content, self.interpolation_context),
                    )
                    for c in contributions
                ]
            )
            if deleted_project and record is None:
                self._merge_warning(
                    MergeConflict(
                        MergeLocation(target.as_posix()),
                        ConflictReason.DELETED_ANCESTOR,
                    )
                )
                continue
            result = reconcile_toml(
                spec,
                original,
                aggregated.value,
                decode_toml_baseline(record.baseline)
                if record and record.baseline is not None
                else MISSING,
                MergeLocation(target.as_posix()),
                overwrite=is_overwrite,
                initializing=initializing,
                missing_file=not self.workspace.exists(target),
                desired_ast=aggregated.document,
                resolutions=self.resolutions,
                proposing=not is_overwrite and self._proposing(target, record),
            )
            self._report(
                result.conflicts, result.resolved, result.proposals, result.preserved
            )
            for note in result.layout_notes:
                self._layout_warning(target, note)
            if result.baseline is not MISSING:
                self._own(
                    toml_located,
                    FileState(
                        target.as_posix(),
                        FilePolicy.TOML,
                        encode_toml_baseline(cast(dict[str, Value], result.baseline)),
                    ),
                )
            new_content = result.content
            if new_content != original:
                try:
                    self.fs.write_text(target, new_content)
                except OSError as e:
                    raise FileSystemError(
                        "mutate configuration AST", str(target), e
                    ) from e
                original_project = tomllib.loads(original).get("project", {})
                updated_project = tomllib.loads(new_content).get("project", {})
                original_python = (
                    original_project.get("requires-python")
                    if isinstance(original_project, dict)
                    else None
                )
                updated_python = (
                    updated_project.get("requires-python")
                    if isinstance(updated_project, dict)
                    else None
                )
                if (
                    target == Path(pyproject.TARGET)
                    and any(c.resolver_footprint for c in contributions)
                    and original_python != updated_python
                ):
                    self._resolution_dirty = True
        declared: dict[str, list[AppendContribution]] = {}
        held: set[str] = set()
        for filepath, regions in self.manifest.filesystem.regions.items():
            # Regions go where the document's tool reads it, so an existing
            # alias is extended instead of a second file created.
            path = self._follow(
                render_template(filepath, self.interpolation_context), held
            )
            if path is not None:
                declared[path] = regions
        # A file whose owned regions nothing declares any more is visited too,
        # so they are retracted.
        for record in self.candidate_state.files:
            if record.regions and record.path not in declared.keys() | held:
                declared[record.path] = []
        for filepath, regions in declared.items():
            target = Path(filepath)
            validate_target(target.as_posix())
            enforce_path_jail(target, Path.cwd())
            try:
                original = (
                    self.workspace.read_bytes(target).decode("utf-8")
                    if self.workspace.exists(target)
                    else ""
                )
            except (OSError, UnicodeError) as e:
                raise FileSystemError(
                    "read target append context", str(target), e
                ) from e
            region_payloads = [
                AppendContribution(
                    c.id, render_template(c.content, self.interpolation_context)
                )
                for c in regions
            ]
            record = next(
                (r for r in self.candidate_state.files if r.path == target.as_posix()),
                None,
            )
            if record is not None and record.policy not in (
                FilePolicy.REGIONS,
                FilePolicy.TEXT,
            ):
                raise ConfigurationError(
                    "Conflicting region ownership policy.",
                    hint="Keep the tracked file policy unchanged.",
                )
            region_result = append_marker_blocks(
                original,
                region_payloads,
                target,
                overwrite=is_overwrite,
                baselines={r.id: r.baseline for r in record.regions} if record else {},
                missing_owned_file=record is not None
                and not self.workspace.exists(target),
                resolutions=self.resolutions,
            )
            self._report(
                region_result.conflicts,
                region_result.resolved,
                preserved=region_result.preserved,
            )
            text_baseline = record.baseline if record else None
            if record is not None and text_baseline is not None:
                # A generated file's text holds its regions; one that was cut
                # leaves that text too.
                cut = {
                    r.id: r.baseline
                    for r in record.regions
                    if r.id not in region_result.baselines
                    and r.baseline not in region_result.content
                }
                if cut:
                    text_baseline = append_marker_blocks(
                        text_baseline, [], target, baselines=cut
                    ).content
            if region_result.baselines or (
                record is not None and record.policy is FilePolicy.TEXT
            ):
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        record.policy if record else FilePolicy.REGIONS,
                        text_baseline,
                        regions=tuple(
                            RegionState(region_tag(identity), identity, baseline)
                            for identity, baseline in region_result.baselines.items()
                        ),
                    )
                )
            elif record is not None:
                self.candidate_state = self.candidate_state.without_file(record.path)
            if region_result.content != original:
                try:
                    self.fs.write_text(target, region_result.content)
                except OSError as e:
                    raise FileSystemError(
                        "append configurations block", str(target), e
                    ) from e

    def _outside_root_table(self, spec: TomlDocumentSpec, original: str) -> bool:
        """Returns whether a TOML document keeps its settings outside its root table.

        Such a document is left alone under every strategy, because adding the
        root table would hide the existing settings from the tool.

        Args:
            spec: The document's merge spec.
            original: Current document text, empty when the file is absent.

        Returns:
            True when the document has settings but not the spec's root table.
        """
        if spec.root_table is None:
            return False
        local = tomllib.loads(original)
        return bool(local) and spec.root_table not in local

    def _resolve(self, target: str) -> Resolution:
        """Resolves which workspace file holds a document, without reporting.

        Args:
            target: The document's canonical workspace path.

        Returns:
            The resolution under the current candidate ownership.
        """
        return resolve_location(
            self.manifest.document_locations(target),
            {record.path for record in self.candidate_state.files},
            lambda path: self.workspace.exists(Path(path)),
        )

    def _follow(self, target: str, held: set[str]) -> str | None:
        """Resolves a free-form document's file and follows a rename's ownership.

        Args:
            target: The document's canonical workspace path.
            held: Collects the ownership record of a document that is held, so
                its content is kept rather than retracted.

        Returns:
            The file that holds the document in this run, or ``None`` when
            competing files leave it held.
        """
        resolution = self._resolve(target)
        for conflict in resolution.conflicts:
            self._merge_warning(conflict)
        if resolution.path is None:
            if resolution.owner is not None:
                held.add(resolution.owner)
            return None
        if resolution.owner is not None and resolution.owner != resolution.path:
            record = next(
                r for r in self.candidate_state.files if r.path == resolution.owner
            )
            self.candidate_state = self.candidate_state.with_file(
                replace(record, path=resolution.path)
            ).without_file(resolution.owner)
        return resolution.path

    def _existing(self, target: str) -> Path | None:
        """Returns the existing file a document would be reconciled in, if any."""
        resolved = self._resolve(target).path
        if resolved is None or not self.workspace.exists(Path(resolved)):
            return None
        return Path(resolved)

    def _locate(self, target: str, policy: FilePolicy) -> _Located | None:
        """Finds the file that holds a document and reports competing configurations.

        Args:
            target: The document's canonical workspace path.
            policy: The document's ownership policy.

        Returns:
            The file to reconcile and the ownership it continues, or ``None`` when
            the document is held.
        """
        resolution = self._resolve(target)
        for conflict in resolution.conflicts:
            self._merge_warning(conflict)
        if resolution.path is None:
            return None
        path = Path(resolution.path)
        enforce_path_jail(path, Path.cwd())
        self._validate_node(path)
        record = (
            self._file_record(Path(resolution.owner), policy)
            if resolution.owner is not None
            else None
        )
        return _Located(target, path, record)

    def _own(self, located: _Located, record: FileState) -> None:
        """Records ownership of the reconciled file, moving it from a followed path.

        Args:
            located: The file the reconciliation edited.
            record: The ownership accepted for that file.
        """
        self.candidate_state = self.candidate_state.with_file(record)
        if located.record is not None and located.record.path != record.path:
            self.candidate_state = self.candidate_state.without_file(
                located.record.path
            )

    def _file_record(self, target: Path, policy: FilePolicy) -> FileState | None:
        """Returns ownership after checking that the policy has not changed."""
        record = next(
            (r for r in self.candidate_state.files if r.path == target.as_posix()), None
        )
        if record is not None and record.policy is not policy:
            raise ConfigurationError(
                "Conflicting file ownership policy.",
                hint="Keep the tracked file policy unchanged.",
            )
        return record

    def _write_generated(self, target: Path, content: str) -> None:
        """Merges a generated file's update into the workspace three ways."""
        enforce_path_jail(target, Path.cwd())
        self._validate_node(target)
        record = next(
            (r for r in self.candidate_state.files if r.path == target.as_posix()), None
        )
        if record is not None and record.policy not in (
            FilePolicy.TEXT,
            FilePolicy.REGIONS,
        ):
            raise ConfigurationError(
                "Conflicting generated ownership policy.",
                hint="Keep the tracked file policy unchanged.",
            )
        contributions = self.manifest.filesystem.regions.get(target.as_posix(), [])
        if record is not None and any(
            r.id not in {c.id for c in contributions} for r in record.regions
        ):
            # Regenerating without an omitted region would drop it unasked. The
            # region step retracts it first, so the next run regenerates.
            return
        framed = append_marker_blocks(
            content,
            [
                AppendContribution(
                    c.id, render_template(c.content, self.interpolation_context)
                )
                for c in contributions
            ],
            target,
            overwrite=True,
        )
        content = framed.content
        try:
            local = (
                self.workspace.read_bytes(target)
                if self.workspace.exists(target)
                else None
            )
            if (
                local is None
                and record is not None
                and record.policy is FilePolicy.REGIONS
                and self.manifest.collision_strategy is not CollisionStrategy.OVERWRITE
            ):
                self._merge_warning(
                    MergeConflict(
                        MergeLocation(target.as_posix()),
                        ConflictReason.DELETED_ANCESTOR,
                    )
                )
                return
            result = reconcile_text(
                local,
                content,
                record.baseline if record else None,
                MergeLocation(target.as_posix()),
                overwrite=self.manifest.collision_strategy
                is CollisionStrategy.OVERWRITE,
                resolutions=self.resolutions,
            )
            self._report(result.conflicts, result.resolved, preserved=result.preserved)
            if result.content is not None:
                self.fs.write_text(target, result.content)
            if result.baseline is not None:
                regions = {r.id: r.baseline for r in record.regions} if record else {}
                if result.baseline == content:
                    regions.update(framed.baselines)
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        FilePolicy.TEXT,
                        result.baseline,
                        regions=tuple(
                            RegionState(region_tag(identity), identity, baseline)
                            for identity, baseline in regions.items()
                        ),
                    )
                )
        except OSError as error:
            raise FileSystemError("write generated file", str(target), error) from error

    def _apply_dependency_includes(self) -> None:
        """Applies typed include edges before uv add observes dependency metadata."""
        if not self.manifest.dependencies.includes:
            return
        target = Path(pyproject.TARGET)
        if (
            not self.workspace.exists(target)
            and self.manifest.collision_strategy is not CollisionStrategy.OVERWRITE
            and (
                any(r.path == pyproject.TARGET for r in self.candidate_state.files)
                or self.candidate_state.dependencies
            )
        ):
            self._merge_warning(
                MergeConflict(
                    MergeLocation(pyproject.TARGET, ("dependency-groups",)),
                    ConflictReason.DELETED_ANCESTOR,
                )
            )
            return
        enforce_path_jail(target, Path.cwd())
        record = self._file_record(target, FilePolicy.TOML)
        baseline = (
            decode_toml_baseline(record.baseline)
            if record and record.baseline is not None
            else {}
        )
        owned_groups = baseline.get("dependency-groups", {})
        if not isinstance(owned_groups, dict):
            raise ConfigurationError(
                "Invalid owned dependency-group baseline.",
                hint="Keep dependency-group ownership as a TOML table.",
            )
        try:
            original = (
                self.workspace.read_bytes(target).decode("utf-8")
                if self.workspace.exists(target)
                else ""
            )
            local_groups = tomllib.loads(original).get("dependency-groups", {})
            accepted: list[DependencyInclude] = []
            overwrite = self.manifest.collision_strategy is CollisionStrategy.OVERWRITE
            for edge in self.manifest.dependencies.includes:
                member: dict[str, Value] = {"include-group": edge.include.value}
                previous = owned_groups.get(edge.group.value, [])
                if not isinstance(previous, list):
                    raise ConfigurationError(
                        "Invalid owned dependency-group baseline.",
                        hint="Keep owned dependency groups as arrays of include records.",
                    )
                local = (
                    local_groups.get(edge.group.value, [])
                    if isinstance(local_groups, dict)
                    else None
                )
                included = (
                    local_groups.get(edge.include.value, [])
                    if isinstance(local_groups, dict)
                    else None
                )
                ambiguous = (
                    isinstance(local, list)
                    and sum(
                        isinstance(item, dict)
                        and item.get("include-group") == edge.include.value
                        for item in local
                    )
                    > 1
                )
                if ambiguous or not isinstance(included, list):
                    self._merge_warning(
                        MergeConflict(
                            MergeLocation(
                                pyproject.TARGET,
                                ("dependency-groups", edge.group.value),
                                edge.include.value,
                            ),
                            ConflictReason.DIVERGED,
                        )
                    )
                    continue
                deleted = (
                    not isinstance(local, list)
                    or (
                        edge.group.value in owned_groups
                        and (
                            not isinstance(local_groups, dict)
                            or edge.group.value not in local_groups
                        )
                    )
                    or (
                        isinstance(previous, list)
                        and member in previous
                        and member not in local
                    )
                )
                deleted = deleted or (
                    edge.include.value in owned_groups
                    and (
                        not isinstance(local_groups, dict)
                        or edge.include.value not in local_groups
                    )
                )
                if deleted and not overwrite:
                    if member not in previous:
                        self._merge_warning(
                            MergeConflict(
                                MergeLocation(
                                    pyproject.TARGET,
                                    ("dependency-groups", edge.group.value),
                                    edge.include.value,
                                ),
                                ConflictReason.DELETED_ANCESTOR,
                            )
                        )
                    continue
                if (
                    not overwrite
                    and isinstance(local, list)
                    and member in local
                    and member not in previous
                ):
                    # Matching foreign edges are not adopted.
                    continue
                accepted.append(edge)
            updated = (
                pyproject.apply_dependency_includes(original, accepted)
                if accepted
                else original
            )
            if updated != original:
                self.fs.write_text(target, updated)
                self._resolution_dirty = True
            for edge in accepted:
                entries = owned_groups.setdefault(edge.group.value, [])
                if not isinstance(entries, list):
                    raise ConfigurationError(
                        "Invalid owned dependency-group baseline.",
                        hint="Keep owned dependency groups as arrays of include records.",
                    )
                member = {"include-group": edge.include.value}
                if member not in entries:
                    entries.append(member)
                if (
                    isinstance(local_groups, dict)
                    and edge.include.value not in local_groups
                ):
                    owned_groups.setdefault(edge.include.value, [])
            if accepted:
                baseline["dependency-groups"] = owned_groups
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        pyproject.TARGET,
                        FilePolicy.TOML,
                        encode_toml_baseline(baseline),
                    )
                )
        except (OSError, UnicodeError) as e:
            raise FileSystemError("apply dependency includes", str(target), e) from e

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.filesystem.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        enforce_path_jail(gitignore, Path.cwd())
        try:
            existing_content = (
                self.workspace.read_text(gitignore)
                if self.workspace.exists(gitignore)
                else ""
            )
            new_content = generate_gitignore(
                vcs_ignores=self.manifest.filesystem.vcs_ignores,
                existing_content=existing_content,
            )
            if new_content is not None:
                self.fs.write_text(gitignore, new_content)
                missing_count = len(
                    self.manifest.filesystem.vcs_ignores
                    - {line.strip() for line in existing_content.splitlines()}
                )
                logger.debug(f"Appended {missing_count} items to .gitignore")
        except OSError as e:
            raise FileSystemError(
                "update workspace ignore manifest (.gitignore)", str(gitignore), e
            ) from e

    def _write_docker_artifacts(self) -> None:
        """Generates container artifacts (.dockerignore and Dockerfile)."""
        if not self.docker:
            return

        dockerfile = Path(DOCKERFILE)
        dockerignore = Path(".dockerignore")
        enforce_path_jail(dockerfile, Path.cwd())
        enforce_path_jail(dockerignore, Path.cwd())
        self._validate_node(dockerignore)

        try:
            existing_content = (
                ""
                if (
                    self.manifest.collision_strategy == CollisionStrategy.OVERWRITE
                    or not self.workspace.exists(dockerignore)
                )
                else self.workspace.read_text(dockerignore)
            )
            has_uv_init = any(
                task.command[:2] == ["uv", "init"]
                for task in self.manifest.tasks.system_tasks
            )
            new_dockerignore = generate_dockerignore(
                vcs_ignores=self.manifest.filesystem.vcs_ignores,
                has_uv_init=has_uv_init,
                existing_content=existing_content,
            )
        except OSError as e:
            raise FileSystemError(
                "scaffold container runtime ignore configurations",
                str(dockerignore),
                e,
            ) from e

        context = self.interpolation_context
        is_script_or_typer = "typer" in self.manifest.dependencies.dependencies or any(
            "project.scripts" in app.content
            for app in self.manifest.filesystem.structured.get(pyproject.TARGET, [])
        )
        docker_port = (
            str(self.manifest.metadata.get("docker_port"))
            if self.manifest.metadata.get("docker_port")
            else None
        )
        dockerfile_content = generate_dockerfile(
            DockerfileSpec(
                python_version=context["PYTHON_VERSION"],
                project_name=context["PROJECT_NAME"],
                package_name=context["PACKAGE_NAME"],
                dependencies=self.manifest.dependencies.dependencies,
                docker_port=docker_port,
                is_script_or_typer=is_script_or_typer,
            )
        )

        if new_dockerignore is not None:
            try:
                self.fs.write_text(dockerignore, new_dockerignore)
                logger.debug(
                    "Scaffolded container runtime ignore configurations (.dockerignore)"
                )
            except OSError as e:
                raise FileSystemError(
                    "scaffold container runtime ignore configurations",
                    str(dockerignore),
                    e,
                ) from e

        try:
            self._write_generated(dockerfile, dockerfile_content)
            logger.debug("Scaffolded Dockerfile")
        except OSError as e:
            raise FileSystemError(
                "scaffold container runtime configurations (Dockerfile)",
                str(dockerfile),
                e,
            ) from e

    def _write_ide_settings(self) -> None:
        """Reconciles IDE workspace preferences without discarding user content.

        A malformed existing settings file is an editor convenience, so it is
        skipped with a warning rather than aborting the run.
        """
        settings = self.manifest.ide_settings
        if not settings:
            return
        try:
            if self.workspace.exists(Path(vscode.SETTINGS_TARGET)):
                parse_jsonc(
                    self.workspace.read_bytes(Path(vscode.SETTINGS_TARGET)).decode(
                        "utf-8"
                    ),
                    allow_empty=True,
                )
        except (OSError, UnicodeError) as error:
            raise FileSystemError(
                "inspect active IDE settings files",
                vscode.SETTINGS_TARGET,
                error,
            ) from error
        except ConfigurationError:
            self.add_diagnostic(
                DiagnosticPhase.EXECUTOR,
                "Existing settings.json is not a valid JSONC object (syntax error or "
                "duplicate keys). Skipping IDE settings injection to prevent data loss.",
                Severity.WARNING,
            )
            return
        if located := self._locate(vscode.SETTINGS_TARGET, FilePolicy.JSONC):
            self._reconcile_document(
                located,
                dumps_jsonc(
                    cast(dict[str, Value], dict(settings)), vscode.SETTINGS_INDENT
                ),
                FilePolicy.JSONC,
                indent=vscode.SETTINGS_INDENT,
            )

    def _proposing(self, target: Path, record: FileState | None) -> bool:
        """Returns whether changes into an existing file are proposals.

        They are while the file existed before this run and Protostar owns
        nothing in it, neither now nor in the committed state: the content is
        the user's, so each change into it can be declined.

        Args:
            target: The file being reconciled.
            record: Its current ownership record, if any.
        """
        return (
            record is None
            and target.as_posix() not in self._owned_on_disk
            and self.workspace.exists(target)
            and self.journal.was_present(target)
        )

    def _merge_warning(self, conflict: MergeConflict) -> None:
        """Exposes a concrete preserved conflict to headless callers."""
        where = describe_location(conflict.location)
        self.diagnostics.append(
            DiagnosticEvent(
                DiagnosticPhase.EXECUTOR,
                f"Preserving local contribution in {conflict.location.file}"
                f"{f': {where}' if where else ''}.",
                Severity.WARNING,
                conflict=conflict,
            )
        )

    def _report(
        self,
        conflicts: tuple[MergeConflict, ...],
        resolved: tuple[MergeConflict, ...],
        proposals: tuple[MergeConflict, ...] = (),
        preserved: tuple[MergeConflict, ...] = (),
    ) -> None:
        """Exposes open and settled conflicts to headless callers.

        Proposals and preserved deviations are no anomaly, so the review lists
        them without a diagnostic.
        """
        self.proposals.extend(proposals)
        self.preserved.extend(preserved)
        for conflict in conflicts:
            self._merge_warning(conflict)
        for conflict in resolved:
            where = describe_location(conflict.location)
            kept = {
                ResolutionChoice.LOCAL: "keeping local content",
                ResolutionChoice.DESIRED: "taking the update",
                ResolutionChoice.BOTH: "keeping both",
            }[cast(ResolutionChoice, conflict.resolution)]
            noun = (
                "local change"
                if conflict.reason is ConflictReason.PRESERVED
                else "conflict"
            )
            self.diagnostics.append(
                DiagnosticEvent(
                    DiagnosticPhase.EXECUTOR,
                    f"Resolved {noun} in {conflict.location.file}"
                    f"{f' at {where}' if where else ''} by {kept}.",
                    Severity.INFO,
                    resolved=conflict,
                )
            )

    def _layout_warning(self, target: Path, reason: str) -> None:
        """Reports a file that was left unformatted because formatting was unsafe."""
        self.diagnostics.append(
            DiagnosticEvent(
                DiagnosticPhase.EXECUTOR,
                f"Left {target.as_posix()} unformatted: {reason}.",
                Severity.WARNING,
            )
        )

    def _validate_node(self, target: Path, *, directory: bool = False) -> None:
        """Rejects unsafe nodes before reads or transaction mutations."""
        if isinstance(self.workspace, ReviewWorkspace):
            self.workspace.capture(target, directory=directory)
            return
        target = self.journal.normalize_path(target)
        for node in (target, *target.parents):
            if node == self.journal.workspace_root:
                break
            try:
                mode = node.lstat().st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode) or not (
                stat.S_ISREG(mode)
                if node == target and not directory
                else stat.S_ISDIR(mode)
            ):
                raise UnsupportedFilesystemNodeError(
                    node, "unsupported transaction target"
                )

    def _load_state(self) -> None:
        """Validates committed ownership before any mutation."""
        target = Path("protostar.lock")
        self._validate_node(target)
        try:
            self._state_bytes = (
                self.workspace.read_bytes(target)
                if self.workspace.exists(target)
                else None
            )
            if self._state_bytes is not None:
                state = deserialize_state(self._state_bytes.decode("utf-8"))
                check_producer_version(state, self.candidate_state.producer_version)
                check_template_identity(state, self.manifest.template_reference)
                self._committed = state
                reference = self.manifest.template_reference
                if reference is not None and state.template is not None:
                    reference = replace(reference, migrated=state.template.migrated)
                self.candidate_state = replace(
                    state,
                    producer_version=self.candidate_state.producer_version,
                    template=reference,
                )
                paths = (
                    {r.path for r in state.files}
                    | {r.path for r in state.dependencies}
                    | {r.path for r in state.hook_pins}
                )
                self._owned_on_disk = frozenset(paths)
                for path in paths:
                    self._validate_node(Path(path))
                # Capture deletion before initializer tasks can recreate the file.
                self._preserve_deleted_pyproject = (
                    pyproject.TARGET in paths
                    and not self.workspace.exists(Path(pyproject.TARGET))
                    and self.manifest.collision_strategy
                    is not CollisionStrategy.OVERWRITE
                )
        except (OSError, UnicodeError) as e:
            raise ConfigurationError(
                "Cannot read Protostar state.",
                hint="Correct the state file encoding and permissions.",
            ) from e

    def _write_recipe(self) -> None:
        """Commits requested intent separately from accepted ownership baselines."""
        from .recipe import edit_recipe

        target = Path(pyproject.TARGET)
        if self.manifest.recipe is None or self._preserve_deleted_pyproject:
            return
        try:
            original = (
                self.workspace.read_text(target)
                if self.workspace.exists(target)
                else ""
            )
            content = edit_recipe(original, self.manifest.recipe)
            if not self.journal.was_present(target):
                # Protostar created this file, so it owns its layout; a project the
                # user already had keeps whatever order they gave it.
                content = pyproject.finalize_new_pyproject(
                    content, lambda reason: self._layout_warning(target, reason)
                )
            if content != original:
                self.fs.write_text(target, content)
        except (OSError, UnicodeError) as e:
            raise FileSystemError("write project recipe", str(target), e) from e

    def _release_undeclared_dependencies(self) -> None:
        """Removes owned requirements that no producer requests any more.

        The removal edits pyproject.toml directly, so the lock is refreshed
        afterwards; see ``retract_requirements`` for each outcome.
        """
        dependencies = self.manifest.dependencies
        if not self.candidate_state.dependencies:
            return
        target = Path(pyproject.TARGET)
        original = (
            self.workspace.read_text(target) if self.workspace.exists(target) else ""
        )
        data = tomllib.loads(original)
        groups = (DependencyGroup.MAIN, DependencyGroup.DEV, DependencyGroup.DOCS)
        retraction = retract_requirements(
            {
                DependencyGroup.MAIN: dependencies.dependencies,
                DependencyGroup.DEV: dependencies.dev_dependencies,
                DependencyGroup.DOCS: dependencies.docs_dependencies,
            },
            {group: requirement_entries(data, group) for group in groups},
            self.candidate_state.dependencies,
            self.resolutions,
        )
        self._report(retraction.conflicts, retraction.resolved)
        updated = original
        for group, entries in retraction.removed:
            updated = pyproject.remove_requirements(updated, group, entries)
        if updated != original:
            self.fs.write_text(target, updated)
            self._resolution_dirty = True
        self.candidate_state = replace(
            self.candidate_state,
            dependencies=tuple(
                r
                for r in self.candidate_state.dependencies
                if r.identity not in retraction.released
            ),
        )

    def _select_dependencies(self) -> tuple[DependencyManifest, set[DependencyGroup]]:
        """Selects resolver requests without predicting materialized requirements."""
        self._release_undeclared_dependencies()
        dependencies = self.manifest.dependencies
        if not (
            dependencies.dependencies
            or dependencies.dev_dependencies
            or dependencies.docs_dependencies
        ):
            return DependencyManifest(), set()
        target = Path(pyproject.TARGET)
        data = (
            tomllib.loads(self.workspace.read_text(target))
            if self.workspace.exists(target)
            else {}
        )
        groups = (
            (DependencyGroup.MAIN, dependencies.dependencies),
            (DependencyGroup.DEV, dependencies.dev_dependencies),
            (DependencyGroup.DOCS, dependencies.docs_dependencies),
        )
        selected: dict[DependencyGroup, list[str]] = {}
        blocked: set[DependencyGroup] = set()
        # A project whose requirements Protostar never owned proposes each one.
        proposing = not self.candidate_state.dependencies and self._proposing(
            target, None
        )
        for group, desired in groups:
            tracked_file = any(
                r.path == pyproject.TARGET for r in self.candidate_state.files
            ) or bool(self.candidate_state.dependencies)
            table = data.get(
                "project" if group is DependencyGroup.MAIN else "dependency-groups", {}
            )
            owned_group = any(
                r.group is group for r in self.candidate_state.dependencies
            )
            file_record = next(
                (
                    r
                    for r in self.candidate_state.files
                    if r.path == pyproject.TARGET and r.baseline is not None
                ),
                None,
            )
            baseline = (
                decode_toml_baseline(file_record.baseline)
                if file_record and file_record.baseline is not None
                else {}
            )
            ancestor_key = (
                "project" if group is DependencyGroup.MAIN else "dependency-groups"
            )
            baseline_groups = baseline.get("dependency-groups", {})
            owned_group = owned_group or (
                group is not DependencyGroup.MAIN
                and isinstance(baseline_groups, dict)
                and group.value in baseline_groups
            )
            owned_ancestor = ancestor_key in baseline
            ancestor_deleted = owned_ancestor and (
                ancestor_key not in data or not isinstance(data[ancestor_key], dict)
            )
            deleted = (
                (tracked_file and not self.workspace.exists(target))
                or ancestor_deleted
                or (
                    owned_group
                    and (
                        not isinstance(table, dict)
                        or (
                            "dependencies"
                            if group is DependencyGroup.MAIN
                            else group.value
                        )
                        not in table
                    )
                )
            )
            if (
                deleted
                and self.manifest.collision_strategy is not CollisionStrategy.OVERWRITE
            ):
                selected[group] = []
                blocked.add(group)
                for package in desired:
                    identity = requirement_identity(package)
                    previous = next(
                        (
                            r
                            for r in self.candidate_state.dependencies
                            if r.group is group and (r.name, r.marker) == identity
                        ),
                        None,
                    )
                    if previous and normalized_requirement(
                        previous.declared
                    ) == normalized_requirement(package):
                        continue
                    self._merge_warning(
                        MergeConflict(
                            MergeLocation(
                                pyproject.TARGET,
                                ("dependencies", group.value),
                                ":".join(requirement_identity(package)),
                            ),
                            ConflictReason.DELETED_ANCESTOR,
                        )
                    )
                continue
            overwrite = self.manifest.collision_strategy is CollisionStrategy.OVERWRITE
            result = select_dependencies(
                desired,
                requirement_entries(data, group),
                self.candidate_state.dependencies,
                group,
                overwrite=overwrite,
                proposing=not overwrite and proposing,
                resolutions=self.resolutions,
            )
            selected[group] = list(result.packages)
            self._report(
                result.conflicts, result.resolved, result.proposals, result.preserved
            )
            if result.records:
                kept = {record.identity for record in result.records}
                self.candidate_state = replace(
                    self.candidate_state,
                    dependencies=(
                        *(
                            r
                            for r in self.candidate_state.dependencies
                            if r.identity not in kept
                        ),
                        *result.records,
                    ),
                )
        accepted = DependencyManifest(
            dependencies=selected[DependencyGroup.MAIN],
            dev_dependencies=selected[DependencyGroup.DEV],
            docs_dependencies=selected[DependencyGroup.DOCS],
            resolver_footprint=dependencies.resolver_footprint,
        )
        return accepted, blocked

    def _materialize_dependencies(
        self, accepted: DependencyManifest, blocked: set[DependencyGroup]
    ) -> None:
        """Records actual workspace requirements after resolver execution or convergence."""
        target = Path(pyproject.TARGET)
        dependencies = self.manifest.dependencies
        groups = (
            (DependencyGroup.MAIN, dependencies.dependencies),
            (DependencyGroup.DEV, dependencies.dev_dependencies),
            (DependencyGroup.DOCS, dependencies.docs_dependencies),
        )
        selected = {
            DependencyGroup.MAIN: accepted.dependencies,
            DependencyGroup.DEV: accepted.dev_dependencies,
            DependencyGroup.DOCS: accepted.docs_dependencies,
        }
        materialized = (
            tomllib.loads(self.workspace.read_text(target))
            if self.workspace.exists(target)
            else {}
        )
        records = list(self.candidate_state.dependencies)
        for group, desired in groups:
            if group in blocked:
                continue
            for package in desired:
                identity = requirement_identity(package)
                record = next(
                    (
                        r
                        for r in records
                        if r.group is group and (r.name, r.marker) == identity
                    ),
                    None,
                )
                entries = [
                    e
                    for e in requirement_entries(materialized, group)
                    if requirement_identity(e) == identity
                ]
                if (
                    record
                    and len(entries) == 1
                    and normalized_requirement(record.declared)
                    != normalized_requirement(package)
                    and normalized_requirement(entries[0])
                    == normalized_requirement(package)
                ):
                    records = [
                        replace(r, declared=package, materialized=entries[0])
                        if r.identity == record.identity
                        else r
                        for r in records
                    ]
        for group, packages in selected.items():
            for package in packages:
                name, marker = requirement_identity(package)
                entries = [
                    entry
                    for entry in requirement_entries(materialized, group)
                    if requirement_identity(entry) == (name, marker)
                ]
                if len(entries) == 1:
                    record = DependencyState(
                        pyproject.TARGET, group, name, marker, package, entries[0]
                    )
                    records = [r for r in records if r.identity != record.identity]
                    records.append(record)
        self.candidate_state = replace(
            self.candidate_state, dependencies=tuple(records)
        )
