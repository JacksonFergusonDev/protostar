from __future__ import annotations

import enum
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

from .errors import ConfigurationError
from .intent import (
    AppendContribution,
    DependencyGroup,
    DependencyInclude,
    ResolverFootprint,
    StructuredContribution,
    StructuredFormat,
    TemplateReference,
    validate_region_id,
    validate_target,
)
from .interpolation import render_template
from .merge import MergeConflict
from .metadata import LicenseType
from .sync_state import FilePolicy
from .workflows import CIFlag, TargetOS
from .workflows import HookRunner as HookRunner
from .workspace import resolve_package_name, resolve_project_name

if TYPE_CHECKING:
    from .documents.locations import DocumentLocations
    from .recipe import ProducerContribution, ProjectRecipe, ToolSelection


def _ignore_contribution(path: tuple[str, ...]) -> None:
    """Ignores attribution when assembling a standalone manifest slice."""


class DiagnosticPhase(enum.StrEnum):
    """Enumeration of execution phases for diagnostic events."""

    CONFIG = "Config"
    DIRENV = "Direnv"
    IDE = "IDE"
    PRE_COMMIT = "Pre-commit"
    JUST = "Just"
    EXECUTOR = "Executor"
    DOCKER = "Docker"
    CI = "CI"


class Severity(enum.StrEnum):
    """Enumeration of severity levels for diagnostic events."""

    INFO = "info"
    SKIP = "skip"
    WARNING = "warning"


@dataclass(frozen=True)
class DiagnosticEvent:
    """A structured record of a non-fatal anomaly or skipped operation.

    Attributes:
        phase: The execution phase or module name (e.g., 'Config', 'Direnv').
        message: A concise description of the event.
        severity: The severity level of the event.
        detail: Optional extended diagnostic information.
        conflict: An open conflict, whose local content was kept.
        resolved: A conflict settled by a resolution.
    """

    phase: DiagnosticPhase | str
    message: str
    severity: Severity
    detail: str | None = None
    conflict: MergeConflict | None = None
    resolved: MergeConflict | None = None


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
        owned_files: list[str] | None = None,
        owned_trees: list[str] | None = None,
    ) -> None:
        self.command = command
        self.description = description
        self.timeout = timeout
        self.owned_files = owned_files or []
        self.owned_trees = owned_trees or []

    def to_dict(self) -> dict[str, Any]:
        """Serializes the task to a JSON-safe dictionary."""
        return {
            "command": self.command,
            "description": self.description,
            "timeout": self.timeout,
            "owned_files": self.owned_files,
            "owned_trees": self.owned_trees,
        }


class CollisionStrategy(enum.Enum):
    """Enumeration of execution routes for intersecting files."""

    MERGE = "merge"
    OVERWRITE = "overwrite"


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

    observe: Callable[[tuple[str, ...]], None] = field(
        default=_ignore_contribution, repr=False
    )

    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    docs_dependencies: list[str] = field(default_factory=list)
    includes: list[DependencyInclude] = field(default_factory=list)
    resolver_footprint: ResolverFootprint = field(default_factory=ResolverFootprint)

    def add_include(self, group: DependencyGroup, include: DependencyGroup) -> None:
        """Declares a supported dependency-group include without generic TOML."""
        self.observe(("includes", group.value, include.value))
        if (
            group not in (DependencyGroup.DEV, DependencyGroup.DOCS)
            or include not in (DependencyGroup.DEV, DependencyGroup.DOCS)
            or group == include
        ):
            raise ConfigurationError(
                "Unsupported dependency include edge.",
                hint="Include docs in dev or dev in docs without cycles.",
            )
        edge = DependencyInclude(group, include)
        if DependencyInclude(include, group) in self.includes:
            raise ConfigurationError(
                "Cyclic dependency includes.",
                hint="Remove the cyclic include-group declaration.",
            )
        if edge not in self.includes:
            self.includes.append(edge)

    def add(self, package: str) -> None:
        """Queues a dependency for installation, preventing duplicates."""
        self.observe(("dependencies", package))
        if package not in self.dependencies:
            self.dependencies.append(package)

    def add_dev(self, package: str) -> None:
        """Queues a development dependency for installation, preventing duplicates."""
        self.observe(("dev_dependencies", package))
        if package not in self.dev_dependencies:
            self.dev_dependencies.append(package)

    def add_docs(self, package: str) -> None:
        """Queues a documentation dependency for installation, preventing duplicates."""
        self.observe(("docs_dependencies", package))
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
            "includes": [
                e.to_dict()
                for e in sorted(self.includes, key=lambda e: (e.group, e.include))
            ],
            "resolver_footprint": self.resolver_footprint.to_dict(),
        }


