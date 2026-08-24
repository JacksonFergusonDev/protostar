import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from .metadata import LicenseType
from .workflows import CIFlag, TargetOS


class DiagnosticPhase(enum.StrEnum):
    """Enumeration of execution phases for diagnostic telemetry events."""

    CONFIG = "Config"
    DIRENV = "Direnv"
    IDE = "IDE"
    PRE_COMMIT = "Pre-commit"
    JUST = "Just"
    EXECUTOR = "Executor"
    DOCKER = "Docker"


class Severity(enum.StrEnum):
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

    phase: DiagnosticPhase | str
    message: str
    severity: Severity
    detail: str | None = None


class SystemTask:
    """A deferred shell command execution directive.

    Attributes:
        command: A list of strings representing the command and its arguments.
        description: An optional human-readable message to display during execution.
        timeout: An optional maximum execution time in seconds.
    """

    def __init__(
        self,
        command: list[str],
        description: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.command = command
        self.description = description
        self.timeout = timeout


class CollisionStrategy(enum.Enum):
    """Enumeration of execution routes for intersecting files."""

    MERGE = "merge"
    OVERWRITE = "overwrite"
    ABORT = "abort"


class ProjectMetadata(TypedDict, total=False):
    """Strict typing for project metadata fields."""

    description: str
    license: LicenseType | str
    author_name: str
    author_email: str
    github_username: str
    minimum_python: str
    supported_os: list[TargetOS | str]
    docker_port: int | str


IDESettings = TypedDict(
    "IDESettings",
    {
        "python.defaultInterpreterPath": str,
        "python.terminal.activateEnvironment": bool,
    },
    total=False,
)

IDESettingKey = Literal[
    "python.defaultInterpreterPath",
    "python.terminal.activateEnvironment",
]


@dataclass
class DependencyManifest:
    """Domain slice managing environment dependencies."""

    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    docs_dependencies: list[str] = field(default_factory=list)

    def add(self, package: str) -> None:
        """Queues a dependency for installation, preventing duplicates."""
        if package not in self.dependencies:
            self.dependencies.append(package)

    def add_dev(self, package: str) -> None:
        """Queues a development dependency for installation, preventing duplicates."""
        if package not in self.dev_dependencies:
            self.dev_dependencies.append(package)

    def add_docs(self, package: str) -> None:
        """Queues a documentation dependency for installation, preventing duplicates."""
        if package not in self.docs_dependencies:
            self.docs_dependencies.append(package)


@dataclass
class FilesystemManifest:
    """Domain slice managing local filesystem scaffolding and tracking."""

    directories: set[str] = field(default_factory=set)
    file_injections: dict[str, str] = field(default_factory=dict)
    file_appends: dict[str, list[str]] = field(default_factory=dict)
    vcs_ignores: set[str] = field(default_factory=set)
    workspace_hides: set[str] = field(default_factory=set)

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

    def add_vcs_ignore(self, path: str) -> None:
        """Appends a file or directory pattern to the VCS ignore list (.gitignore)."""
        self.vcs_ignores.add(path)

    def add_workspace_hide(self, path: str) -> None:
        """Appends a file or directory pattern to the IDE workspace exclusion list."""
        self.workspace_hides.add(path)

    def add_environment_artifact(self, path: str) -> None:
        """Appends a file or directory pattern to both the VCS ignore and IDE exclusion lists."""
        self.add_vcs_ignore(path)
        self.add_workspace_hide(path)


@dataclass
class ToolingManifest:
    """Domain slice managing tooling configuration and templating parameters."""

    wants_pre_commit: bool = False
    wants_prek: bool = False
    pre_commit_hooks: list[str] = field(default_factory=list)
    pre_commit_local_hooks: list[str] = field(default_factory=list)
    wants_ci: bool = False
    wants_release: bool = False
    ci_flags: set[CIFlag | str] = field(default_factory=set)
    ci_steps: list[str] = field(default_factory=list)
    wants_just: bool = False
    just_format_commands: list[str] = field(default_factory=list)
    just_lint_commands: list[str] = field(default_factory=list)
    just_typecheck_commands: list[str] = field(default_factory=list)
    just_clean_paths: list[str] = field(default_factory=list)
    ide_extensions: set[str | tuple[str, ...]] = field(default_factory=set)

    def add_pre_commit_hook(self, payload: str) -> None:
        """Appends a raw YAML payload to the pre-commit configuration."""
        if payload not in self.pre_commit_hooks:
            self.pre_commit_hooks.append(payload)

    def add_pre_commit_local_hook(self, payload: str) -> None:
        """Appends a raw YAML hook payload to the local pre-commit toolchain configuration."""
        if payload not in self.pre_commit_local_hooks:
            self.pre_commit_local_hooks.append(payload)

    def add_ci_flag(self, key: CIFlag | str) -> None:
        """Adds a CI flag to trigger specialized executor generation logic."""
        self.ci_flags.add(key)

    def add_ci_step(self, step_yaml: str) -> None:
        """Appends a raw YAML payload to the CI configuration."""
        if step_yaml not in self.ci_steps:
            self.ci_steps.append(step_yaml)

    def add_ide_extension(self, extension_id: str | tuple[str, ...]) -> None:
        """Queues an IDE extension ID (or fallback tuple) for verification during the realization phase."""
        self.ide_extensions.add(extension_id)


@dataclass
class TaskManifest:
    """Domain slice managing shell command execution tasks."""

    system_tasks: list[SystemTask] = field(default_factory=list)
    post_install_tasks: list[SystemTask] = field(default_factory=list)

    def add_system_task(
        self,
        command: list[str],
        timeout: int | None = 30,
        description: str | None = None,
    ) -> None:
        """Queues a shell command for execution during the realization phase."""
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
        """Queues a shell command for execution after dependencies are fully installed."""
        if any(task.command == command for task in self.post_install_tasks):
            return
        self.post_install_tasks.append(
            SystemTask(command=command, timeout=timeout, description=description)
        )


@dataclass
class EnvironmentManifest:
    """The materialized build state of the target environment.

    Modules mutate this declarative object rather than the host system directly. The Executor
    subsequently reads this object to execute the unified system changes.
    """

    dependencies: DependencyManifest = field(default_factory=DependencyManifest)
    filesystem: FilesystemManifest = field(default_factory=FilesystemManifest)
    tooling: ToolingManifest = field(default_factory=ToolingManifest)
    tasks: TaskManifest = field(default_factory=TaskManifest)

    metadata: ProjectMetadata = field(default_factory=lambda: cast(ProjectMetadata, {}))
    ide_settings: IDESettings = field(default_factory=lambda: cast(IDESettings, {}))
    collision_strategy: CollisionStrategy = CollisionStrategy.MERGE
    force_merge: bool = False
    force_replace: bool = False

    def add_ide_setting(self, key: IDESettingKey, value: Any) -> None:
        """Sets a key-value configuration for the requested IDE."""
        self.ide_settings[key] = value

    def should_skip_file(self, target: Path) -> bool:
        """Returns True if the file exists and collision strategy is not OVERWRITE."""
        return (
            target.exists() and self.collision_strategy != CollisionStrategy.OVERWRITE
        )
