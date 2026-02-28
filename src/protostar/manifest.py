import dataclasses
from typing import Any


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
        system_tasks (list[list[str]]): Ordered queue of shell commands to execute.
        directories (set[str]): Local directories to scaffold in the workspace.
        file_injections (dict[str, str]): Exact paths mapped to their raw file contents.
    """

    vcs_ignores: set[str] = dataclasses.field(default_factory=set)
    workspace_hides: set[str] = dataclasses.field(default_factory=set)
    ide_settings: dict[str, Any] = dataclasses.field(default_factory=dict)
    dependencies: list[str] = dataclasses.field(default_factory=list)
    system_tasks: list[list[str]] = dataclasses.field(default_factory=list)
    directories: set[str] = dataclasses.field(default_factory=set)
    file_injections: dict[str, str] = dataclasses.field(default_factory=dict)

    def add_vcs_ignore(self, path: str) -> None:
        """Appends a file or directory pattern to the VCS ignore list (.gitignore)."""
        self.vcs_ignores.add(path)

    def add_workspace_hide(self, path: str) -> None:
        """Appends a file or directory pattern to the IDE workspace exclusion list."""
        self.workspace_hides.add(path)

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

    def add_directory(self, path: str) -> None:
        """Queues a relative directory path to be scaffolded."""
        self.directories.add(path)

    def add_file_injection(self, path: str, content: str) -> None:
        """Queues a file path and its string content to be written to disk."""
        if path not in self.file_injections:
            self.file_injections[path] = content
