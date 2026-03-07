import hashlib
import json
import logging
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from rich.console import Console

from .config import ProtostarConfig
from .manifest import CollisionStrategy, EnvironmentManifest
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
        self.warnings: list[str] = []

    def execute(self) -> None:
        """Executes the materialized manifest in a deterministic sequence."""
        self._validate_targets()
        self._create_directories()
        self._write_injected_files()
        self._write_pre_commit_config()
        self._execute_tasks()
        self._append_files()
        self._write_ignores()
        self._write_docker_artifacts()
        self._write_ide_settings()
        self._install_dependencies()

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
                    console.print(
                        f"\n[bold red]Validation Failure:[/bold red] Syntax error in existing workspace file: {filepath}"
                    )
                    console.print(f"Details: {e}")
                    console.print(
                        "\nProtostar cannot safely merge configurations into a malformed file. "
                        "Please fix the syntax error and re-run the command."
                    )
                    sys.exit(1)

    def _write_pre_commit_config(self) -> None:
        """Assembles and interpolates the pre-commit configuration."""
        if not self.manifest.wants_pre_commit:
            return

        target = Path(".pre-commit-config.yaml")
        if (
            target.exists()
            and self.manifest.collision_strategy != CollisionStrategy.OVERWRITE
        ):
            logger.debug(
                "Skipping .pre-commit-config.yaml generation; file already exists."
            )
            return

        base_yaml = """repos:
  # 1. Generic hooks (configured to ignore Python to avoid formatting conflicts)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \\.py$
      - id: end-of-file-fixer
        exclude: \\.py$
      - id: check-yaml
      - id: check-added-large-files
"""
        hooks_yaml = "\n".join(self.manifest.pre_commit_hooks)
        full_yaml = f"{base_yaml}\n{hooks_yaml}\n" if hooks_yaml else f"{base_yaml}\n"

        if "{{MYPY_DEPENDENCIES}}" in full_yaml:
            deps = self.manifest.dependencies + self.manifest.dev_dependencies
            if deps:
                deps_formatted = "\n".join(f"          - {d}" for d in deps)
            else:
                deps_formatted = "          []"
            full_yaml = full_yaml.replace("{{MYPY_DEPENDENCIES}}", deps_formatted)

        target.write_text(full_yaml)
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
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                logger.debug(f"Injected configuration file: {filepath}")

    def _create_directories(self) -> None:
        """Scaffolds all queued directories in the local workspace."""
        if not self.manifest.directories:
            return

        for dir_path in self.manifest.directories:
            path = Path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Scaffolded directory: {path}")

    def _execute_tasks(self) -> None:
        """Runs the accumulated system tasks (e.g., initialization commands)."""
        for task in self.manifest.system_tasks:
            with console.status(f"Executing {task[0]}"):
                execute_subprocess(task)

    def _deep_merge_tomlkit(
        self, base: Any, payload: Any, overwrite: bool = False
    ) -> None:
        """Recursively deep-merges a tomlkit payload into a base document."""
        import tomlkit.items

        for key, value in payload.items():
            if key in base:
                if isinstance(value, tomlkit.items.Table):
                    # Type Parity Guard
                    if not isinstance(base[key], tomlkit.items.Table):
                        self.warnings.append(
                            f"TOML Merge Collision: Expected a Table for key '{key}', "
                            f"but found {type(base[key]).__name__}. Skipping injection."
                        )
                        continue

                    has_sub_tables = any(
                        isinstance(v, (tomlkit.items.Table, tomlkit.items.AoT))
                        for v in value.values()
                    )
                    if overwrite and not has_sub_tables:
                        base[key] = value
                    else:
                        self._deep_merge_tomlkit(base[key], value, overwrite)

                elif isinstance(value, tomlkit.items.AoT):
                    # Type Parity Guard
                    if not isinstance(base[key], tomlkit.items.AoT):
                        self.warnings.append(
                            f"TOML Merge Collision: Expected an Array of Tables for key '{key}', "
                            f"but found {type(base[key]).__name__}. Skipping injection."
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
                base[key] = value

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        if not self.manifest.file_appends:
            return

        # Resolve the active Python version via a fallback chain
        python_version = None

        # 1. pyproject.toml `requires-python` (uv-managed projects)
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
                        logger.debug(
                            f"Resolved Python version {python_version} from pyproject.toml"
                        )
            except Exception as e:
                logger.debug(f"Failed to parse pyproject.toml for python version: {e}")

        # 2. .venv/pyvenv.cfg `version` field (pip/venv-managed projects)
        if not python_version:
            pyvenv_path = Path(".venv/pyvenv.cfg")
            if pyvenv_path.exists():
                content = pyvenv_path.read_text()
                match = re.search(r"^version\s*=\s*(\d+\.\d+)", content, re.MULTILINE)
                if match:
                    python_version = match.group(1)
                    logger.debug(
                        f"Resolved Python version {python_version} from pyvenv.cfg"
                    )
                else:
                    logger.warning(
                        "Found .venv/pyvenv.cfg but could not extract Python version. "
                        "Falling back to default."
                    )

        # 3. Protostar config or hardcoded default
        if not python_version:
            python_version = self.config.python_version or "3.12"

        for filepath, contents in self.manifest.file_appends.items():
            target = Path(filepath)
            original_content = target.read_text() if target.exists() else ""
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)

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
                        console.print(
                            f"\n[bold red]Internal Error:[/bold red] Failed to parse injected TOML payload for {filepath}.\nDetails: {e}"
                        )
                        sys.exit(1)

                if ast_mutated:
                    new_content = tomlkit.dumps(doc)
                    if new_content.strip() != original_content.strip():
                        target.write_text(new_content)
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
            target.write_text(existing_clean + prefix + combined_content + "\n")
            logger.debug(f"Updated configuration string block in {filepath}")

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        existing_content = gitignore.read_text() if gitignore.exists() else ""
        missing = [p for p in self.manifest.vcs_ignores if p not in existing_content]

        if missing:
            with gitignore.open("a") as f:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                f.write(prefix + "\n".join(missing) + "\n")
            logger.debug(f"Appended {len(missing)} items to .gitignore")

    def _write_docker_artifacts(self) -> None:
        """Generates a .dockerignore to optimize container build contexts."""
        if not self.docker:
            return

        dockerignore = Path(".dockerignore")
        existing_content = dockerignore.read_text() if dockerignore.exists() else ""
        base_ignores = {".git/", "tests/", "docs/", "README*", ".vscode/", ".idea/"}

        has_uv_init = any(
            task[:2] == ["uv", "init"] for task in self.manifest.system_tasks
        )
        if has_uv_init:
            base_ignores.add(".python-version")

        combined_ignores = self.manifest.vcs_ignores | base_ignores
        missing = [p for p in combined_ignores if p not in existing_content]

        if missing:
            with dockerignore.open("a") as f:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                f.write(prefix + "\n".join(sorted(missing)) + "\n")
            logger.debug(f"Appended {len(missing)} items to .dockerignore")

    def _write_ide_settings(self) -> None:
        """Writes the aggregated IDE configuration to the appropriate local files."""
        if not self.manifest.ide_settings:
            return

        vscode_dir = Path(".vscode")
        settings_path = vscode_dir / "settings.json"
        settings = {}

        if settings_path.exists():
            original_content = settings_path.read_text()
            if not original_content.strip():
                # Handle completely empty files gracefully by defaulting to {}
                pass
            else:
                try:
                    parsed_data = json.loads(original_content)
                    if not isinstance(parsed_data, dict):
                        raise ValueError("Root JSON element is not an object.")
                    settings = parsed_data
                except (json.JSONDecodeError, ValueError):
                    console.print(
                        "Existing settings.json contains comments, "
                        "trailing commas, or is malformed. Skipping IDE settings injection "
                        "to prevent data loss."
                    )
                    return

        # 1-level deep dictionary merge
        for key, value in self.manifest.ide_settings.items():
            if isinstance(value, dict) and isinstance(settings.get(key), dict):
                settings[key].update(value)
            else:
                settings[key] = value

        vscode_dir.mkdir(exist_ok=True)
        # json.dumps inherently preserves dictionary insertion order in standard CPython
        settings_path.write_text(json.dumps(settings, indent=4) + "\n")

    def _install_dependencies(self) -> None:
        """Installs queued dependencies using the active Python manager."""
        if not self.manifest.dependencies and not self.manifest.dev_dependencies:
            return

        if self.config.python_package_manager == "uv":
            if self.manifest.dependencies:
                cmd = ["uv", "add"] + self.manifest.dependencies
                try:
                    with console.status(
                        f"Resolving and installing {len(self.manifest.dependencies)} dependencies"
                    ):
                        execute_subprocess(cmd)
                except RuntimeError as e:
                    self.warnings.append(f"Standard dependency resolution failed: {e}")

            if self.manifest.dev_dependencies:
                dev_cmd = ["uv", "add", "--dev"] + self.manifest.dev_dependencies
                try:
                    with console.status(
                        f"Resolving and installing {len(self.manifest.dev_dependencies)} development dependencies"
                    ):
                        execute_subprocess(dev_cmd)
                except RuntimeError as e:
                    self.warnings.append(
                        f"Development dependency resolution failed: {e}"
                    )
        else:
            venv_pip = Path(".venv/bin/pip")
            pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"
            all_deps = self.manifest.dependencies + self.manifest.dev_dependencies
            cmd = [pip_cmd, "install"] + all_deps

            try:
                with console.status(
                    f"Resolving and installing {len(all_deps)} total dependencies"
                ):
                    execute_subprocess(cmd)
            except RuntimeError as e:
                self.warnings.append(f"Pip dependency resolution failed: {e}")

            req_path = Path("requirements.txt")
            if req_path.exists():
                console.print(
                    "[yellow]Warning:[/yellow] requirements.txt already exists. "
                    "Dependencies were installed to the virtual environment, but the file was not overwritten."
                )
            else:
                try:
                    result = subprocess.run(
                        [pip_cmd, "freeze"], capture_output=True, text=True, check=True
                    )
                    req_path.write_text(result.stdout)
                    logger.debug("Successfully froze dependencies to requirements.txt")
                except Exception as e:
                    self.warnings.append(
                        f"Failed to freeze dependencies to requirements.txt: {e}"
                    )
