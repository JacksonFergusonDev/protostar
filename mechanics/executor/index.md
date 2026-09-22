# The System Executor & Modular Execution Engine

While the Orchestrator plans the environment, the execution engine carries it out—writing files, updating configurations, and running shell commands.

To keep the codebase maintainable, secure, and testable, Protostar breaks execution logic into seven focused modules. This separates **content generation** and **security checks** from **command execution**.

______________________________________________________________________

## The 7-Module Architecture

```
flowchart LR
    classDef pure fill:#0f172a,stroke:#3b82f6,stroke-width:1px,color:#e2e8f0;
    classDef stateful fill:#334155,stroke:#475569,stroke-width:1px,color:#e2e8f0;
    classDef coordinator fill:#1e293b,stroke:#00e5ff,stroke-width:2px,color:#fff;

    M[(Environment\nManifest)] --> E(executor.py):::coordinator

    subgraph Execution Engine
        E --> S(security.py):::pure
        E --> T(toml_ast.py):::pure
        E --> A(appends.py):::pure
        E --> W(workflows.py):::pure
        E --> R(registry.py):::stateful

        E --> D(dependencies.py):::stateful
        E --> I(ide.py):::stateful
    end
```

### 1. The Thin Orchestrator (`executor.py`)

**Role:** Stateful execution sequencing and disk I/O. The `SystemExecutor` class acts as a thin coordinator. It iterates over the manifest, gathers necessary parameters, invokes the pure content generators, and writes the output to disk using atomic operations. It strictly enforces the chronological order of execution to prevent race conditions (e.g., ensuring `uv init` completes before attempting to merge `pyproject.toml` payloads).

### 2. Pure Content Generation

These modules contain pure functions: given the same inputs, they always return the same string or AST without touching the disk or network.

- **`workflows.py`**: Handles string templating for CI/CD workflows, Justfiles, Dockerfiles, pre-commit configurations, and VCS ignores.
- **`appends.py`**: Resolves language-specific comment syntax and injects hash-delimited marker blocks into existing file strings.
- **`toml_ast.py`**: Parses TOML strings using `tomlkit` to manipulate the Abstract Syntax Tree (AST), performing deep merges, header formatting, and array-of-tables (AoT) conflict resolution while preserving your comments.

### 3. Policy & System Integration

These modules interact with external boundaries, but do so predictably.

- **`security.py`**: Enforces strict boundaries (Pure). Validates that no filesystem operations escape the workspace root (`enforce_path_jail`) and that no unauthorized shell commands are executed (`enforce_binary_safelist`).
- **`dependencies.py`** (Stateful): Orchestrates `uv add` commands to resolve and install Python packages into their appropriate dependency groups (main, dev, docs).
- **`ide.py`** (Stateful): Verifies the presence of recommended extensions via the IDE's CLI (e.g., `code --list-extensions`) and deep-merges telemetry diagnostics and settings into `.vscode/settings.json`.
- **`registry.py`**: Interacts with the asynchronous static registry to fetch the latest pre-commit hook versions during the execution phase, falling back gracefully to a static mapping (`_fallbacks.py`) if network access is unavailable. These fallbacks are automatically kept in sync with the live edge CDN prior to every release via `scripts/sync_registry_fallbacks.py`.

______________________________________________________________________

## Security & Path Isolation

All disk writes and subprocess calls pass through security checks in `security.py`:

- **Path Jailing**: Before the executor writes any artifact, it asserts that the `target` path is physically bounded within `Path.cwd()`. This structurally prevents malicious blueprint templates from triggering directory traversal attacks (e.g., writing to `/etc/passwd`).
- **Binary Safelisting**: Before any shell task is executed (whether pre-install or post-install), the executable command name is verified against `ALLOWED_BINARIES` (e.g., `uv`, `git`, `npm`).

______________________________________________________________________

## AST Deep Merging & Collision Strategies

When merging configuration payloads into existing TOML files, Protostar utilizes `tomlkit` AST parsing rather than standard dictionary updates or destructive regular expressions.

```
flowchart TD
    classDef artifact fill:#0f172a,stroke:#3b82f6,stroke-width:1px,color:#e2e8f0;
    classDef process fill:#334155,stroke:#475569,stroke-width:1px,color:#e2e8f0;
    classDef decision fill:#1e293b,stroke:#00e5ff,stroke-width:2px,color:#fff;
    classDef format fill:#14532d,stroke:#4ade80,stroke-width:1px,color:#fff;

    Base[(Host pyproject.toml)]:::artifact --> ParseHost[Parse AST via tomlkit]:::process
    Payload[(Manifest Payload)]:::artifact --> ParsePayload[Parse AST via tomlkit]:::process

    ParseHost --> Strategy{Collision\nStrategy}:::decision
    ParsePayload --> Strategy

    Strategy -- ABORT --> Exit([Halt Operations])

    Strategy -- MERGE --> MergeLogic[Union Nodes\nPreserve host scalars]:::process
    Strategy -- OVERWRITE --> OverwriteLogic[Union Nodes\nPurge orphaned host scalars]:::process

    MergeLogic --> Formatter
    OverwriteLogic --> Formatter[Deterministic Formatter\nApply Headers & Sorting]:::format

    Formatter --> Write[(Atomic Disk Write)]:::artifact
```

The merge behavior is governed by the resolved `CollisionStrategy`:

- **Merge (Default):** The engine walks the AST, appending missing keys and extending tables. Existing scalar values or sibling tables that are not explicitly targeted by the payload are safely ignored and preserved.
- **Overwrite:** The engine aggressively prunes the target. If the payload defines a specific table (e.g., `[tool.ruff]`), any existing scalar keys within that table on the host that *do not* exist in the payload are purged, forcing strict parity with Protostar's baseline.

