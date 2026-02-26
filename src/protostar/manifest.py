import dataclasses
from typing import Any


@dataclasses.dataclass
class EnvironmentManifest:
    """Centralized state object holding the aggregate environment requirements.

    Modules append to this manifest during the build phase. The orchestrator
    subsequently reads this object to execute the unified system changes.

    Attributes:
        ignored_paths (set[str]): Unique file/directory patterns for .gitignore.
        ide_settings (dict[str, Any]): Nested key-value pairs for IDE configurations.
        dependencies (list[str]): Packages to inject via the active package manager.
        system_tasks (list[list[str]]): Ordered queue of shell commands to execute.
    """

    ignored_paths: set[str] = dataclasses.field(default_factory=set)
    ide_settings: dict[str, Any] = dataclasses.field(default_factory=dict)
    dependencies: list[str] = dataclasses.field(default_factory=list)
    system_tasks: list[list[str]] = dataclasses.field(default_factory=list)

    def add_ignore(self, path: str) -> None:
        """Appends a file or directory pattern to the ignore list."""
        self.ignored_paths.add(path)

    def add_ide_setting(self, key: str, value: Any) -> None:
        """Sets a key-value configuration for the requested IDE."""
        self.ide_settings[key] = value

    def add_system_task(self, command: list[str]) -> None:
        """Queues a shell command to be executed (e.g., ['uv', 'init'])."""
        self.system_tasks.append(command)

    def add_dependency(self, package: str) -> None:
        """Queues a dependency for installation, preventing duplicates."""
        if package not in self.dependencies:
            self.dependencies.append(package)
