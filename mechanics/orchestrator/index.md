# The Orchestrator

The `Orchestrator` operates as the primary deterministic state machine for Protostar. It is responsible for bridging the gap between declarative module configurations and imperative disk/shell mutations, ensuring the local filesystem is manipulated safely and predictably.

To guarantee idempotency and prevent partial initialization states (e.g., half-written configuration files following a pre-flight failure), the Orchestrator enforces a strict, multi-phase execution topology.

______________________________________________________________________

## Execution Lifecycle & Topology

The `Orchestrator` enforces a strict separation between read-only state aggregation and physical side effects (the [Engine Bulkhead](../../design-principles/#engine-bulkhead)). The core engine is purely headless: it ingests caller intent via an `InitRequest`, calculates the complete environment manifest via `plan()`, and mutates the workspace via `execute()`, returning an immutable `ExecutionResult`.

All terminal interaction (collision prompts, remote trust confirmations, progress spinners) is isolated in the CLI presentation layer (`cli.py`).

```
flowchart TD
    classDef boundary fill:#0f172a,stroke:#38bdf8,stroke-width:1px,color:#e2e8f0;
    classDef phase fill:#1e293b,stroke:#1e293b,stroke:#00e5ff,stroke-width:2px,color:#fff;
    classDef state fill:#334155,stroke:#7c4dff,stroke-width:2px,color:#fff;
    classDef error fill:#7f1d1d,stroke:#f87171,stroke-width:1px,color:#fff;
    classDef success fill:#14532d,stroke:#4ade80,stroke-width:1px,color:#fff;

    Req([InitRequest]):::boundary --> Plan["Phase 1: plan()<br/>• Workspace collision checks<br/>• Pre-flight binary verification<br/>• Manifest aggregation"]:::phase

    Plan -->|Validation Failure| Err["Raise ProtostarError<br/>(Caught by CLI Presentation Layer)"]:::error
    Plan -->|Plan Validated| Manifest[(EnvironmentManifest)]:::state

    Manifest -->|--dry-run / --json| DryRun([Serialize Manifest / Dry Run]):::boundary
    Manifest -->|Live Execution| Exec["Phase 2: execute()<br/>• Validate & deep-merge ASTs<br/>• Scaffold directories & inject files<br/>• Execute managed subprocesses"]:::phase

    Exec --> Result([ExecutionResult]):::success
```

______________________________________________________________________

## The Lifecycle Phases

The `plan()` phase calculates the target state without performing disk mutations:

- **Collision Check:** Scans the workspace for existing configuration markers (e.g., `pyproject.toml`). If collisions exist and no force flag is active, raises `WorkspaceCollisionError(paths=...)`.
- **Pre-Flight Verification:** Runs `pre_flight()` across all loaded modules to assert that required binaries (`uv`, `git`, etc.) exist in `$PATH`.
- **Manifest Aggregation:** Evaluates language, tooling, and preset modules to populate an `EnvironmentManifest` with file injections, AST merge payloads, ignore patterns, and system tasks.

When `WorkspaceCollisionError` or untrusted external templates are encountered:

- **Interactive TUI:** In interactive terminals, `cli.py` prompts you to `Merge`, `Overwrite`, or `Abort`. If authorized, it generates a fresh `InitRequest` with updated force flags and calls `plan()` again.
- **Headless Contexts:** In non-interactive environments (CI/CD), `cli.py` aborts safely with an error message instructing you to supply `--force-merge` or `--force-replace`.

The `execute()` phase hands the calculated manifest to `SystemExecutor` to apply all side effects in a deterministic sequence:

1. Validates existing TOML files for syntax errors.
1. Creates directories and injects base files.
1. Modifies configurations via AST deep-merging.
1. Writes deduplicated ignore files and Docker artifacts.
1. Writes local IDE settings.
1. Executes sequential subprocesses (package resolution, git hooks).

Interrupting this phase via `KeyboardInterrupt` raises `PartialExecutionAbortedError`, recording all paths modified so far.

______________________________________________________________________

## Telemetry & Diagnostics

During planning and execution, non-fatal skips and warnings (e.g., missing optional binaries like `direnv` or skipped optional tasks) are recorded into `ExecutionResult.diagnostics`. The CLI presentation layer renders these events in a structured summary panel upon completion:

For unexpected internal exceptions or AST parsing failures, the runtime traps errors at the CLI boundary to generate pre-filled GitHub crash reports without corrupting the workspace. For complete details on the exception hierarchy, POSIX exit code mappings, and crash issue generation, see the [Error Handling Architecture](.././error_handling/#crash-diagnostics-and-telemetry).

______________________________________________________________________

## API Reference

Caller Intent: `InitRequest`

## protostar.models.InitRequest `dataclass`

Declarative intent from the caller for a scaffolding run.

Attributes:

| Name                 | Type                | Description                                                           |
| -------------------- | ------------------- | --------------------------------------------------------------------- |
| `template_blueprint` | \`TemplateBlueprint | None\`                                                                |
| `python_version`     | \`str               | None\`                                                                |
| `docker`             | `bool`              | If True, scaffolds container artifacts (.dockerignore, Dockerfile).   |
| `force_merge`        | `bool`              | If True, bypasses collision prompts and forces a merge strategy.      |
| `force_replace`      | `bool`              | If True, bypasses collision prompts and forces an overwrite strategy. |
| `metadata`           | \`dict[str, Any]    | None\`                                                                |
| `is_external`        | `bool`              | If True, the template was loaded from an external (untrusted) source. |
| `is_user_aliased`    | `bool`              | If True, the template was resolved via a trusted global config alias. |

Source code in `src/protostar/models.py`

```python
@dataclass
class InitRequest:
    """Declarative intent from the caller for a scaffolding run.

    Attributes:
        template_blueprint: An optional pre-loaded template blueprint to apply.
        python_version: An optional Python version string (e.g. '3.13'). Informational;
            the modules list is already constructed with the resolved version.
        docker: If True, scaffolds container artifacts (.dockerignore, Dockerfile).
        force_merge: If True, bypasses collision prompts and forces a merge strategy.
        force_replace: If True, bypasses collision prompts and forces an overwrite strategy.
        metadata: Pre-resolved metadata dictionary to inject into the manifest.
        is_external: If True, the template was loaded from an external (untrusted) source.
        is_user_aliased: If True, the template was resolved via a trusted global config alias.
    """

    template_blueprint: TemplateBlueprint | None = None
    python_version: str | None = None
    docker: bool = False
    force_merge: bool = False
    force_replace: bool = False
    metadata: dict[str, Any] | None = field(default=None)
    is_external: bool = False
    is_user_aliased: bool = False
```

Execution Outcome: `ExecutionResult`

## protostar.models.ExecutionResult `dataclass`

Observed outcome returned by Orchestrator.execute().

Attributes:

| Name            | Type                          | Description                                                            |
| --------------- | ----------------------------- | ---------------------------------------------------------------------- |
| `touched_paths` | `frozenset[str]`              | Immutable set of relative paths written or created on disk.            |
| `diagnostics`   | `tuple[DiagnosticEvent, ...]` | Ordered tuple of non-fatal diagnostic events emitted during execution. |

Source code in `src/protostar/models.py`

```python
@dataclass(frozen=True)
class ExecutionResult:
    """Observed outcome returned by Orchestrator.execute().

    Attributes:
        touched_paths: Immutable set of relative paths written or created on disk.
        diagnostics: Ordered tuple of non-fatal diagnostic events emitted during execution.
    """

    touched_paths: frozenset[str]
    diagnostics: tuple[DiagnosticEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serializes the execution result to a JSON-safe dictionary.

        The ``touched_paths`` frozenset is emitted as a sorted list for deterministic
        output. Each diagnostic event is emitted as an explicit dict; the optional
        ``detail`` field is omitted when absent to keep payloads compact.

        Returns:
            A JSON-serializable dictionary representation.
        """
        diagnostics: list[dict[str, Any]] = []
        for event in self.diagnostics:
            entry: dict[str, Any] = {
                "phase": str(event.phase),
                "message": event.message,
                "severity": event.severity.value,
            }
            if event.detail is not None:
                entry["detail"] = event.detail
            diagnostics.append(entry)

        return {
            "touched_paths": sorted(self.touched_paths),
            "diagnostics": diagnostics,
        }
```

### to_dict

```python
to_dict()
```

Serializes the execution result to a JSON-safe dictionary.

The `touched_paths` frozenset is emitted as a sorted list for deterministic output. Each diagnostic event is emitted as an explicit dict; the optional `detail` field is omitted when absent to keep payloads compact.

Returns:

| Type             | Description                                    |
| ---------------- | ---------------------------------------------- |
| `dict[str, Any]` | A JSON-serializable dictionary representation. |

Source code in `src/protostar/models.py`

```python
def to_dict(self) -> dict[str, Any]:
    """Serializes the execution result to a JSON-safe dictionary.

    The ``touched_paths`` frozenset is emitted as a sorted list for deterministic
    output. Each diagnostic event is emitted as an explicit dict; the optional
    ``detail`` field is omitted when absent to keep payloads compact.

    Returns:
        A JSON-serializable dictionary representation.
    """
    diagnostics: list[dict[str, Any]] = []
    for event in self.diagnostics:
        entry: dict[str, Any] = {
            "phase": str(event.phase),
            "message": event.message,
            "severity": event.severity.value,
        }
        if event.detail is not None:
            entry["detail"] = event.detail
        diagnostics.append(entry)

    return {
        "touched_paths": sorted(self.touched_paths),
        "diagnostics": diagnostics,
    }
```

Core Interface: `Orchestrator`

## protostar.orchestrator.Orchestrator

Manages the lifecycle of the Python environment scaffolding process.

The orchestrator provides a strict two-phase API:

- plan(): Evaluates the workspace state and assembles a declarative EnvironmentManifest without mutating the filesystem.
- execute(): Takes an already-built manifest and realizes it on disk.

This separation guarantees that plan() is always safe to retry (it instantiates a fresh manifest on every call), and that execute() never performs planning, collision detection, or user interaction.

Source code in `src/protostar/orchestrator.py`

```python
class Orchestrator:
    """Manages the lifecycle of the Python environment scaffolding process.

    The orchestrator provides a strict two-phase API:
    - plan(): Evaluates the workspace state and assembles a declarative
      EnvironmentManifest without mutating the filesystem.
    - execute(): Takes an already-built manifest and realizes it on disk.

    This separation guarantees that plan() is always safe to retry (it
    instantiates a fresh manifest on every call), and that execute() never
    performs planning, collision detection, or user interaction.
    """

    def __init__(
        self,
        modules: list[BootstrapModule],
        user_config: UserConfig,
        request: InitRequest | None = None,
    ) -> None:
        """Initializes the orchestrator with the requested modules and intent.

        Args:
            modules: The ordered stack of bootstrap layers to apply.
            user_config: The active UserConfig instance.
            request: Optional InitRequest describing caller intent. Defaults to a
                no-op InitRequest if omitted.
        """
        self.modules = modules
        self.user_config = user_config
        self.request = request or InitRequest()

    def plan(self) -> EnvironmentManifest:
        """Evaluates workspace state and assembles a declarative EnvironmentManifest.

        A fresh EnvironmentManifest is instantiated on every call, guaranteeing
        that retries (e.g. after a collision resolution) start from a clean slate.

        Raises:
            WorkspaceCollisionError: If collision markers exist on disk and no
                force flag (force_merge / force_replace) was provided in the request.
            MissingDependencyError: If a module pre-flight check fails.

        Returns:
            A populated EnvironmentManifest ready to be passed to execute().
        """
        req = self.request

        # Phase 1: Instantiate a fresh manifest for every plan() call
        manifest = EnvironmentManifest(
            force_merge=req.force_merge,
            force_replace=req.force_replace,
        )

        # Phase 2: Collision intercept (raises instead of prompting)
        collision_targets: set[Path] = set()
        for mod in self.modules:
            for marker in mod.collision_markers:
                if marker.exists():
                    collision_targets.add(marker)

        if collision_targets:
            if req.force_replace:
                logger.debug(
                    "--force-replace flag provided. Defaulting to OVERWRITE collision strategy."
                )
                manifest.collision_strategy = CollisionStrategy.OVERWRITE
            elif req.force_merge:
                logger.debug(
                    "--force-merge flag provided. Defaulting to MERGE collision strategy."
                )
                manifest.collision_strategy = CollisionStrategy.MERGE
            else:
                raise WorkspaceCollisionError(
                    paths=frozenset(collision_targets),
                )

        # Phase 3: Pre-flight verification
        missing_deps: dict[GlobalExecutable, MissingDependencyError] = {}
        for mod in self.modules:
            try:
                mod.pre_flight()
            except MissingDependencyError as e:
                missing_deps[e.dependency] = e

        if missing_deps:
            raise AggregatedDependencyError(tuple(missing_deps.values()))

        # Phase 4: Manifest aggregation
        if req.metadata:
            manifest.metadata.update(cast(ProjectMetadata, req.metadata))

        for mod in self.modules:
            mod.build(manifest)

        # Phase 5: Blueprint injection
        blueprint = req.template_blueprint
        if blueprint:
            logger.debug("Injecting blueprint structural fields into manifest.")

            for dep in blueprint.dependencies:
                manifest.dependencies.add(dep)

            for dep in blueprint.dev_dependencies:
                manifest.dependencies.add_dev(dep)

            for dep in blueprint.docs_dependencies:
                manifest.dependencies.add_docs(dep)

            for d in blueprint.directories:
                manifest.filesystem.add_directory(d)

            for ig in blueprint.vcs_ignores:
                manifest.filesystem.add_vcs_ignore(ig)

            for cmd in blueprint.system_tasks:
                manifest.tasks.add_system_task(cmd)

            for cmd in blueprint.post_install_tasks:
                manifest.tasks.add_post_install_task(cmd)

            if blueprint.pyproject_injections:
                logger.debug("Injecting pyproject.toml payloads from configuration.")
                for payload in blueprint.pyproject_injections.values():
                    manifest.filesystem.add_file_append("pyproject.toml", payload)

            if blueprint.appends:
                logger.debug("Injecting generic file appends from configuration.")
                for filepath, payloads in blueprint.appends.items():
                    for payload in payloads:
                        manifest.filesystem.add_file_append(filepath, payload)

            if blueprint.files:
                logger.debug("Injecting static files from configuration.")
                for filepath, content in blueprint.files.items():
                    manifest.filesystem.add_file_injection(filepath, content)

        return manifest

    def execute(self, manifest: EnvironmentManifest) -> ExecutionResult:
        """Realizes the pre-built manifest on disk.

        Takes an already-built manifest from plan() and executes it. Performs no
        planning, collision detection, template resolution, or user interaction.

        Args:
            manifest: The populated EnvironmentManifest to execute.

        Raises:
            PartialExecutionAbortedError: If the user interrupts execution after
                disk mutations have already begun.

        Returns:
            An ExecutionResult describing what was touched and any diagnostics.
        """
        executor = SystemExecutor(manifest, self.user_config, self.request.docker)
        try:
            executor.execute()
        except KeyboardInterrupt:
            raise PartialExecutionAbortedError(
                frozenset(executor.touched_paths)
            ) from None

        return ExecutionResult(
            touched_paths=frozenset(executor.touched_paths),
            diagnostics=tuple(executor.diagnostics),
        )
```

### __init__

```python
__init__(modules, user_config, request=None)
```

Initializes the orchestrator with the requested modules and intent.

Parameters:

| Name          | Type                    | Description                                     | Default                                                                                    |
| ------------- | ----------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `modules`     | `list[BootstrapModule]` | The ordered stack of bootstrap layers to apply. | *required*                                                                                 |
| `user_config` | `UserConfig`            | The active UserConfig instance.                 | *required*                                                                                 |
| `request`     | \`InitRequest           | None\`                                          | Optional InitRequest describing caller intent. Defaults to a no-op InitRequest if omitted. |

Source code in `src/protostar/orchestrator.py`

```python
def __init__(
    self,
    modules: list[BootstrapModule],
    user_config: UserConfig,
    request: InitRequest | None = None,
) -> None:
    """Initializes the orchestrator with the requested modules and intent.

    Args:
        modules: The ordered stack of bootstrap layers to apply.
        user_config: The active UserConfig instance.
        request: Optional InitRequest describing caller intent. Defaults to a
            no-op InitRequest if omitted.
    """
    self.modules = modules
    self.user_config = user_config
    self.request = request or InitRequest()
```

### plan

```python
plan()
```

Evaluates workspace state and assembles a declarative EnvironmentManifest.

A fresh EnvironmentManifest is instantiated on every call, guaranteeing that retries (e.g. after a collision resolution) start from a clean slate.

Raises:

| Type                      | Description                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `WorkspaceCollisionError` | If collision markers exist on disk and no force flag (force_merge / force_replace) was provided in the request. |
| `MissingDependencyError`  | If a module pre-flight check fails.                                                                             |

Returns:

| Type                  | Description                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `EnvironmentManifest` | A populated EnvironmentManifest ready to be passed to execute(). |

Source code in `src/protostar/orchestrator.py`

```python
def plan(self) -> EnvironmentManifest:
    """Evaluates workspace state and assembles a declarative EnvironmentManifest.

    A fresh EnvironmentManifest is instantiated on every call, guaranteeing
    that retries (e.g. after a collision resolution) start from a clean slate.

    Raises:
        WorkspaceCollisionError: If collision markers exist on disk and no
            force flag (force_merge / force_replace) was provided in the request.
        MissingDependencyError: If a module pre-flight check fails.

    Returns:
        A populated EnvironmentManifest ready to be passed to execute().
    """
    req = self.request

    # Phase 1: Instantiate a fresh manifest for every plan() call
    manifest = EnvironmentManifest(
        force_merge=req.force_merge,
        force_replace=req.force_replace,
    )

    # Phase 2: Collision intercept (raises instead of prompting)
    collision_targets: set[Path] = set()
    for mod in self.modules:
        for marker in mod.collision_markers:
            if marker.exists():
                collision_targets.add(marker)

    if collision_targets:
        if req.force_replace:
            logger.debug(
                "--force-replace flag provided. Defaulting to OVERWRITE collision strategy."
            )
            manifest.collision_strategy = CollisionStrategy.OVERWRITE
        elif req.force_merge:
            logger.debug(
                "--force-merge flag provided. Defaulting to MERGE collision strategy."
            )
            manifest.collision_strategy = CollisionStrategy.MERGE
        else:
            raise WorkspaceCollisionError(
                paths=frozenset(collision_targets),
            )

    # Phase 3: Pre-flight verification
    missing_deps: dict[GlobalExecutable, MissingDependencyError] = {}
    for mod in self.modules:
        try:
            mod.pre_flight()
        except MissingDependencyError as e:
            missing_deps[e.dependency] = e

    if missing_deps:
        raise AggregatedDependencyError(tuple(missing_deps.values()))

    # Phase 4: Manifest aggregation
    if req.metadata:
        manifest.metadata.update(cast(ProjectMetadata, req.metadata))

    for mod in self.modules:
        mod.build(manifest)

    # Phase 5: Blueprint injection
    blueprint = req.template_blueprint
    if blueprint:
        logger.debug("Injecting blueprint structural fields into manifest.")

        for dep in blueprint.dependencies:
            manifest.dependencies.add(dep)

        for dep in blueprint.dev_dependencies:
            manifest.dependencies.add_dev(dep)

        for dep in blueprint.docs_dependencies:
            manifest.dependencies.add_docs(dep)

        for d in blueprint.directories:
            manifest.filesystem.add_directory(d)

        for ig in blueprint.vcs_ignores:
            manifest.filesystem.add_vcs_ignore(ig)

        for cmd in blueprint.system_tasks:
            manifest.tasks.add_system_task(cmd)

        for cmd in blueprint.post_install_tasks:
            manifest.tasks.add_post_install_task(cmd)

        if blueprint.pyproject_injections:
            logger.debug("Injecting pyproject.toml payloads from configuration.")
            for payload in blueprint.pyproject_injections.values():
                manifest.filesystem.add_file_append("pyproject.toml", payload)

        if blueprint.appends:
            logger.debug("Injecting generic file appends from configuration.")
            for filepath, payloads in blueprint.appends.items():
                for payload in payloads:
                    manifest.filesystem.add_file_append(filepath, payload)

        if blueprint.files:
            logger.debug("Injecting static files from configuration.")
            for filepath, content in blueprint.files.items():
                manifest.filesystem.add_file_injection(filepath, content)

    return manifest
```

### execute

```python
execute(manifest)
```

Realizes the pre-built manifest on disk.

Takes an already-built manifest from plan() and executes it. Performs no planning, collision detection, template resolution, or user interaction.

Parameters:

| Name       | Type                  | Description                                   | Default    |
| ---------- | --------------------- | --------------------------------------------- | ---------- |
| `manifest` | `EnvironmentManifest` | The populated EnvironmentManifest to execute. | *required* |

Raises:

| Type                           | Description                                                               |
| ------------------------------ | ------------------------------------------------------------------------- |
| `PartialExecutionAbortedError` | If the user interrupts execution after disk mutations have already begun. |

Returns:

| Type              | Description                                                         |
| ----------------- | ------------------------------------------------------------------- |
| `ExecutionResult` | An ExecutionResult describing what was touched and any diagnostics. |

Source code in `src/protostar/orchestrator.py`

```python
def execute(self, manifest: EnvironmentManifest) -> ExecutionResult:
    """Realizes the pre-built manifest on disk.

    Takes an already-built manifest from plan() and executes it. Performs no
    planning, collision detection, template resolution, or user interaction.

    Args:
        manifest: The populated EnvironmentManifest to execute.

    Raises:
        PartialExecutionAbortedError: If the user interrupts execution after
            disk mutations have already begun.

    Returns:
        An ExecutionResult describing what was touched and any diagnostics.
    """
    executor = SystemExecutor(manifest, self.user_config, self.request.docker)
    try:
        executor.execute()
    except KeyboardInterrupt:
        raise PartialExecutionAbortedError(
            frozenset(executor.touched_paths)
        ) from None

    return ExecutionResult(
        touched_paths=frozenset(executor.touched_paths),
        diagnostics=tuple(executor.diagnostics),
    )
```

______________________________________________________________________

## Related Mechanics & Guides

- **[The Environment Manifest](.././manifest/):** Deep dive into the structured state container generated during the `plan()` phase.
- **[The System Executor](.././executor/):** See how the executor applies atomic AST deep-merges, file injections, and subprocess execution.
- **[Error Handling Architecture](.././error_handling/):** Learn how the orchestrator traps exceptions and routes them to POSIX exit codes and telemetry reports.