______________________________________________________________________

## Subprocess Telemetry

Directly calling `subprocess.run` in a CLI tool often leads to silent failures or messy interleaved terminal output. Protostar routes all system tasks and dependency resolutions through `protostar.system.execute_subprocess`.

This wrapper executes the command silently while capturing both `stdout` and `stderr`, and enforces granular task-level timeouts. If the process returns a non-zero exit code, the executor raises a strictly typed `CommandExecutionError`. These exceptions preserve the exact upstream streams, ensuring the Orchestrator can catch the failure and present the raw diagnostics to you without destructively flattening the context.

Simulated Subprocess Telemetry Output

When a shell execution fails, the captured streams are formatted to pinpoint the exact failure mechanism:

```text
Command failed during setup: uv init --python 3.99

Diagnostics:
--- STDERR ---
error: Failed to download python 3.99
Caused by: No downloadable Python versions matching: 3.99
```

______________________________________________________________________

## API Reference

Core Interface: `SystemExecutor`

## protostar.executor.SystemExecutor

Executes the materialized environment manifest by mutating the local disk and shell.

Source code in `src/protostar/executor.py`

```python
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
            msg = task.description or f"Running: {binary_name}"
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
                original_content = (
                    target.read_text(encoding="utf-8") if target.exists() else ""
                )
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
            existing_content = (
                gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
            )
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
            existing_content = (
                dockerignore.read_text(encoding="utf-8")
                if dockerignore.exists()
                else ""
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
```

### interpolation_context `property`

```python
interpolation_context
```

Dynamically generates the context for template interpolation.

### __init__

```python
__init__(manifest, config, docker=False)
```

Initializes the executor with the target manifest state.

Parameters:

| Name       | Type                  | Description                                                       | Default    |
| ---------- | --------------------- | ----------------------------------------------------------------- | ---------- |
| `manifest` | `EnvironmentManifest` | The centralized state object containing all execution directives. | *required* |
| `config`   | `UserConfig`          | The active Protostar configuration instance.                      | *required* |
| `docker`   | `bool`                | If True, scaffolds a .dockerignore from the manifest ignores.     | `False`    |

Source code in `src/protostar/executor.py`

```python
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
```

### record_touch

```python
record_touch(path)
```

Records a path as having been modified or created during execution.

Source code in `src/protostar/executor.py`

```python
def record_touch(self, path: Path | str) -> None:
    """Records a path as having been modified or created during execution."""
    try:
        rel_path = Path(path).resolve().relative_to(Path.cwd().resolve())
        self.touched_paths.add(rel_path.as_posix())
    except (ValueError, RuntimeError):
        self.touched_paths.add(str(path))
```

### add_diagnostic

```python
add_diagnostic(
    phase, message, severity=Severity.INFO, detail=None
)
```

Queues a diagnostic event for the post-execution summary panel.

Source code in `src/protostar/executor.py`

```python
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
```

### execute

```python
execute()
```

Executes the materialized manifest in a deterministic sequence.

Source code in `src/protostar/executor.py`

```python
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
```

Core Interface: `execute_subprocess`

## protostar.system.execute_subprocess

```python
execute_subprocess(cmd, timeout=None)
```

Executes a subprocess silently and captures telemetry on failure.

Parameters:

| Name      | Type        | Description                                         | Default                                                  |
| --------- | ----------- | --------------------------------------------------- | -------------------------------------------------------- |
| `cmd`     | `list[str]` | The command and its arguments as a list of strings. | *required*                                               |
| `timeout` | \`int       | None\`                                              | The maximum execution time in seconds. Defaults to None. |

Raises:

| Type                    | Description                                  |
| ----------------------- | -------------------------------------------- |
| `CommandTimeoutError`   | If the execution time limit is exceeded.     |
| `CommandExecutionError` | If the process returns a non-zero exit code. |

Source code in `src/protostar/system.py`

```python
def execute_subprocess(cmd: list[str], timeout: int | None = None) -> None:
    """Executes a subprocess silently and captures telemetry on failure.

    Args:
        cmd: The command and its arguments as a list of strings.
        timeout: The maximum execution time in seconds. Defaults to None.

    Raises:
        CommandTimeoutError: If the execution time limit is exceeded.
        CommandExecutionError: If the process returns a non-zero exit code.
    """
    exe = shutil.which(cmd[0])
    resolved_cmd = list(cmd)
    if exe:
        resolved_cmd[0] = exe

    try:
        subprocess.run(
            resolved_cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        logger.debug(f"Task timed out after {timeout} seconds: {' '.join(cmd)}")
        raise CommandTimeoutError(command=cmd, timeout=timeout or 0) from e
    except subprocess.CalledProcessError as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""

        output_blocks = []
        if stdout:
            output_blocks.append(f"--- STDOUT ---\n{stdout.strip()}")
        if stderr:
            output_blocks.append(f"--- STDERR ---\n{stderr.strip()}")

        log_output = (
            "\n\n".join(output_blocks) if output_blocks else "No output captured."
        )
        logger.debug(f"Task failed: {' '.join(cmd)}\nOutput:\n{log_output}")

        raise CommandExecutionError(
            command=cmd,
            returncode=e.returncode,
            stdout=stdout,
            stderr=stderr,
        ) from e
```

______________________________________________________________________

## Related Mechanics & Guides

- **[The Orchestrator](.././orchestrator/):** See how the state machine coordinates the planning phase and passes the manifest to the executor.
- **[The Environment Manifest](.././manifest/):** Review the structured state container evaluated by the executor.
- **[The Module Architecture](.././modules/):** Explore the polymorphic modules that generate the requirements processed by the executor.