@dataclass
class FilesystemManifest:
    """Domain slice managing local filesystem scaffolding and tracking."""

    observe: Callable[[tuple[str, ...]], None] = field(
        default=_ignore_contribution, repr=False
    )

    directories: set[str] = field(default_factory=set)
    file_injections: dict[str, str] = field(default_factory=dict)
    structured: dict[str, list[StructuredContribution]] = field(default_factory=dict)
    regions: dict[str, list[AppendContribution]] = field(default_factory=dict)
    vcs_ignores: set[str] = field(default_factory=set)
    workspace_hides: set[str] = field(default_factory=set)

    def add_directory(self, path: str) -> None:
        """Queues a relative directory path to be scaffolded."""
        self.observe(("directories", path))
        validate_target(path)
        self.directories.add(Path(path).as_posix())

    def add_file_injection(self, path: str, content: str) -> None:
        """Queues a file path and its string content to be written to disk.

        Args:
            path: Relative file path to create.
            content: File body string payload.

        Raises:
            ConfigurationError: If the path has already been registered with
                conflicting file content.
        """
        self.observe(("file_injections", path))
        validate_target(path)
        path = Path(path).as_posix()
        if path == "pyproject.toml":
            raise ConfigurationError(
                "Free-form pyproject.toml replacement is unsupported.",
                hint="Declare structured TOML contributions; tool.protostar is reserved.",
            )
        if path in self.structured or path in self.regions:
            raise ConfigurationError(
                f"Ambiguous contributions for '{path}'.",
                hint="Do not combine free-form files with structured configuration or regions.",
            )
        if path in self.file_injections and self.file_injections[path] != content:
            raise ConfigurationError(
                f"Conflicting file injections for '{path}': multiple sources registered different content.",
                hint="Check for conflicting module configurations or overlapping template definitions.",
            )
        self.file_injections[path] = content

    def add_structured(
        self,
        path: str,
        content: str,
        *,
        producer: str,
        document_format: StructuredFormat = StructuredFormat.TOML,
    ) -> None:
        """Declares explicit structured intent for a TOML or contributable YAML target."""
        self.observe(("structured", path, producer))
        from .documents.pyproject import declare_contribution

        validate_target(path)
        path = Path(path).as_posix()
        if path in self.file_injections or path in self.regions:
            raise ConfigurationError(
                f"Ambiguous contributions for '{path}'.",
                hint="Use one contribution policy per target.",
            )
        if document_format is StructuredFormat.YAML:
            from .documents import YAML_CONTRIBUTION_TARGETS
            from .yaml_ast import decode_yaml_baseline

            if path not in YAML_CONTRIBUTION_TARGETS:
                raise ConfigurationError(
                    "Unsupported structured YAML target.",
                    hint=f"Declare a contribution to one of: {', '.join(sorted(YAML_CONTRIBUTION_TARGETS))}.",
                )
            decode_yaml_baseline(content)
            if path in self.structured:
                raise ConfigurationError(
                    "Ambiguous YAML producers.",
                    hint=f"Declare one contribution to '{path}' per manifest.",
                )
            self.structured[path] = [
                StructuredContribution(producer, content, format=document_format)
            ]
            return
        if not path.endswith(".toml"):
            raise ConfigurationError(
                "Structured contributions require TOML targets.",
                hint="Use a named append region for non-TOML files.",
            )
        self.structured.setdefault(path, []).append(
            declare_contribution(path, content, producer)
        )

    def add_region(self, path: str, content: str, *, identity: str) -> None:
        """Declares one uniquely identified non-TOML text region."""
        self.observe(("regions", path, identity))
        validate_target(path)
        path = Path(path).as_posix()
        validate_region_id(identity)
        if path.endswith(".toml"):
            raise ConfigurationError(
                "TOML append regions are unsupported.",
                hint="Use dev.pyproject structured configuration.",
            )
        from .documents import yaml_spec

        if yaml_spec(path) is not None:
            raise ConfigurationError(
                f"Append regions are unsupported for '{path}'.",
                hint="Protostar merges this YAML file by structure; appended text cannot be merged.",
            )
        if path in self.file_injections or path in self.structured:
            raise ConfigurationError(
                f"Ambiguous contributions for '{path}'.",
                hint="Use one contribution policy per target.",
            )
        regions = self.regions.setdefault(path, [])
        if any(r.id == identity for r in regions):
            raise ConfigurationError(
                f"Duplicate append identity '{identity}' for '{path}'.",
                hint="Give every region a unique stable ID.",
            )
        regions.append(AppendContribution(identity, content))

    def add_vcs_ignore(self, path: str) -> None:
        """Appends a file or directory pattern to the VCS ignore list (.gitignore)."""
        self.observe(("vcs_ignores", path))
        self.vcs_ignores.add(path)

    def add_workspace_hide(self, path: str) -> None:
        """Appends a file or directory pattern to the IDE workspace exclusion list."""
        self.observe(("workspace_hides", path))
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
            "structured": {
                k: [c.to_dict() for c in self.structured[k]]
                for k in sorted(self.structured)
            },
            "regions": {
                k: [c.to_dict() for c in self.regions[k]] for k in sorted(self.regions)
            },
            "file_policy": FilePolicy.SEED.value,
            "vcs_ignores": sorted(self.vcs_ignores),
            "workspace_hides": sorted(self.workspace_hides),
        }


