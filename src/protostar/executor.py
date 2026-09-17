import datetime
import json
import logging
import stat
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import cast

from .appends import append_marker_blocks
from .checksum import checksum_gate
from .config import UserConfig
from .dependencies import (
    install_dependencies,
    normalized_requirement,
    requirement_entries,
    requirement_identity,
    select_dependencies,
)
from .errors import (
    ConfigurationError,
    FileSystemError,
    UnsupportedFilesystemNodeError,
)
from .fs_transaction import TransactionAwareFS
from .ide import check_ide_extensions, write_ide_settings
from .intent import (
    AppendContribution,
    ContributionPolicy,
    DependencyGroup,
    DependencyInclude,
    ResolverFootprint,
    StructuredFormat,
    validate_target,
)
from .interpolation import render_template
from .journal import MutationJournal
from .manifest import (
    CollisionStrategy,
    DependencyManifest,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
    SystemTask,
)
from .merge import MISSING, ConflictReason, MergeConflict, MergeLocation, Value
from .pre_commit import reconcile_hook_config
from .registry import resolve_hook_revisions
from .security import enforce_binary_safelist, enforce_path_jail
from .sync_state import (
    DependencyState,
    FilePolicy,
    FileState,
    RegionState,
    SyncState,
    check_template_identity,
    decode_toml_baseline,
    deserialize_state,
    encode_toml_baseline,
    serialize_state,
)
from .system import ProcessRunner, shield_sigint
from .toml_ast import (
    aggregate_toml,
    aggregate_toml_document,
    apply_dependency_includes,
    reconcile_toml,
)
from .workflows import (
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
from .yaml_ast import decode_yaml_baseline, encode_yaml_baseline, reconcile_codecov

logger = logging.getLogger("protostar")

__all__ = ["SystemExecutor"]


class SystemExecutor:
    """Executes the materialized environment manifest by mutating the local disk and shell."""

    def __init__(
        self,
        manifest: EnvironmentManifest,
        config: UserConfig,
        docker: bool = False,
    ) -> None:
        """Initializes the executor with the target manifest state.

        Args:
            manifest: The centralized state object containing all execution directives.
            config: The active Protostar configuration instance.
            docker: If True, scaffolds a .dockerignore from the manifest ignores.
        """
        self.manifest = manifest
        self.hook_revisions = (
            resolve_hook_revisions() if manifest.tooling.wants_hooks else ()
        )
        self.config = config
        self.docker = docker or manifest.tooling.wants_docker
        if self.docker:
            manifest.tooling.wants_docker = True
        self.journal = MutationJournal()
        self.fs = TransactionAwareFS(self.journal)
        self.process_runner = ProcessRunner()
        self.diagnostics: list[DiagnosticEvent] = []
        self.completed_tasks: list[SystemTask] = []
        self.interrupted_task: SystemTask | None = None
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

    # --- Architecture Note: Deterministic Pipeline Sequencing ---
    # The execution phases in `execute()` follow a strict dependency order:
    #   1. Pre-flight Validation: Fast C-optimized TOML syntax check before writing to disk.
    #   2. Directory & File Realization: Basic structure & config injection prior to task invocation.
    #   3. System Tasks: Git initialization must occur before pre-commit/nbdime post-install tasks.
    #   4. Dependency Resolution: `uv add` runs before post-install tasks so installed binaries
    #      are present in `.venv/bin`.
    #   5. IDE Diagnostics: Runs last as non-blocking diagnostic warnings.
    def execute(self) -> None:
        """Executes the materialized manifest in a deterministic sequence."""
        try:
            from .recipe import decode_recipe, read_recipe

            if self.manifest.recipe:
                decode_recipe(self.manifest.recipe.to_dict())
            self._load_state()

            self._validate_node(Path("pyproject.toml"))
            read_recipe(Path("pyproject.toml"))
            self._validate_targets()
            self._create_directories()
            self._write_injected_files()
            self._write_pre_commit_config()
            self._write_ci_workflow()
            self._write_release_workflow()
            self._write_justfile()
            self._run_tasks(self.manifest.tasks.system_tasks)
            self._append_files()
            self._apply_dependency_includes()
            self._install_dependencies()
            if self._resolution_dirty:
                self._run_lock(self.manifest.dependencies.resolver_footprint)
            self._write_ignores()
            self._write_docker_artifacts()
            self._write_ide_settings()
            self._run_tasks(self.manifest.tasks.post_install_tasks)
            self._check_ide_extensions()
            self._write_recipe()
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
        )

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
                "pyproject.toml"
            ):
                raise ConfigurationError(
                    "Free-form pyproject.toml replacement is unsupported.",
                    hint="Declare structured contributions; tool.protostar is reserved.",
                )
        for filepath, contributions in self.manifest.filesystem.structured.items():
            if any(c.format is StructuredFormat.YAML for c in contributions):
                if len(contributions) != 1 or filepath != ".github/codecov.yml":
                    raise ConfigurationError(
                        "Unsupported YAML contributions.",
                        hint="Declare exactly one Codecov YAML producer.",
                    )
                decode_yaml_baseline(contributions[0].content)
                target = Path(filepath)
                if target.exists():
                    try:
                        decode_yaml_baseline(target.read_bytes().decode("utf-8"))
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
            toml_targets.add("pyproject.toml")
        for _group, packages in (
            (DependencyGroup.MAIN, deps.dependencies),
            (DependencyGroup.DEV, deps.dev_dependencies),
            (DependencyGroup.DOCS, deps.docs_dependencies),
        ):
            for package in packages:
                requirement_identity(package)
        for filepath in sorted(toml_targets):
            target = Path(render_template(filepath, self.interpolation_context))
            self._validate_node(target)
            if target.suffix == ".toml" and target.exists():
                try:
                    with target.open("rb") as f:
                        tomllib.load(f)
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

        target = Path(".pre-commit-config.yaml")
        enforce_path_jail(target, Path.cwd())
        full_yaml = generate_pre_commit_config(
            local_hooks=self.manifest.tooling.pre_commit_local_hooks,
            remote_hooks=self.manifest.tooling.pre_commit_hooks,
            dependencies=self.manifest.dependencies.dependencies,
            hook_runner=self.manifest.tooling.hook_runner,
            install_hook_types=self.manifest.tooling.pre_commit_install_hook_types,
        )

        record = next(
            (r for r in self.candidate_state.files if r.path == target.as_posix()), None
        )
        if record is not None and record.policy is not FilePolicy.YAML:
            raise ConfigurationError(
                "Conflicting pre-commit ownership policy.",
                hint="Keep the tracked file policy unchanged.",
            )
        self._validate_node(target)
        try:
            original = target.read_bytes().decode("utf-8") if target.exists() else ""
            result, pins = reconcile_hook_config(
                original,
                full_yaml,
                record,
                self.hook_revisions,
                self.candidate_state.hook_pins,
                missing_file=not target.exists(),
                overwrite=self.manifest.collision_strategy
                is CollisionStrategy.OVERWRITE,
            )
            for conflict in result.conflicts:
                self._merge_warning(conflict)
            if result.baseline is not MISSING:
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        FilePolicy.YAML,
                        encode_yaml_baseline(cast(dict[str, Value], result.baseline)),
                    )
                )
            self.candidate_state = replace(self.candidate_state, hook_pins=pins)
            if result.content != original:
                self.fs.write_text(target, result.content)
        except (OSError, UnicodeError) as error:
            raise FileSystemError(
                "reconcile pre-commit configuration", str(target), error
            ) from error

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
            if target.as_posix() == ".github/renovate.json":
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as error:
                    raise ConfigurationError(
                        "Invalid generated Renovate JSON.",
                        hint="Provide strict JSON for the generated configuration.",
                    ) from error
                if not isinstance(parsed, dict):
                    raise ConfigurationError(
                        "Invalid generated Renovate root.",
                        hint="Provide a JSON object.",
                    )
                alternatives = (
                    "renovate.json",
                    "renovate.json5",
                    ".renovaterc",
                    ".renovaterc.json",
                    ".renovaterc.json5",
                    ".github/renovate.json5",
                    ".gitlab/renovate.json",
                    ".gitlab/renovate.json5",
                )
                if any(Path(path).exists() for path in alternatives):
                    self._merge_warning(
                        MergeConflict(
                            MergeLocation(target.as_posix()), ConflictReason.UNOWNED
                        )
                    )
                    continue
                self._write_generated(target, content)
                continue
            record = self._file_record(target, FilePolicy.SEED)
            if self.manifest.collision_strategy is not CollisionStrategy.OVERWRITE and (
                target.exists() or record is not None
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
                    FileState(target.as_posix(), FilePolicy.SEED)
                )
            except OSError as e:
                raise FileSystemError("inject boilerplate file", str(target), e) from e
            logger.debug(f"Injected configuration file: {interpolated_filepath}")

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
            binary_name = Path(task.command[0]).name
            msg = task.description or f"Running: {binary_name}"

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

            logger.info(msg)
            try:
                self.process_runner.run(task.command, timeout=task.timeout)
                self.completed_tasks.append(task)
            except BaseException:
                self.interrupted_task = task
                raise

    def _write_ci_workflow(self) -> None:
        """Assembles and writes the .github/workflows/ci.yml file if requested."""
        if not self.manifest.tooling.wants_ci:
            return

        target = Path(".github/workflows/ci.yml")
        enforce_path_jail(target, Path.cwd())
        workflow = generate_ci_workflow(
            CIWorkflowSpec(
                supported_os=self.manifest.metadata.get("supported_os", ["Linux"]),
                min_python=self.manifest.metadata.get("minimum_python", "3.13"),
                ci_flags=self.manifest.tooling.ci_flags,
                ci_steps=self.manifest.tooling.ci_steps,
            )
        )
        try:
            self._write_generated(target, workflow)
        except OSError as e:
            raise FileSystemError("write CI workflow", str(target), e) from e

    def _write_release_workflow(self) -> None:
        """Assembles and writes the .github/workflows/release.yml file if requested."""
        if not self.manifest.tooling.wants_release:
            return

        target = Path(".github/workflows/release.yml")
        enforce_path_jail(target, Path.cwd())
        workflow = generate_release_workflow()
        try:
            self._write_generated(target, workflow)
        except OSError as e:
            raise FileSystemError("write release workflow", str(target), e) from e

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

    def _reconcile_codecov(self, desired: str) -> None:
        """Applies the YAML pilot through the transaction and candidate state."""
        target = Path(".github/codecov.yml")
        record = next(
            (r for r in self.candidate_state.files if r.path == target.as_posix()), None
        )
        if record is not None and record.policy is not FilePolicy.YAML:
            raise ConfigurationError(
                "Conflicting structured ownership policy.",
                hint="Keep the tracked file policy unchanged.",
            )
        try:
            original = target.read_bytes().decode("utf-8") if target.exists() else ""
            result = reconcile_codecov(
                original,
                desired,
                decode_yaml_baseline(record.baseline)
                if record and record.baseline is not None
                else MISSING,
                MergeLocation(target.as_posix()),
                missing_file=not target.exists(),
                overwrite=self.manifest.collision_strategy
                is CollisionStrategy.OVERWRITE,
            )
            for conflict in result.conflicts:
                self._merge_warning(conflict)
            if result.baseline is not MISSING:
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        FilePolicy.YAML,
                        encode_yaml_baseline(cast(dict[str, Value], result.baseline)),
                    )
                )
            if result.content != original:
                self.fs.write_text(target, result.content)
        except (OSError, UnicodeError) as error:
            raise FileSystemError(
                "reconcile Codecov configuration", str(target), error
            ) from error

    # --- Architectural Note: AST-Preserving TOML Merging ---
    # Protostar uses `tomlkit` AST parsing rather than standard dictionary updates or tomllib/tomli.
    #
    # Rationale:
    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        is_overwrite = self.manifest.collision_strategy == CollisionStrategy.OVERWRITE
        for filepath, contributions in self.manifest.filesystem.structured.items():
            if contributions[0].format is StructuredFormat.YAML:
                self._reconcile_codecov(contributions[0].content)
                continue
            target = Path(render_template(filepath, self.interpolation_context))
            validate_target(target.as_posix())
            enforce_path_jail(target, Path.cwd())
            try:
                original = (
                    target.read_bytes().decode("utf-8") if target.exists() else ""
                )
            except (OSError, UnicodeError) as e:
                raise FileSystemError(
                    "read structured configuration", str(target), e
                ) from e
            record = next(
                (r for r in self.candidate_state.files if r.path == target.as_posix()),
                None,
            )
            if record is not None and record.policy is not FilePolicy.TOML:
                raise ConfigurationError(
                    "Conflicting structured ownership policy.",
                    hint="Keep the tracked file policy unchanged.",
                )
            deleted_project = (
                target == Path("pyproject.toml") and self._preserve_deleted_pyproject
            )
            initializing = (
                not self.journal.was_present(target)
                and record is None
                and not deleted_project
            )
            payloads = [
                replace(
                    c, content=render_template(c.content, self.interpolation_context)
                )
                for c in contributions
                if c.policy is not ContributionPolicy.SEED_ONLY
                or is_overwrite
                or initializing
            ]
            if not payloads:
                continue
            aggregated = aggregate_toml_document(payloads)
            if deleted_project and record is None:
                self._merge_warning(
                    MergeConflict(
                        MergeLocation(target.as_posix()),
                        ConflictReason.DELETED_ANCESTOR,
                    )
                )
                continue
            result = reconcile_toml(
                original,
                aggregated.value,
                decode_toml_baseline(record.baseline)
                if record and record.baseline is not None
                else MISSING,
                MergeLocation(target.as_posix()),
                overwrite=is_overwrite,
                initializing=initializing,
                missing_file=not target.exists(),
                desired_ast=aggregated.document,
            )
            for conflict in result.conflicts:
                self._merge_warning(conflict)
            if result.baseline is not MISSING:
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        FilePolicy.TOML,
                        encode_toml_baseline(cast(dict[str, Value], result.baseline)),
                    )
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
                    target == Path("pyproject.toml")
                    and any(c.resolver_footprint for c in contributions)
                    and original_python != updated_python
                ):
                    self._resolution_dirty = True
        for filepath, regions in self.manifest.filesystem.regions.items():
            target = Path(render_template(filepath, self.interpolation_context))
            validate_target(target.as_posix())
            enforce_path_jail(target, Path.cwd())
            try:
                original = (
                    target.read_bytes().decode("utf-8") if target.exists() else ""
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
                FilePolicy.CHECKSUM,
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
                baselines={r.id: r.digest for r in record.regions} if record else {},
                missing_owned_file=record is not None and not target.exists(),
            )
            for identity in region_result.conflicts:
                self._merge_warning(
                    MergeConflict(
                        MergeLocation(target.as_posix(), identity=identity),
                        ConflictReason.DIVERGED if record else ConflictReason.UNOWNED,
                    )
                )
            if region_result.digests:
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        record.policy if record else FilePolicy.REGIONS,
                        digest=record.digest if record else None,
                        regions=tuple(
                            RegionState(identity, digest)
                            for identity, digest in region_result.digests.items()
                        ),
                    )
                )
            if region_result.content != original:
                try:
                    self.fs.write_text(target, region_result.content)
                except OSError as e:
                    raise FileSystemError(
                        "append configurations block", str(target), e
                    ) from e

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
        """Applies the shared checksum gate transactionally to exact generated bytes."""
        enforce_path_jail(target, Path.cwd())
        self._validate_node(target)
        record = next(
            (r for r in self.candidate_state.files if r.path == target.as_posix()), None
        )
        if record is not None and record.policy not in (
            FilePolicy.CHECKSUM,
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
            # Digests cannot reconstruct omitted payloads. Preserve the whole file
            # rather than removing a region during otherwise clean regeneration.
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
            local = target.read_bytes() if target.exists() else None
            desired = content.encode("utf-8")
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
            result = checksum_gate(
                local,
                desired,
                record.digest if record else None,
                overwrite=self.manifest.collision_strategy
                is CollisionStrategy.OVERWRITE,
            )
            if result.conflict:
                self._merge_warning(
                    MergeConflict(
                        MergeLocation(target.as_posix()),
                        ConflictReason.DIVERGED if record else ConflictReason.UNOWNED,
                    )
                )
            if result.write:
                self.fs.write_text(target, content)
            if result.digest is not None:
                regions = {r.id: r.digest for r in record.regions} if record else {}
                if result.write or (record is not None and local == desired):
                    regions.update(framed.digests)
                self.candidate_state = self.candidate_state.with_file(
                    FileState(
                        target.as_posix(),
                        FilePolicy.CHECKSUM,
                        digest=result.digest,
                        regions=tuple(
                            RegionState(identity, digest)
                            for identity, digest in regions.items()
                        ),
                    )
                )
        except OSError as error:
            raise FileSystemError("write generated file", str(target), error) from error

    def _apply_dependency_includes(self) -> None:
        """Applies typed include edges before uv add observes dependency metadata."""
        if not self.manifest.dependencies.includes:
            return
        target = Path("pyproject.toml")
        if (
            not target.exists()
            and self.manifest.collision_strategy is not CollisionStrategy.OVERWRITE
            and (
                any(r.path == "pyproject.toml" for r in self.candidate_state.files)
                or self.candidate_state.dependencies
            )
        ):
            self._merge_warning(
                MergeConflict(
                    MergeLocation("pyproject.toml", ("dependency-groups",)),
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
            original = target.read_bytes().decode("utf-8") if target.exists() else ""
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
                                "pyproject.toml",
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
                                    "pyproject.toml",
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
                apply_dependency_includes(original, accepted) if accepted else original
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
                        "pyproject.toml",
                        FilePolicy.TOML,
                        encode_toml_baseline(baseline),
                    )
                )
        except (OSError, UnicodeError) as e:
            raise FileSystemError("apply dependency includes", str(target), e) from e

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
        self.process_runner.run(["uv", "lock"], timeout=600)
        self._resolution_dirty = False

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.filesystem.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        enforce_path_jail(gitignore, Path.cwd())
        try:
            existing_content = (
                gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
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

        dockerfile = Path("Dockerfile")
        dockerignore = Path(".dockerignore")
        enforce_path_jail(dockerfile, Path.cwd())
        enforce_path_jail(dockerignore, Path.cwd())
        self._validate_node(dockerignore)

        try:
            existing_content = (
                ""
                if (
                    self.manifest.collision_strategy == CollisionStrategy.OVERWRITE
                    or not dockerignore.exists()
                )
                else dockerignore.read_text(encoding="utf-8")
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
            for app in self.manifest.filesystem.structured.get("pyproject.toml", [])
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
        """Writes the aggregated IDE configuration to the appropriate local files."""
        write_ide_settings(
            ide_settings=self.manifest.ide_settings,
            on_diagnostic=lambda msg, sev: self.add_diagnostic(
                phase=DiagnosticPhase.EXECUTOR,
                message=msg,
                severity=sev,
            ),
            fs=self.fs,
        )

    def _install_dependencies(self) -> None:
        """Installs queued dependencies using uv."""
        dependencies = self.manifest.dependencies
        if not (
            dependencies.dependencies
            or dependencies.dev_dependencies
            or dependencies.docs_dependencies
        ):
            return
        target = Path("pyproject.toml")
        data = (
            tomllib.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        )
        groups = (
            (DependencyGroup.MAIN, dependencies.dependencies),
            (DependencyGroup.DEV, dependencies.dev_dependencies),
            (DependencyGroup.DOCS, dependencies.docs_dependencies),
        )
        selected: dict[DependencyGroup, list[str]] = {}
        blocked: set[DependencyGroup] = set()
        for group, desired in groups:
            tracked_file = any(
                r.path == "pyproject.toml" for r in self.candidate_state.files
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
                    if r.path == "pyproject.toml" and r.baseline is not None
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
                (tracked_file and not target.exists())
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
                                "pyproject.toml",
                                ("dependencies", group.value),
                                ":".join(requirement_identity(package)),
                            ),
                            ConflictReason.DELETED_ANCESTOR,
                        )
                    )
                continue
            result = select_dependencies(
                desired,
                requirement_entries(data, group),
                self.candidate_state.dependencies,
                group,
                overwrite=self.manifest.collision_strategy
                is CollisionStrategy.OVERWRITE,
            )
            selected[group] = list(result.packages)
            for conflict in result.conflicts:
                self._merge_warning(conflict)
        accepted = DependencyManifest(
            dependencies=selected[DependencyGroup.MAIN],
            dev_dependencies=selected[DependencyGroup.DEV],
            docs_dependencies=selected[DependencyGroup.DOCS],
            resolver_footprint=dependencies.resolver_footprint,
        )
        if any(selected.values()):
            validate_resolver_workspace(self.journal.workspace_root)
            self._validate_resolver_project()
            for declared_path in dependencies.resolver_footprint.paths:
                path = Path(declared_path)
                enforce_path_jail(path, Path.cwd())
                self.journal.record_mutation(path)
        install_dependencies(
            dependencies_manifest=accepted, process_runner=self.process_runner
        )
        if any(selected.values()):
            self._resolution_dirty = False
        materialized = (
            tomllib.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
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
                        "pyproject.toml", group, name, marker, package, entries[0]
                    )
                    records = [r for r in records if r.identity != record.identity]
                    records.append(record)
        self.candidate_state = replace(
            self.candidate_state, dependencies=tuple(records)
        )

    def _merge_warning(self, conflict: MergeConflict) -> None:
        """Exposes a concrete preserved conflict to headless callers."""
        self.diagnostics.append(
            DiagnosticEvent(
                DiagnosticPhase.EXECUTOR,
                f"Preserving local contribution in {conflict.location.file}: {'.'.join(conflict.location.keys)}.",
                Severity.WARNING,
                conflict=conflict,
            )
        )

    def _validate_node(self, target: Path, *, directory: bool = False) -> None:
        """Rejects unsafe nodes before reads or transaction mutations."""
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
        target = Path(".protostar.lock.toml")
        self._validate_node(target)
        try:
            self._state_bytes = target.read_bytes() if target.exists() else None
            if self._state_bytes is not None:
                state = deserialize_state(self._state_bytes.decode("utf-8"))
                check_template_identity(state, self.manifest.template_reference)
                self.candidate_state = replace(
                    state,
                    producer_version=self.candidate_state.producer_version,
                    template=self.manifest.template_reference,
                )
                paths = (
                    {r.path for r in state.files}
                    | {r.path for r in state.dependencies}
                    | {r.path for r in state.hook_pins}
                )
                for path in paths:
                    self._validate_node(Path(path))
                # Capture deletion before initializer tasks can recreate the file.
                self._preserve_deleted_pyproject = (
                    "pyproject.toml" in paths
                    and not Path("pyproject.toml").exists()
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

        target = Path("pyproject.toml")
        if self.manifest.recipe is None or self._preserve_deleted_pyproject:
            return
        try:
            original = target.read_text() if target.exists() else ""
            content = edit_recipe(original, self.manifest.recipe)
            if content != original:
                self.fs.write_text(target, content)
        except (OSError, UnicodeError) as e:
            raise FileSystemError("write project recipe", str(target), e) from e

    def _write_state(self) -> None:
        """Writes candidate ownership last, before committing the journal."""
        content = serialize_state(self.candidate_state)
        if content.encode("utf-8") != self._state_bytes:
            try:
                self.fs.write_text(Path(".protostar.lock.toml"), content)
            except OSError as e:
                raise FileSystemError(
                    "write reconciliation state", ".protostar.lock.toml", e
                ) from e
