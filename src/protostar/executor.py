import datetime
import logging
import tomllib
from pathlib import Path

from .appends import append_marker_blocks
from .config import UserConfig
from .dependencies import install_dependencies
from .errors import (
    ConfigurationError,
    FileSystemError,
)
from .fs import atomic_write_text
from .ide import check_ide_extensions, write_ide_settings
from .interpolation import render_template
from .manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
    SystemTask,
)
from .registry import HookRegistry
from .security import enforce_binary_safelist, enforce_path_jail
from .system import execute_subprocess
from .toml_ast import merge_toml_payloads
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
)

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
        self.config = config
        self.docker = docker
        self.touched_paths: set[str] = set()
        self.diagnostics: list[DiagnosticEvent] = []

    def record_touch(self, path: Path | str) -> None:
        """Records a path as having been modified or created during execution."""
        try:
            rel_path = Path(path).resolve().relative_to(Path.cwd().resolve())
            self.touched_paths.add(rel_path.as_posix())
        except (ValueError, RuntimeError):
            self.touched_paths.add(str(path))

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
    #   5. IDE Diagnostics: Runs last as non-blocking telemetry warnings.
    def execute(self) -> None:
        """Executes the materialized manifest in a deterministic sequence."""
        self._validate_targets()
        self._create_directories()
        self._write_injected_files()
        self._write_pre_commit_config()
        self._write_ci_workflow()
        self._write_release_workflow()
        self._write_justfile()
        self._run_tasks(self.manifest.tasks.system_tasks)
        self._install_dependencies()
        self._append_files()
        self._write_ignores()
        self._write_docker_artifacts()
        self._write_ide_settings()
        self._run_tasks(self.manifest.tasks.post_install_tasks)
        self._check_ide_extensions()

    def _check_ide_extensions(self) -> None:
        """Verifies that the configured IDE has the recommended extensions installed.

        Fails silently if the IDE CLI is unavailable or execution fails. Appends a warning
        diagnostic only on a successful check that uncovers missing extensions.
        """
        check_ide_extensions(
            ide=self.config.ide,
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
            SystemExit: If an existing target TOML file contains syntax errors.
        """
        for filepath in self.manifest.filesystem.file_appends:
            target = Path(filepath)
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
        if (
            not self.manifest.tooling.wants_pre_commit
            and not self.manifest.tooling.wants_prek
        ):
            return

        target = Path(".pre-commit-config.yaml")
        enforce_path_jail(target, Path.cwd())
        if self.manifest.should_skip_file(target):
            self.add_diagnostic(
                phase=DiagnosticPhase.PRE_COMMIT,
                message=f"Skipping {target.name} generation; file already exists.",
                severity=Severity.SKIP,
            )
            return

        full_yaml = generate_pre_commit_config(
            local_hooks=self.manifest.tooling.pre_commit_local_hooks,
            remote_hooks=self.manifest.tooling.pre_commit_hooks,
            dependencies=self.manifest.dependencies.dependencies,
            is_prek=self.manifest.tooling.wants_prek,
            install_hook_types=self.manifest.tooling.pre_commit_install_hook_types,
        )

        full_yaml = HookRegistry.resolve_placeholders(full_yaml)

        try:
            atomic_write_text(target, full_yaml)
            self.record_touch(target)
        except OSError as e:
            raise FileSystemError("write configuration file", str(target), e) from e
        logger.debug("Scaffolded .pre-commit-config.yaml")

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
            if self.manifest.should_skip_file(target):
                self.add_diagnostic(
                    phase=DiagnosticPhase.EXECUTOR,
                    message=f"Skipping {target.name} generation; file already exists.",
                    severity=Severity.SKIP,
                )
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(target, content)
                self.record_touch(target)
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
                path.mkdir(parents=True, exist_ok=True)
                self.record_touch(path)
            except OSError as e:
                raise FileSystemError(
                    "create scaffolding directory", str(path), e
                ) from e
            logger.debug(f"Scaffolded directory: {path}")

    def _run_tasks(self, tasks: list[SystemTask]) -> None:
        """Runs a sequence of system tasks (e.g., initialization or post-install commands)."""
        for task in tasks:
            enforce_binary_safelist(task.command)
            binary_name = Path(task.command[0]).name
            msg = task.description or f"Propelling sequence: {binary_name}"
            logger.info(msg)
            execute_subprocess(task.command, timeout=task.timeout)

    def _write_ci_workflow(self) -> None:
        """Assembles and writes the .github/workflows/ci.yml file if requested."""
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
        target = Path(".github/workflows/ci.yml")
        enforce_path_jail(target, Path.cwd())
        atomic_write_text(target, workflow)
        self.record_touch(target)

    def _write_release_workflow(self) -> None:
        """Assembles and writes the .github/workflows/release.yml file if requested."""
        if not self.manifest.tooling.wants_release:
            return

        workflow = generate_release_workflow()
        target = Path(".github/workflows/release.yml")
        enforce_path_jail(target, Path.cwd())
        atomic_write_text(target, workflow)
        self.record_touch(target)

    def _write_justfile(self) -> None:
        """Assembles and writes the justfile if requested."""
        if not self.manifest.tooling.wants_just:
            return

        target = Path("justfile")
        enforce_path_jail(target, Path.cwd())
        if self.manifest.should_skip_file(target):
            self.add_diagnostic(
                phase=DiagnosticPhase.JUST,
                message=f"Skipping {target.name} generation; file already exists.",
                severity=Severity.SKIP,
            )
            return

        full_content = generate_justfile(
            JustfileSpec(
                format_commands=self.manifest.tooling.just_format_commands,
                lint_commands=self.manifest.tooling.just_lint_commands,
                typecheck_commands=self.manifest.tooling.just_typecheck_commands,
                ci_flags=self.manifest.tooling.ci_flags,
                clean_paths=self.manifest.tooling.just_clean_paths,
            )
        )
        atomic_write_text(target, full_content)
        self.record_touch(target)

    # --- Architectural Note: AST-Preserving TOML Merging ---
    # Protostar uses `tomlkit` AST parsing rather than standard dictionary updates or tomllib/tomli.
    #
    # Rationale:
    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        if not self.manifest.filesystem.file_appends:
            return

        is_overwrite = self.manifest.collision_strategy == CollisionStrategy.OVERWRITE

        for filepath, contents in self.manifest.filesystem.file_appends.items():
            target = Path(filepath)
            enforce_path_jail(target, Path.cwd())

            try:
                original_content = target.read_text() if target.exists() else ""
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileSystemError(
                    "read target append context", str(target), e
                ) from e

            interpolated_payloads = [
                render_template(p, self.interpolation_context) for p in contents
            ]

            if target.suffix == ".toml":
                try:
                    new_content = merge_toml_payloads(
                        original_content=original_content,
                        payloads=interpolated_payloads,
                        is_pyproject=(target.name == "pyproject.toml"),
                        overwrite=is_overwrite,
                        on_conflict=lambda msg, sev: self.add_diagnostic(
                            phase=DiagnosticPhase.EXECUTOR,
                            message=msg,
                            severity=sev,
                        ),
                    )
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to parse injected TOML payload for {filepath}.\nDetails: {e}"
                    ) from e

                if new_content.strip() != original_content.strip():
                    try:
                        atomic_write_text(target, new_content)
                        self.record_touch(target)
                    except OSError as e:
                        raise FileSystemError(
                            "mutate configuration AST", str(target), e
                        ) from e
                    logger.debug(f"Updated configuration AST in {filepath}")
            else:
                appended_content = append_marker_blocks(
                    original_content=original_content,
                    payloads=interpolated_payloads,
                    filepath=target,
                    overwrite=is_overwrite,
                )
                if appended_content is not None:
                    try:
                        atomic_write_text(target, appended_content)
                        self.record_touch(target)
                    except OSError as e:
                        raise FileSystemError(
                            "append configurations block", str(target), e
                        ) from e
                    logger.debug(f"Updated configuration string block in {filepath}")

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.filesystem.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        enforce_path_jail(gitignore, Path.cwd())
        try:
            existing_content = gitignore.read_text() if gitignore.exists() else ""
            new_content = generate_gitignore(
                vcs_ignores=self.manifest.filesystem.vcs_ignores,
                existing_content=existing_content,
            )
            if new_content is not None:
                atomic_write_text(gitignore, new_content)
                self.record_touch(gitignore)
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

        dockerignore = Path(".dockerignore")
        enforce_path_jail(dockerignore, Path.cwd())
        try:
            existing_content = dockerignore.read_text() if dockerignore.exists() else ""
            has_uv_init = any(
                task.command[:2] == ["uv", "init"]
                for task in self.manifest.tasks.system_tasks
            )
            new_dockerignore = generate_dockerignore(
                vcs_ignores=self.manifest.filesystem.vcs_ignores,
                has_uv_init=has_uv_init,
                existing_content=existing_content,
            )
            if new_dockerignore is not None:
                atomic_write_text(dockerignore, new_dockerignore)
                self.record_touch(dockerignore)
                logger.debug(
                    "Scaffolded container runtime ignore configurations (.dockerignore)"
                )
        except OSError as e:
            raise FileSystemError(
                "scaffold container runtime ignore configurations",
                str(dockerignore),
                e,
            ) from e

        dockerfile = Path("Dockerfile")
        enforce_path_jail(dockerfile, Path.cwd())
        if self.manifest.should_skip_file(dockerfile):
            self.add_diagnostic(
                phase=DiagnosticPhase.DOCKER,
                message=f"Skipping {dockerfile.name} generation; file already exists.",
                severity=Severity.SKIP,
            )
            return

        try:
            context = self.interpolation_context
            is_script_or_typer = (
                "typer" in self.manifest.dependencies.dependencies
                or any(
                    "project.scripts" in app
                    for app in self.manifest.filesystem.file_appends.get(
                        "pyproject.toml", []
                    )
                )
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
            atomic_write_text(dockerfile, dockerfile_content)
            self.record_touch(dockerfile)
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
            on_record_touch=self.record_touch,
        )

    def _install_dependencies(self) -> None:
        """Installs queued dependencies using uv."""
        install_dependencies(
            dependencies_manifest=self.manifest.dependencies,
            on_diagnostic=lambda msg, sev, detail: self.add_diagnostic(
                phase=DiagnosticPhase.EXECUTOR,
                message=msg,
                severity=sev,
                detail=detail,
            ),
        )