@dataclass
class ToolingManifest:
    """Domain slice managing tooling configuration and templating parameters."""

    observe: Callable[[tuple[str, ...]], None] = field(
        default=_ignore_contribution, repr=False
    )

    hook_runner: HookRunner = HookRunner.NONE
    pre_commit_hooks: list[str] = field(default_factory=list)
    pre_commit_local_hooks: list[str] = field(default_factory=list)
    pre_commit_install_hook_types: set[str] = field(default_factory=set)
    wants_ci: bool = False
    wants_release: bool = False
    wants_docker: bool = False
    ci_flags: set[CIFlag | str] = field(default_factory=set)
    ci_steps: list[str] = field(default_factory=list)
    wants_just: bool = False
    just_format_commands: list[str] = field(default_factory=list)
    just_lint_commands: list[str] = field(default_factory=list)
    just_typecheck_commands: list[str] = field(default_factory=list)
    just_clean_paths: list[str] = field(default_factory=list)
    wants_agents: bool = False
    ide_extensions: set[str | tuple[str, ...]] = field(default_factory=set)

    @property
    def wants_hooks(self) -> bool:
        """Returns True if a Git hook manager is configured."""
        return self.hook_runner != HookRunner.NONE

    def set_hook_runner(self, runner: HookRunner) -> None:
        """Sets the Git hook manager, enforcing mutual exclusivity."""
        self.observe(("hook_runner", runner.value))
        if self.hook_runner != HookRunner.NONE and self.hook_runner != runner:
            raise ConfigurationError(
                f"Cannot configure '{runner.value}' when '{self.hook_runner.value}' is already active.",
                hint="Choose either pre-commit or prek as your git hook manager.",
            )
        self.hook_runner = runner

    def add_pre_commit_hook(self, payload: str) -> None:
        """Appends a raw YAML payload to the pre-commit configuration."""
        self.observe(("pre_commit_hooks", hashlib.sha256(payload.encode()).hexdigest()))
        if payload not in self.pre_commit_hooks:
            self.pre_commit_hooks.append(payload)

    def add_pre_commit_local_hook(self, payload: str) -> None:
        """Appends a raw YAML hook payload to the local pre-commit toolchain configuration."""
        self.observe(
            ("pre_commit_local_hooks", hashlib.sha256(payload.encode()).hexdigest())
        )
        if payload not in self.pre_commit_local_hooks:
            self.pre_commit_local_hooks.append(payload)

    def add_pre_commit_hook_type(self, hook_type: str) -> None:
        """Declares a Git hook lifecycle type required by a tooling module (e.g. 'commit-msg')."""
        self.observe(("pre_commit_install_hook_types", hook_type))
        self.pre_commit_install_hook_types.add(hook_type)

    def add_ci_flag(self, key: CIFlag | str) -> None:
        """Adds a CI flag to trigger specialized executor generation logic."""
        self.observe(("ci_flags", str(key)))
        self.ci_flags.add(key)

    def add_ci_step(self, step_yaml: str) -> None:
        """Appends a raw YAML payload to the CI configuration."""
        self.observe(("ci_steps", hashlib.sha256(step_yaml.encode()).hexdigest()))
        if step_yaml not in self.ci_steps:
            self.ci_steps.append(step_yaml)

    def add_ide_extension(self, extension_id: str | tuple[str, ...]) -> None:
        """Queues an IDE extension ID (or fallback tuple) for verification during the realization phase."""
        self.observe(("ide_extensions", str(extension_id)))
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
            "hook_runner": self.hook_runner.value,
            "pre_commit_hooks": list(self.pre_commit_hooks),
            "pre_commit_local_hooks": list(self.pre_commit_local_hooks),
            "wants_ci": self.wants_ci,
            "wants_release": self.wants_release,
            "wants_docker": self.wants_docker,
            "ci_flags": sorted(
                f.value if isinstance(f, CIFlag) else str(f) for f in self.ci_flags
            ),
            "ci_steps": list(self.ci_steps),
            "wants_just": self.wants_just,
            "just_format_commands": list(self.just_format_commands),
            "just_lint_commands": list(self.just_lint_commands),
            "just_typecheck_commands": list(self.just_typecheck_commands),
            "just_clean_paths": list(self.just_clean_paths),
            "wants_agents": self.wants_agents,
            "ide_extensions": sorted(
                (_serialize_extension(ext) for ext in self.ide_extensions),
                key=lambda x: x[0] if isinstance(x, list) else x,
            ),
        }


