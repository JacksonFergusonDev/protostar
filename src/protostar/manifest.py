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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the dependency manifest to a JSON-safe dictionary.

        Ordered lists (dependencies, dev_dependencies, docs_dependencies) preserve
        their semantic insertion order so agents can reason about dependency intent.

        Returns:
            A JSON-serializable dictionary representation.
        """
        return {
            "dependencies": list(self.dependencies),
            "dev_dependencies": list(self.dev_dependencies),
            "docs_dependencies": list(self.docs_dependencies),
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the filesystem manifest to a JSON-safe dictionary.

        Set-backed fields (directories, vcs_ignores, workspace_hides) are emitted as
        sorted lists for deterministic output. Dict-backed fields preserve their
        insertion-ordered structure.

        Returns:
            A JSON-serializable dictionary representation.
        """
        return {
            "directories": sorted(self.directories),
            "file_injections": dict(self.file_injections),
            "file_appends": {k: list(v) for k, v in self.file_appends.items()},
            "vcs_ignores": sorted(self.vcs_ignores),
            "workspace_hides": sorted(self.workspace_hides),
        }


@dataclass
class ToolingManifest:
    """Domain slice managing tooling configuration and templating parameters."""

    wants_pre_commit: bool = False
    wants_prek: bool = False
    pre_commit_hooks: list[str] = field(default_factory=list)
    pre_commit_local_hooks: list[str] = field(default_factory=list)
    pre_commit_install_hook_types: set[str] = field(default_factory=set)
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

    def add_pre_commit_hook_type(self, hook_type: str) -> None:
        """Declares a Git hook lifecycle type required by a tooling module (e.g. 'commit-msg')."""
        self.pre_commit_install_hook_types.add(hook_type)

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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the tooling manifest to a JSON-safe dictionary.

        Set-backed fields (ci_flags, ide_extensions) are emitted as sorted lists.
        Enum values are coerced to their string representation. IDE extension tuples
        are converted to lists for JSON compatibility.

        Returns:
            A JSON-serializable dictionary representation.
        """

        def _serialize_extension(ext: str | tuple[str, ...]) -> str | list[str]:
            return list(ext) if isinstance(ext, tuple) else ext

        return {
            "wants_pre_commit": self.wants_pre_commit,
            "wants_prek": self.wants_prek,
            "pre_commit_hooks": list(self.pre_commit_hooks),
            "pre_commit_local_hooks": list(self.pre_commit_local_hooks),
            "wants_ci": self.wants_ci,
            "wants_release": self.wants_release,
            "ci_flags": sorted(
                f.value if isinstance(f, CIFlag) else str(f) for f in self.ci_flags
            ),
            "ci_steps": list(self.ci_steps),
            "wants_just": self.wants_just,
            "just_format_commands": list(self.just_format_commands),
            "just_lint_commands": list(self.just_lint_commands),
            "just_typecheck_commands": list(self.just_typecheck_commands),
            "just_clean_paths": list(self.just_clean_paths),
            "ide_extensions": sorted(
                (_serialize_extension(ext) for ext in self.ide_extensions),
                key=lambda x: x[0] if isinstance(x, list) else x,
            ),
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the task manifest to a JSON-safe dictionary.

        SystemTask objects are emitted as explicit dicts with ``command``,
        ``description``, and ``timeout`` keys so agents can evaluate the exact
        shell commands that would be executed.

        Returns:
            A JSON-serializable dictionary representation.
        """

        def _task_to_dict(task: SystemTask) -> dict[str, object]:
            return {
                "command": task.command,
                "description": task.description,
                "timeout": task.timeout,
            }

        return {
            "system_tasks": [_task_to_dict(t) for t in self.system_tasks],
            "post_install_tasks": [_task_to_dict(t) for t in self.post_install_tasks],
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the full environment manifest to a JSON-safe dictionary.

        Delegates serialization to each sub-manifest's ``to_dict()`` method and
        coerces top-level scalar fields to JSON-safe types. The collision_strategy
        enum is emitted as its string value. Metadata and IDE settings are included
        as-is since they are already dict-typed.

        Returns:
            A JSON-serializable dictionary representation of the full manifest.
        """
        return {
            "collision_strategy": self.collision_strategy.value,
            "force_merge": self.force_merge,
            "force_replace": self.force_replace,
            "metadata": dict(self.metadata),
            "ide_settings": dict(self.ide_settings),
            "dependencies": self.dependencies.to_dict(),
            "filesystem": self.filesystem.to_dict(),
            "tooling": self.tooling.to_dict(),
            "tasks": self.tasks.to_dict(),
        }
