import dataclasses
import enum
from typing import Any


class CollisionStrategy(enum.Enum):
    """Enumeration of strategies for resolving state collisions during realization."""

    MERGE = "merge"
    OVERWRITE = "overwrite"
    ABORT = "abort"


@dataclasses.dataclass
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
        system_tasks (list[list[str]]): Ordered queue of shell commands to execute.
        directories (set[str]): Local directories to scaffold in the workspace.
        file_injections (dict[str, str]): Exact paths mapped to their raw file contents.
        file_appends (dict[str, list[str]]): Exact paths mapped to lists of content to append.
        wants_pre_commit (bool): Flag indicating if pre-commit hooks should be scaffolded.
        pre_commit_hooks (list[str]): Raw YAML payloads for the pre-commit config.
        collision_strategy (CollisionStrategy): The execution route for intersecting files.
    """

    vcs_ignores: set[str] = dataclasses.field(default_factory=set)
    workspace_hides: set[str] = dataclasses.field(default_factory=set)
    ide_settings: dict[str, Any] = dataclasses.field(default_factory=dict)
    dependencies: list[str] = dataclasses.field(default_factory=list)
    dev_dependencies: list[str] = dataclasses.field(default_factory=list)
    system_tasks: list[list[str]] = dataclasses.field(default_factory=list)
    directories: set[str] = dataclasses.field(default_factory=set)
    file_injections: dict[str, str] = dataclasses.field(default_factory=dict)
    file_appends: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    wants_pre_commit: bool = False
    pre_commit_hooks: list[str] = dataclasses.field(default_factory=list)
    collision_strategy: CollisionStrategy = CollisionStrategy.MERGE

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

    def add_system_task(self, command: list[str]) -> None:
        """Queues a shell command for execution during the realization phase."""
        self.system_tasks.append(command)

    def add_dependency(self, package: str) -> None:
        """Queues a dependency for installation, preventing duplicates."""
        if package not in self.dependencies:
            self.dependencies.append(package)

    def add_dev_dependency(self, package: str) -> None:
        """Queues a development dependency for installation, preventing duplicates."""
        if package not in self.dev_dependencies:
            self.dev_dependencies.append(package)

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
        """Queues a YAML payload block for the .pre-commit-config.yaml file."""
        if payload not in self.pre_commit_hooks:
            self.pre_commit_hooks.append(payload)