@dataclass
class TaskManifest:
    """Domain slice managing shell command execution tasks."""

    observe: Callable[[tuple[str, ...]], None] = field(
        default=_ignore_contribution, repr=False
    )

    system_tasks: list[SystemTask] = field(default_factory=list)
    post_install_tasks: list[SystemTask] = field(default_factory=list)

    def add_system_task(
        self,
        command: list[str],
        timeout: int | None = 30,
        description: str | None = None,
        owned_files: list[str] | None = None,
        owned_trees: list[str] | None = None,
    ) -> None:
        """Queues a shell command for execution during the realization phase."""
        self.observe(
            ("system_tasks", hashlib.sha256("\0".join(command).encode()).hexdigest())
        )
        if any(task.command == command for task in self.system_tasks):
            return
        self.system_tasks.append(
            SystemTask(
                command=command,
                timeout=timeout,
                description=description,
                owned_files=owned_files,
                owned_trees=owned_trees,
            )
        )

    def add_post_install_task(
        self,
        command: list[str],
        timeout: int | None = 30,
        description: str | None = None,
        owned_files: list[str] | None = None,
        owned_trees: list[str] | None = None,
    ) -> None:
        """Queues a shell command for execution after dependencies are fully installed."""
        self.observe(
            (
                "post_install_tasks",
                hashlib.sha256("\0".join(command).encode()).hexdigest(),
            )
        )
        if any(task.command == command for task in self.post_install_tasks):
            return
        self.post_install_tasks.append(
            SystemTask(
                command=command,
                timeout=timeout,
                description=description,
                owned_files=owned_files,
                owned_trees=owned_trees,
            )
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
                "owned_files": task.owned_files,
                "owned_trees": task.owned_trees,
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

    producer_contributions: tuple[ProducerContribution, ...] = ()
    selections: tuple[ToolSelection, ...] = ()
    recipe: ProjectRecipe | None = None
    template_reference: TemplateReference | None = None
    dependencies: DependencyManifest = field(default_factory=DependencyManifest)
    filesystem: FilesystemManifest = field(default_factory=FilesystemManifest)
    tooling: ToolingManifest = field(default_factory=ToolingManifest)
    tasks: TaskManifest = field(default_factory=TaskManifest)

    metadata: ProjectMetadata = field(default_factory=lambda: cast(ProjectMetadata, {}))
    ide_settings: IDESettings = field(default_factory=lambda: cast(IDESettings, {}))
    collision_strategy: CollisionStrategy | None = CollisionStrategy.MERGE
    collisions: frozenset[Path] = frozenset()

    def add_ide_setting(self, key: IDESettingKey, value: Any) -> None:
        """Sets a key-value configuration for the requested IDE."""
        self.ide_settings[key] = value

    def document_locations(self, target: str) -> DocumentLocations:
        """Returns the paths the tool behind a planned document reads it from.

        Args:
            target: The document's canonical workspace path.

        Returns:
            The document's locations under this manifest's hook runner.
        """
        from .documents import document_locations

        return document_locations(target, self.tooling.hook_runner)

    def target_files(self) -> set[Path]:
        """Returns all concrete workspace file paths that this manifest intends to create or mutate.

        Excludes directory scaffolding (handled safely via ensure_directory) and
        .gitignore updates (deduplicated and non-destructive).

        Returns:
            A set of Path objects representing target files.
        """
        from .documents import github_workflows, pre_commit, pyproject

        targets: set[Path] = set()
        ctx = self._path_context()

        for filepath in self.filesystem.file_injections:
            rendered = render_template(filepath, ctx, escape_toml=False)
            targets.add(Path(rendered))

        for filepath in (
            self.filesystem.structured.keys() | self.filesystem.regions.keys()
        ):
            rendered = render_template(filepath, ctx, escape_toml=False)
            targets.add(Path(rendered))

        if self.dependencies.includes:
            targets.add(Path(pyproject.TARGET))

        if self.tooling.wants_hooks:
            targets.add(Path(pre_commit.TARGET))

        if self.tooling.wants_ci:
            targets.add(Path(github_workflows.CI_TARGET))

        if self.tooling.wants_release:
            targets.add(Path(github_workflows.RELEASE_TARGET))

        if self.tooling.wants_just:
            targets.add(Path("justfile"))

        if self.tooling.wants_docker:
            targets.add(Path("Dockerfile"))
            targets.add(Path(".dockerignore"))

        return targets

    def target_directories(self) -> set[Path]:
        """Returns the rendered workspace directories this manifest scaffolds.

        Returns:
            A set of Path objects representing target directories.
        """
        ctx = self._path_context()
        return {
            Path(render_template(path, ctx, escape_toml=False))
            for path in self.filesystem.directories
        }

    def written_files(self) -> set[Path]:
        """Returns every workspace file execution writes itself, for previews.

        Adds the append-only .gitignore and the IDE settings, which
        ``target_files`` leaves out because they never collide, to its targets.
        A document found under another name its tool reads is listed there.
        Engine state and subprocess output (such as ``uv.lock``) are excluded.

        Returns:
            A set of Path objects representing written files.
        """
        from .documents import vscode
        from .documents.locations import resolve_location

        files = self.target_files()
        if self.filesystem.vcs_ignores:
            files.add(Path(".gitignore"))
        if self.ide_settings:
            files.add(Path(vscode.SETTINGS_TARGET))
        return {
            Path(
                resolve_location(
                    self.document_locations(file.as_posix()),
                    (),
                    lambda path: Path(path).exists(),
                ).path
                or file
            )
            for file in files
        }

    def colliding_files(self) -> set[Path]:
        """Returns the existing workspace files this manifest would edit.

        A document counts under every name its tool reads it from that Protostar
        edits, so an existing alias is a collision like the canonical file.

        Returns:
            A set of Path objects that already exist.
        """
        return {
            Path(path)
            for file in self.target_files()
            for path in self.document_locations(file.as_posix()).editable
            if Path(path).exists()
        }

    def _path_context(self) -> dict[str, str]:
        """Returns the built-in names that render target paths."""
        if self.recipe:
            return dict(self.recipe.context)
        return {
            "PROJECT_NAME": resolve_project_name(self.metadata),
            "PACKAGE_NAME": resolve_package_name(self.metadata),
        }

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
            "template_reference": self.template_reference.to_dict()
            if self.template_reference
            else None,
            "collision_strategy": self.collision_strategy.value
            if self.collision_strategy
            else None,
            "collisions": sorted(path.as_posix() for path in self.collisions),
            "metadata": dict(self.metadata),
            "ide_settings": dict(self.ide_settings),
            "dependencies": self.dependencies.to_dict(),
            "filesystem": self.filesystem.to_dict(),
            "tooling": self.tooling.to_dict(),
            "tasks": self.tasks.to_dict(),
        }
