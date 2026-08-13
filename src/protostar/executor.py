import hashlib
import json
import logging
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from rich.console import Console

from .config import ProtostarConfig
from .errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ConfigurationError,
    FileSystemError,
)
from .fs import atomic_write_text
from .manifest import CollisionStrategy, EnvironmentManifest, Severity
from .system import execute_subprocess

logger = logging.getLogger("protostar")
console = Console()


class SystemExecutor:
    """Executes the materialized environment manifest by mutating the local disk and shell."""

    def __init__(
        self,
        manifest: EnvironmentManifest,
        config: ProtostarConfig,
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
        self._execute_tasks()
        self._install_dependencies()
        self._append_files()
        self._write_ignores()
        self._write_docker_artifacts()
        self._write_ide_settings()
        self._execute_post_install_tasks()
        self._check_ide_extensions()

    def _check_ide_extensions(self) -> None:
        """Verifies that the configured IDE has the recommended extensions installed.

        Fails silently if the IDE CLI is unavailable or execution fails. Appends a warning
        diagnostic only on a successful check that uncovers missing extensions.
        """
        if not self.manifest.ide_extensions or self.config.ide not in (
            "vscode",
            "cursor",
        ):
            return

        binary_map = {"vscode": "code", "cursor": "cursor"}
        ide_binary = binary_map[self.config.ide]

        if not shutil.which(ide_binary):
            return

        try:
            result = subprocess.run(
                [ide_binary, "--list-extensions"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            # Normalize to lowercase for safe diffing
            installed = {ext.lower() for ext in result.stdout.strip().splitlines()}
            missing = []

            for ext_req in self.manifest.ide_extensions:
                if isinstance(ext_req, tuple):
                    if not any(e.lower() in installed for e in ext_req):
                        missing.append(f"{' or '.join(ext_req)}")
                else:
                    if ext_req.lower() not in installed:
                        missing.append(ext_req)

            if missing:
                self.manifest.add_diagnostic(
                    phase="IDE",
                    message=f"Missing recommended {self.config.ide} extensions: {', '.join(missing)}",
                    severity=Severity.WARNING,
                )
        except Exception as e:
            # Reached if the CLI crashes, hangs past 5s, or throws an unexpected I/O error.
            self.manifest.add_diagnostic(
                phase="IDE",
                message=f"IDE extension verification skipped due to an unexpected error: {e}",
                severity=Severity.SKIP,
            )

    def _validate_targets(self) -> None:
        """Validates the syntax of existing target files before disk I/O begins.

        Uses the C-optimized tomllib to quickly evaluate target workspace files,
        ensuring that subsequent tomlkit operations will not fail mid-execution
        and leave the environment fragmented.

        Raises:
            SystemExit: If an existing target TOML file contains syntax errors.
        """
        for filepath in self.manifest.file_appends:
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
        """Assembles and interpolates the pre-commit configuration."""
        if not self.manifest.wants_pre_commit and not self.manifest.wants_prek:
            return

        target = Path(".pre-commit-config.yaml")
        if (
            target.exists()
            and self.manifest.collision_strategy != CollisionStrategy.OVERWRITE
        ):
            self.manifest.add_diagnostic(
                phase="Executor",
                message="Skipping .pre-commit-config.yaml generation; file already exists.",
                severity=Severity.SKIP,
            )
            return

        base_yaml = """repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \\.py$
      - id: end-of-file-fixer
        exclude: \\.py$
      - id: check-yaml
        exclude: \\.py$
      - id: check-added-large-files"""

        # Enforce exactly one empty line between all dynamic payloads
        hooks_yaml = "\n\n".join(self.manifest.pre_commit_hooks)

        # Enforce exactly one empty line between the base block and the dynamic payloads
        full_yaml = f"{base_yaml}\n\n{hooks_yaml}\n" if hooks_yaml else f"{base_yaml}\n"

        if "{{MYPY_DEPENDENCIES}}" in full_yaml:
            # We use manual string manipulation here instead of a YAML library (like PyYAML)
            # to avoid adding a heavy third-party dependency for a very minor feature.
            # If the schema of .pre-commit-config.yaml ever becomes significantly more
            # complex, this should be refactored to use a dedicated YAML serialization library.
            deps = self.manifest.dependencies
            if deps:
                # Guarantee exactly 10 spaces of indentation for each list item
                deps_formatted = "\n".join(f"{' ' * 10}- {d}" for d in deps)
                full_yaml = full_yaml.replace("{{MYPY_DEPENDENCIES}}", deps_formatted)
            else:
                # If no runtime dependencies, strip the key cleanly
                full_yaml = full_yaml.replace(
                    "        additional_dependencies:\n{{MYPY_DEPENDENCIES}}", ""
                )

        try:
            atomic_write_text(target, full_yaml)
        except OSError as e:
            raise FileSystemError("write configuration file", str(target), e) from e
        logger.debug("Scaffolded .pre-commit-config.yaml")

    def _write_injected_files(self) -> None:
        """Writes all queued boilerplate files to the local workspace."""
        if not self.manifest.file_injections:
            return

        for filepath, content in self.manifest.file_injections.items():
            target = Path(filepath)
            if (
                not target.exists()
                or self.manifest.collision_strategy == CollisionStrategy.OVERWRITE
            ):
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write_text(target, content)
                except OSError as e:
                    raise FileSystemError(
                        "inject boilerplate file", str(target), e
                    ) from e
                logger.debug(f"Injected configuration file: {filepath}")

    def _create_directories(self) -> None:
        """Scaffolds all queued directories in the local workspace."""
        if not self.manifest.directories:
            return

        for dir_path in self.manifest.directories:
            path = Path(dir_path)
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileSystemError(
                    "create scaffolding directory", str(path), e
                ) from e
            logger.debug(f"Scaffolded directory: {path}")

    def _execute_tasks(self) -> None:
        """Runs the accumulated system tasks (e.g., initialization commands)."""
        for task in self.manifest.system_tasks:
            binary_name = Path(task.command[0]).name
            msg = task.description or f"Propelling sequence: {binary_name}"
            with console.status(msg):
                execute_subprocess(task.command, timeout=task.timeout)

    def _execute_post_install_tasks(self) -> None:
        """Runs accumulated tasks that require dependencies to be installed first."""
        for task in self.manifest.post_install_tasks:
            binary_name = Path(task.command[0]).name
            msg = task.description or f"Propelling sequence: {binary_name}"
            with console.status(msg):
                execute_subprocess(task.command, timeout=task.timeout)

    # --- Architectural Note: AST-Preserving TOML Merging ---
    # Protostar uses `tomlkit` AST parsing rather than standard dictionary updates or tomllib/tomli.
    #
    # Rationale:
    #   1. Comment & Format Preservation: Simple deserialization/reserialization strips user comments,
    #      custom ordering, and blank lines in pyproject.toml.
    #   2. Selective Overwrites: In OVERWRITE mode, scalar keys are purged from target tables while
    #      sibling tables (e.g., [tool.pytest] vs [tool.ruff]) are preserved to prevent destroying
    #      unrelated tooling configuration.
    #   3. AST Parity Guards: Type mismatches (e.g., merging a table into a scalar key) emit non-fatal
    #      diagnostics rather than corrupting the AST.
    def _deep_merge_tomlkit(
        self,
        base: Any,
        payload: Any,
        overwrite: bool = False,
        path: tuple[str, ...] = (),
    ) -> None:
        """Recursively deep-merges a tomlkit payload into a base document.

        Args:
            base: The existing tomlkit document or table to mutate.
            payload: The incoming tomlkit table to merge into the base.
            overwrite: If True, unmatched scalar keys in the base will be purged,
                and array-of-tables will be completely replaced.
            path: The tuple of keys representing the current path in the document.
        """
        import tomlkit.items

        # Purge scalar/array keys in base that are missing from the payload
        # to enforce strict AST overwriting, while preserving sibling tables.
        # We explicitly protect the root document and the [project] table from being purged.
        if overwrite and len(path) > 0 and path[0] != "project":
            keys_to_remove = []
            for b_key, b_val in base.items():
                if b_key not in payload and not isinstance(
                    b_val, (tomlkit.items.Table, tomlkit.items.AoT)
                ):
                    keys_to_remove.append(b_key)
            for k in keys_to_remove:
                del base[k]

        for key, value in payload.items():
            if key in base:
                if isinstance(value, tomlkit.items.Table):
                    # Type Parity Guard
                    if not isinstance(base[key], tomlkit.items.Table):
                        self.manifest.add_diagnostic(
                            phase="Executor",
                            message=f"TOML Merge Collision: Expected a Table for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            severity=Severity.WARNING,
                        )
                        continue

                    has_sub_tables = any(
                        isinstance(v, (tomlkit.items.Table, tomlkit.items.AoT))
                        for v in value.values()
                    )

                    is_project = (key == "project" and len(path) == 0) or (
                        len(path) > 0 and path[0] == "project"
                    )

                    if overwrite and not has_sub_tables and not is_project:
                        base[key] = value
                    else:
                        self._deep_merge_tomlkit(
                            base[key], value, overwrite, (*path, key)
                        )

                elif isinstance(value, tomlkit.items.AoT):
                    # Type Parity Guard
                    if not isinstance(base[key], tomlkit.items.AoT):
                        self.manifest.add_diagnostic(
                            phase="Executor",
                            message=f"TOML Merge Collision: Expected an Array of Tables for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            severity=Severity.WARNING,
                        )
                        continue

                    if overwrite:
                        base[key] = value
                    else:
                        for item in value:
                            base[key].append(item)
                else:
                    base[key] = value
            else:
                if isinstance(value, tomlkit.items.Table):
                    value.add(tomlkit.nl())
                elif isinstance(value, tomlkit.items.AoT) and len(value) > 0:
                    value[-1].add(tomlkit.nl())

                base[key] = value

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        if not self.manifest.file_appends:
            return

        python_version = None
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            try:
                with pyproject_path.open("rb") as f:
                    pyproject_data = tomllib.load(f)
                    req_python = pyproject_data.get("project", {}).get(
                        "requires-python", ""
                    )
                    match = re.search(r"(\d+\.\d+)", req_python)
                    if match:
                        python_version = match.group(1)
            except Exception as e:
                logger.debug(f"Failed to parse pyproject.toml for python version: {e}")

        # 2. Protostar config or hardcoded default
        if not python_version:
            python_version = self.config.python_version or "3.13"

        for filepath, contents in self.manifest.file_appends.items():
            target = Path(filepath)

            try:
                original_content = target.read_text() if target.exists() else ""
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileSystemError(
                    "read target append context", str(target), e
                ) from e

            if target.suffix == ".toml":
                import tomlkit

                doc = (
                    tomlkit.parse(original_content)
                    if original_content
                    else tomlkit.document()
                )
                ast_mutated = False

                for payload in contents:
                    interpolated = payload.replace("{{PYTHON_VERSION}}", python_version)
                    try:
                        payload_doc = tomlkit.parse(interpolated)
                        ast_mutated = True
                        is_overwrite = (
                            self.manifest.collision_strategy
                            == CollisionStrategy.OVERWRITE
                        )
                        self._deep_merge_tomlkit(
                            doc, payload_doc, overwrite=is_overwrite
                        )
                    except Exception as e:
                        raise ConfigurationError(
                            f"Failed to parse injected TOML payload for {filepath}.\nDetails: {e}"
                        ) from e

                if ast_mutated:
                    new_content = tomlkit.dumps(doc)

                    # Apply visual separators safely using anchored regex to prevent substring collisions
                    if not re.search(
                        r"^# ---- Ruff ---- #", new_content, flags=re.MULTILINE
                    ):
                        new_content = re.sub(
                            r"^\[tool\.ruff\]\s*$",
                            "# ---- Ruff ---- #\n\n[tool.ruff]",
                            new_content,
                            flags=re.MULTILINE,
                        )
                    if not re.search(
                        r"^# ---- Mypy ---- #", new_content, flags=re.MULTILINE
                    ):
                        new_content = re.sub(
                            r"^\[tool\.mypy\]\s*$",
                            "# ---- Mypy ---- #\n\n[tool.mypy]",
                            new_content,
                            flags=re.MULTILINE,
                        )
                    if not re.search(
                        r"^# ---- Pytest ---- #", new_content, flags=re.MULTILINE
                    ):
                        new_content = re.sub(
                            r"^\[tool\.pytest\.ini_options\]\s*$",
                            "# ---- Pytest ---- #\n\n[tool.pytest.ini_options]",
                            new_content,
                            flags=re.MULTILINE,
                        )
                    if not re.search(
                        r"^# ---- Commitizen ---- #", new_content, flags=re.MULTILINE
                    ):
                        new_content = re.sub(
                            r"^\[tool\.commitizen\]\s*$",
                            "# ---- Commitizen ---- #\n\n[tool.commitizen]",
                            new_content,
                            flags=re.MULTILINE,
                        )

                    # Add main Tool Configuration header before the first tool header if not exists
                    if "# Tool Configuration" not in new_content:
                        tool_match = re.search(
                            r"^# ---- (Ruff|Mypy|Pytest|Commitizen) ---- #\s*$",
                            new_content,
                            flags=re.MULTILINE,
                        )
                        if tool_match:
                            header = "# ==================================================\n# Tool Configuration\n# ==================================================\n\n"
                            # Ensure empty line before the header
                            prefix = (
                                "\n"
                                if not new_content[: tool_match.start()].endswith(
                                    "\n\n"
                                )
                                else ""
                            )
                            new_content = (
                                new_content[: tool_match.start()]
                                + prefix
                                + header
                                + new_content[tool_match.start() :]
                            )

                    new_content = re.sub(r"\n{3,}", "\n\n", new_content)
                    if new_content.strip() != original_content.strip():
                        try:
                            atomic_write_text(target, new_content)
                        except OSError as e:
                            raise FileSystemError(
                                "mutate configuration AST", str(target), e
                            ) from e
                        logger.debug(f"Updated configuration AST in {filepath}")
                continue

            existing_clean = original_content.rstrip()
            missing_payloads = []

            for payload in contents:
                interpolated = payload.replace("{{PYTHON_VERSION}}", python_version)

                # Generate a deterministic boundary marker
                payload_hash = hashlib.md5(payload.encode("utf-8")).hexdigest()[:8]
                marker = f"# --- Protostar Injection: {payload_hash} ---"

                if (
                    marker in original_content
                    and self.manifest.collision_strategy != CollisionStrategy.OVERWRITE
                ):
                    continue

                framed_payload = f"{marker}\n{interpolated.strip()}\n# --- End Protostar Injection ---"
                missing_payloads.append(framed_payload)

            if not missing_payloads:
                continue

            combined_content = "\n\n".join(missing_payloads)
            prefix = "\n\n" if existing_clean and combined_content else ""

            try:
                atomic_write_text(
                    target, existing_clean + prefix + combined_content + "\n"
                )
            except OSError as e:
                raise FileSystemError(
                    "append configurations block", str(target), e
                ) from e
            logger.debug(f"Updated configuration string block in {filepath}")

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        try:
            existing_content = gitignore.read_text() if gitignore.exists() else ""
            existing_lines = {line.strip() for line in existing_content.splitlines()}
            missing = [p for p in self.manifest.vcs_ignores if p not in existing_lines]

            if missing:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                atomic_write_text(
                    gitignore,
                    existing_content + prefix + "\n".join(sorted(missing)) + "\n",
                )
                logger.debug(f"Appended {len(missing)} items to .gitignore")
        except OSError as e:
            raise FileSystemError(
                "update workspace ignore manifest (.gitignore)", str(gitignore), e
            ) from e

    def _write_docker_artifacts(self) -> None:
        """Generates a .dockerignore to optimize container build contexts."""
        if not self.docker:
            return

        dockerignore = Path(".dockerignore")
        try:
            existing_content = dockerignore.read_text() if dockerignore.exists() else ""
            existing_lines = {line.strip() for line in existing_content.splitlines()}
            base_ignores = {".git/", "tests/", "docs/", "README*", ".vscode/", ".idea/"}

            has_uv_init = any(
                task.command[:2] == ["uv", "init"]
                for task in self.manifest.system_tasks
            )
            if has_uv_init:
                base_ignores.add(".python-version")

            combined_ignores = self.manifest.vcs_ignores | base_ignores
            missing = [p for p in combined_ignores if p not in existing_lines]

            if missing:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                atomic_write_text(
                    dockerignore,
                    existing_content + prefix + "\n".join(sorted(missing)) + "\n",
                )
                logger.debug(f"Appended {len(missing)} items to .dockerignore")
        except OSError as e:
            raise FileSystemError(
                "scaffold container runtime ignore configurations", str(dockerignore), e
            ) from e

    def _write_ide_settings(self) -> None:
        """Writes the aggregated IDE configuration to the appropriate local files."""
        if not self.manifest.ide_settings:
            return

        vscode_dir = Path(".vscode")
        settings_path = vscode_dir / "settings.json"
        settings = {}

        if settings_path.exists():
            try:
                original_content = settings_path.read_text()
                if original_content.strip():
                    parsed_data = json.loads(original_content)
                    if not isinstance(parsed_data, dict):
                        raise ValueError("Root JSON element is not an object.")
                    settings = parsed_data
            except (json.JSONDecodeError, ValueError):
                self.manifest.add_diagnostic(
                    phase="Executor",
                    message="Existing settings.json contains comments, trailing commas, or is malformed. Skipping IDE settings injection to prevent data loss.",
                    severity=Severity.WARNING,
                )
                return
            except OSError as e:
                raise FileSystemError(
                    "inspect active IDE settings files", str(settings_path), e
                ) from e

        # 1-level deep dictionary merge
        for key, value in self.manifest.ide_settings.items():
            if isinstance(value, dict) and isinstance(settings.get(key), dict):
                settings[key].update(value)
            else:
                settings[key] = value

        try:
            vscode_dir.mkdir(exist_ok=True)
            atomic_write_text(settings_path, json.dumps(settings, indent=4) + "\n")
        except OSError as e:
            raise FileSystemError(
                "synchronize IDE workspace preferences", str(settings_path), e
            ) from e

    def _install_dependencies(self) -> None:
        """Installs queued dependencies using uv."""
        if not self.manifest.dependencies and not self.manifest.dev_dependencies:
            return

        # Apply a generous 10-minute leash for heavy, network-bound payload resolutions
        resolution_timeout = 600

        if self.manifest.dependencies:
            cmd = ["uv", "add", *self.manifest.dependencies]
            try:
                with console.status(
                    f"Resolving and injecting {len(self.manifest.dependencies)} payloads"
                ):
                    execute_subprocess(cmd, timeout=resolution_timeout)
            except (CommandExecutionError, CommandTimeoutError) as e:
                self.manifest.add_diagnostic(
                    phase="Executor",
                    message=f"Standard dependency resolution failed: {e}",
                    severity=Severity.WARNING,
                    detail=e.output_detail
                    if isinstance(e, CommandExecutionError)
                    else None,
                )

        if self.manifest.dev_dependencies:
            dev_cmd = ["uv", "add", "--dev", *self.manifest.dev_dependencies]
            try:
                with console.status(
                    f"Resolving and installing {len(self.manifest.dev_dependencies)} development dependencies"
                ):
                    execute_subprocess(dev_cmd, timeout=resolution_timeout)
            except (CommandExecutionError, CommandTimeoutError) as e:
                self.manifest.add_diagnostic(
                    phase="Executor",
                    message=f"Development dependency resolution failed: {e}",
                    severity=Severity.WARNING,
                    detail=e.output_detail
                    if isinstance(e, CommandExecutionError)
                    else None,
                )
