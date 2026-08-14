import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class Severity(enum.Enum):
    """Enumeration of severity levels for diagnostic events."""

    INFO = "info"
    SKIP = "skip"
    WARNING = "warning"


@dataclass
class DiagnosticEvent:
    """A structured record of a non-fatal anomaly or skipped operation.

    Attributes:
        phase: The execution phase or module name (e.g., 'Config', 'Direnv').
        message: A concise description of the event.
        severity: The severity level of the event.
        detail: Optional extended diagnostic information.
    """

    phase: str
    message: str
    severity: Severity = Severity.INFO
    detail: str | None = None


class CollisionStrategy(enum.Enum):
    """Enumeration of strategies for resolving state collisions during realization."""

    MERGE = "merge"
    OVERWRITE = "overwrite"
    ABORT = "abort"


@dataclass
class SystemTask:
    """A shell command with an associated execution timeout limit.

    Attributes:
        command: The command and its arguments as a list of strings.
        timeout: The maximum execution time in seconds, or None for no limit.
        description: An optional human-readable description for the terminal UI.
    """

    command: list[str]
    timeout: int | None = None
    description: str | None = None


@dataclass
class EnvironmentManifest:
    """Centralized state object holding the aggregate environment requirements.

    Modules append to this manifest during the build phase. The orchestrator
    subsequently reads this object to execute the unified system changes.

    Attributes:
        vcs_ignores (set[str]): Unique file/directory patterns for .gitignore.
        workspace_hides (set[str]): Unique file/directory patterns to hide in the IDE.
        ide_settings (dict[str, Any]): Nested key-value pairs for IDE configurations.
        dependencies (list[str]): Packages to inject via the active package manager.
        dev_dependencies (list[str]): Development packages to inject.
        system_tasks (list[SystemTask]): Ordered queue of shell commands to execute.
        post_install_tasks (list[SystemTask]): Ordered queue of shell commands to execute after dependencies are installed.
        directories (set[str]): Local directories to scaffold in the workspace.
        file_injections (dict[str, str]): Exact paths mapped to their raw file contents.
        file_appends (dict[str, list[str]]): Exact paths mapped to lists of content to append.
        wants_pre_commit (bool): Flag indicating if pre-commit hooks should be scaffolded.
        pre_commit_hooks (list[str]): Raw YAML payloads for the pre-commit config.
        metadata (dict[str, Any]): Resolved project metadata (e.g. minimum_python, supported_os).
        wants_ci (bool): Flag indicating if GitHub Actions CI workflow should be scaffolded.
        wants_release (bool): Flag indicating if GitHub Actions PyPI release workflow should be scaffolded.
        ci_flags (set[str]): Tooling flags indicating specific behavior to inject into the CI workflow.
        ci_steps (list[str]): Raw YAML payloads for individual CI steps.
        wants_just (bool): Flag indicating if a justfile should be scaffolded.
        just_format_commands (list[str]): Shell commands for the format recipe.
        just_lint_commands (list[str]): Shell commands for the lint recipe.
        just_typecheck_commands (list[str]): Shell commands for the typecheck recipe.
        just_clean_paths (list[str]): File/directory paths to remove in the clean recipe.
        collision_strategy (CollisionStrategy): The execution route for intersecting files.
    """

    vcs_ignores: set[str] = field(default_factory=set)
    workspace_hides: set[str] = field(default_factory=set)
    ide_settings: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    docs_dependencies: list[str] = field(default_factory=list)
    system_tasks: list[SystemTask] = field(default_factory=list)
    post_install_tasks: list[SystemTask] = field(default_factory=list)
    directories: set[str] = field(default_factory=set)
    file_injections: dict[str, str] = field(default_factory=dict)
    file_appends: dict[str, list[str]] = field(default_factory=dict)
    wants_pre_commit: bool = False
    wants_prek: bool = False
    pre_commit_hooks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    wants_ci: bool = False
    wants_release: bool = False
    ci_flags: set[str] = field(default_factory=set)
    ci_steps: list[str] = field(default_factory=list)
    wants_just: bool = False
    just_format_commands: list[str] = field(default_factory=list)
    just_lint_commands: list[str] = field(default_factory=list)
    just_typecheck_commands: list[str] = field(default_factory=list)
    just_clean_paths: list[str] = field(default_factory=list)
    ide_extensions: set[str | tuple[str, ...]] = field(default_factory=set)
    collision_strategy: CollisionStrategy = CollisionStrategy.MERGE
    diagnostics: list[DiagnosticEvent] = field(default_factory=list)

    def add_ide_extension(self, extension_id: str | tuple[str, ...]) -> None:
        """Queues an IDE extension ID (or fallback tuple) for verification during the realization phase."""
        self.ide_extensions.add(extension_id)

    def add_vcs_ignore(self, path: str) -> None:
        """Appends a file or directory pattern to the VCS ignore list (.gitignore)."""
        self.vcs_ignores.add(path)

    def add_workspace_hide(self, path: str) -> None:
        """Appends a file or directory pattern to the IDE workspace exclusion list."""
        self.workspace_hides.add(path)

    def add_environment_artifact(self, path: str) -> None:
        """Appends a file or directory pattern to both the VCS ignore and IDE exclusion lists.

        Args:
            path: The unique file or directory pattern to hide and ignore.
        """
        self.add_vcs_ignore(path)
        self.add_workspace_hide(path)

    def add_ide_setting(self, key: str, value: Any) -> None:
        """Sets a key-value configuration for the requested IDE."""
        self.ide_settings[key] = value

    def add_system_task(
        self,
        command: list[str],
        timeout: int | None = 30,
        description: str | None = None,
    ) -> None:
        """Queues a shell command for execution during the realization phase.

        Args:
            command: The command and its arguments to execute.
            timeout: The maximum allowed execution time in seconds. Defaults to 30.
            description: An optional human-readable description for the terminal UI.
        """
        if any(task.command == command for task in self.system_tasks):
            return
        self.system_tasks.append(
            SystemTask(command=command, timeout=timeout, description=description)
        )

    def add_post_install_task(
        self,
        command: list[str],
        timeout: int | None = 30,
        description: str | None = None,
    ) -> None:
        """Queues a shell command for execution after dependencies are fully installed.

        Args:
            command: The command and its arguments to execute.
            timeout: The maximum allowed execution time in seconds. Defaults to 30.
            description: An optional human-readable description for the terminal UI.
        """
        if any(task.command == command for task in self.post_install_tasks):
            return
        self.post_install_tasks.append(
            SystemTask(command=command, timeout=timeout, description=description)
        )

    def add_dependency(self, package: str) -> None:
        """Queues a dependency for installation, preventing duplicates."""
        if package not in self.dependencies:
            self.dependencies.append(package)

    def add_dev_dependency(self, package: str) -> None:
        """Queues a development dependency for installation, preventing duplicates."""
        if package not in self.dev_dependencies:
            self.dev_dependencies.append(package)

    def add_docs_dependency(self, package: str) -> None:
        """Queues a documentation dependency for installation, preventing duplicates."""
        if package not in self.docs_dependencies:
            self.docs_dependencies.append(package)

    def add_directory(self, path: str) -> None:
        """Queues a relative directory path to be scaffolded."""
        self.directories.add(path)

    def add_file_injection(self, path: str, content: str) -> None:
        """Queues a file path and its string content to be written to disk."""
        if path not in self.file_injections:
            self.file_injections[path] = content

    def add_file_append(self, path: str, content: str) -> None:
        """Queues a string payload to be appended to a file during late-binding."""
        if path not in self.file_appends:
            self.file_appends[path] = []
        self.file_appends[path].append(content)

    def add_pre_commit_hook(self, payload: str) -> None:
        """Appends a raw YAML payload to the pre-commit configuration."""
        if payload not in self.pre_commit_hooks:
            self.pre_commit_hooks.append(payload)

    def add_ci_flag(self, key: str) -> None:
        """Adds a CI flag to trigger specialized executor generation logic."""
        self.ci_flags.add(key)

    def add_ci_step(self, step_yaml: str) -> None:
        """Appends a raw YAML payload to the CI configuration."""
        if step_yaml not in self.ci_steps:
            self.ci_steps.append(step_yaml)

    def add_diagnostic(
        self,
        phase: str,
        message: str,
        severity: Severity = Severity.INFO,
        detail: str | None = None,
    ) -> None:
        """Queues a diagnostic event for the post-execution summary panel.

        Args:
            phase: The execution phase or module generating the event.
            message: A concise description of the skipped operation or anomaly.
            severity: The severity level of the event. Defaults to INFO.
            detail: Optional extended diagnostic information.
        """
        self.diagnostics.append(
            DiagnosticEvent(
                phase=phase, message=message, severity=severity, detail=detail
            )
        )

    def should_skip_file(self, target: Path, phase: str) -> bool:
        """Returns True if the file exists and collision strategy is not OVERWRITE, logging a SKIP event."""
        if target.exists() and self.collision_strategy != CollisionStrategy.OVERWRITE:
            self.add_diagnostic(
                phase=phase,
                message=f"Skipping {target.name} generation; file already exists.",
                severity=Severity.SKIP,
            )
            return True
        return False
