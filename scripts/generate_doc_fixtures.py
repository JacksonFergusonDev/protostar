import argparse
import importlib.resources
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import tomlkit
from rich.console import Console
from rich.panel import Panel
from rich.terminal_theme import DEFAULT_TERMINAL_THEME, TerminalTheme
from rich.text import Text
from tomlkit.items import String, StringType, Trivia

import protostar.cli
from protostar.config import DEFAULT_CONFIG_CONTENT, TemplateBlueprint, UserConfig
from protostar.errors import WorkspaceCollisionError
from protostar.fs import atomic_write_text
from protostar.manifest import DiagnosticEvent, EnvironmentManifest, Severity
from protostar.metadata import METADATA_FIELDS
from protostar.models import ExecutionResult, InitRequest
from protostar.modules import (
    LICENSE_MAP,
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    RuffModule,
    SystemWorkspaceModule,
)
from protostar.orchestrator import Orchestrator

# Define matrices for combinatorial CLI execution scenarios
FIXTURES = {
    "cli": [
        [
            "--template",
            "cli",
            "--mypy",
            "--pytest",
            "--prek",
            "--markdownlint",
        ],
    ],
    "astro": [["--template", "astro"]],
    "ml": [["--template", "ml", "--docker"]],
    "ml_merged": [
        ["--template", "ml", "--docker"],
        ["--template", "astro", "--mypy", "--docker", "--force-merge"],
    ],
    "api": [["--template", "api"]],
    "dsp": [["--template", "dsp"]],
    "embedded": [["--template", "embedded"]],
}

# Resolve absolute path to prevent os.chdir() related pathing errors
FIXTURES_DIR = Path("docs/fixtures").resolve()


def _write_fixture(filepath: str | Path, content: str) -> None:
    """Writes raw unformatted content to a fixture file in the documentation fixtures directory.

    Args:
        filepath: Target filename or Path relative to fixtures or absolute.
        content: Raw string data to write to disk.
    """
    output_path = FIXTURES_DIR / filepath if isinstance(filepath, str) else filepath

    content = content.rstrip() + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, content)


def _freeze_pyproject_deps(old_content: str, new_content: str) -> str:
    """Preserves dependency versions from an existing pyproject.toml.

    Prevents arbitrary diff churn during documentation regeneration by extracting
    and injecting prior semantic version pins into the newly generated payload.

    Args:
        old_content: Existing documentation fixture string.
        new_content: Newly generated configuration string.

    Returns:
        The updated string containing the frozen dependency versions.
    """
    frozen_deps: dict[str, str] = dict(
        re.findall(r'"([a-zA-Z0-9_-]+)>=([^"]+)"', old_content)
    )

    def repl_deps(match: re.Match[str]) -> str:
        package_name = match.group(1)
        new_version = match.group(2)
        frozen_version = frozen_deps.get(package_name, new_version)
        return f'"{package_name}>={frozen_version}"'

    return re.sub(r'"([a-zA-Z0-9_-]+)>=([^"]+)"', repl_deps, new_content)


def _freeze_pre_commit_hooks(old_content: str, new_content: str) -> str:
    """Preserves Git hook revisions from an existing .pre-commit-config.yaml.

    Prevents unnecessary documentation churn by extracting prior repository
    revisions and injecting them into the new configuration string.

    Args:
        old_content: Existing documentation fixture string.
        new_content: Newly generated configuration string.

    Returns:
        The updated string containing the frozen Git hook revisions.
    """
    frozen_hooks: dict[str, str] = dict(
        re.findall(r"repo:\s*([^\n]+)\n\s*rev:\s*([^\n]+)", old_content)
    )

    def repl_hooks(match: re.Match[str]) -> str:
        repo_url = match.group(1)
        indentation = match.group(2)
        new_rev = match.group(3)
        frozen_rev = frozen_hooks.get(repo_url, new_rev)
        return f"repo: {repo_url}\n{indentation}rev: {frozen_rev}"

    return re.sub(r"repo:\s*([^\n]+)\n(\s*)rev:\s*([^\n]+)", repl_hooks, new_content)


def _format_markdown_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> str:
    """Constructs a Markdown-formatted table from headers and row values.

    Args:
        headers: Sequence of column header names.
        rows: Sequence containing the row data.

    Returns:
        A valid Markdown table string.
    """
    header_row = f"| {' | '.join(headers)} |"
    separator_row = f"| {' | '.join([':---'] * len(headers))} |"

    table = [header_row, separator_row]
    for row in rows:
        table.append(f"| {' | '.join(row)} |")

    return "\n".join(table)


class ManifestEncoder(json.JSONEncoder):
    """Custom JSON serialization encoder for the EnvironmentManifest datastructure."""

    def default(self, obj: Any) -> Any:
        """Overrides the default JSON encoder for custom data types."""
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


def generate_default_config() -> None:
    """Writes the default global TOML configuration to a documentation fixture."""
    _write_fixture("default_config.toml", DEFAULT_CONFIG_CONTENT)


def generate_template_schema_fixture() -> None:
    """Dynamically generates an annotated TOML template schema fixture from internal definitions."""
    doc = tomlkit.document()

    doc.add(
        tomlkit.comment(
            "=============================================================================="
        )
    )
    doc.add(tomlkit.comment("Protostar Template Specification Schema"))
    doc.add(
        tomlkit.comment(
            "=============================================================================="
        )
    )
    doc.add(tomlkit.nl())

    def _multiline_literal(content: str) -> String:
        clean = content.strip("\r\n")
        return String(
            StringType.MLL,
            clean,
            f"\n{clean}\n",
            Trivia(),
        )

    def _python_to_tomlkit(val: Any) -> Any:
        if isinstance(val, list):
            if not val:
                return tomlkit.array()
            if isinstance(val[0], list):
                arr = tomlkit.array()
                for item in val:
                    sub_arr = tomlkit.array()
                    sub_arr.extend(item)
                    arr.append(sub_arr)
                arr.multiline(True)
                return arr
            arr = tomlkit.array()
            arr.extend(val)
            arr.multiline(True)
            return arr
        if isinstance(val, dict):
            table = tomlkit.table()
            for k, v in val.items():
                if isinstance(v, str) and ("\n" in v or "'''" in v or '"""' in v):
                    table.add(k, _multiline_literal(v))
                elif isinstance(v, list):
                    arr = tomlkit.array()
                    arr.extend(v)
                    table.add(k, arr)
                else:
                    table.add(k, v)
            return table
        return val

    blueprint_fields = list(fields(TemplateBlueprint))
    table_fields = {"files", "pyproject_injections", "appends", "dev"}
    ordered_fields = [f for f in blueprint_fields if f.name not in table_fields] + [
        f for f in blueprint_fields if f.name in table_fields
    ]

    for f in ordered_fields:
        if "description" in f.metadata:
            if f.name == "dependencies":
                doc.add(tomlkit.comment("--- Dependencies ---"))
            elif f.name == "directories":
                doc.add(tomlkit.comment("--- Directory Architecture ---"))
            elif f.name == "vcs_ignores":
                doc.add(tomlkit.comment("--- Version Control Ignores ---"))
            elif f.name == "system_tasks":
                doc.add(tomlkit.comment("--- Subprocess Tasks ---"))
            elif f.name == "files":
                doc.add(tomlkit.comment("--- Static File Injections ---"))
            elif f.name == "pyproject_injections":
                doc.add(tomlkit.comment("--- pyproject.toml AST Injections ---"))
            elif f.name == "appends":
                doc.add(tomlkit.comment("--- File Appends ---"))
            elif f.name == "tooling_overrides":
                doc.add(tomlkit.comment("--- Tooling Opinions & Overrides ---"))

            doc.add(tomlkit.comment(f.metadata["description"]))

        if f.name == "tooling_overrides":
            doc.add(
                tomlkit.comment(
                    "Dynamic precedence: CLI Flags > Template Opinions > Global UserConfig"
                )
            )
            tooling_keys = sorted(
                [mod.config_key for mod in TOOLING_MODULES if mod.config_key]
            )
            for key in tooling_keys:
                default_val = key in ("ruff", "pytest")
                doc.add(key, default_val)
            doc.add(tomlkit.nl())
            continue

        if "example" in f.metadata:
            example = f.metadata["example"]
            if f.name == "pyproject_injections":
                dev_table = tomlkit.table()
                dev_table.add("pyproject", _python_to_tomlkit(example))
                doc.add("dev", dev_table)
            else:
                doc.add(f.name, _python_to_tomlkit(example))
            doc.add(tomlkit.nl())

    out_str = doc.as_string().strip() + "\n"
    _write_fixture("template_schema.toml", out_str)


def generate_capability_tables() -> None:
    """Generates Markdown tables detailing modules, templates, and their CLI footprints."""

    def _format_flags(flags: tuple[str, ...]) -> str:
        return ", ".join(f"`{f}`" for f in flags) if flags else "*None*"

    # Tooling integration matrix
    tool_headers = ["Tooling Module", "CLI Flags", "Description", "Collision Markers"]
    tool_rows = [
        [
            mod.name,
            _format_flags(mod.cli_flags),
            mod.cli_help,
            ", ".join(f"`{m.name}`" for m in mod.collision_markers) or "*None*",
        ]
        for mod in TOOLING_MODULES
    ]
    _write_fixture("table_tooling.md", _format_markdown_table(tool_headers, tool_rows))

    # Built-in Template matrix (scanned directly from protostar/templates)
    template_headers = ["Template", "Invocation", "Dependencies"]
    template_rows = []

    try:
        templates_dir = importlib.resources.files("protostar.templates")
        for item in sorted(templates_dir.iterdir(), key=lambda p: p.name):
            if item.is_file() and item.name.endswith(".toml"):
                name = item.name[:-5]
                content = tomllib.loads(item.read_text(encoding="utf-8"))
                deps = content.get("dependencies", [])
                deps_formatted = ", ".join(f"`{d}`" for d in deps) if deps else "*None*"
                template_rows.append(
                    [
                        f"`{name}`",
                        f"`protostar init --template {name}`",
                        deps_formatted,
                    ]
                )
    except Exception as e:
        print(f"Warning: Failed to load built-in templates: {e}")

    _write_fixture(
        "table_templates.md", _format_markdown_table(template_headers, template_rows)
    )

    # Interactive wizard project metadata fields matrix
    metadata_headers = ["Key", "Label", "Prompt Type", "Default"]
    metadata_rows = []
    for key, field in METADATA_FIELDS.items():
        if field.default is None or field.default == "":
            default_str = "*None*"
        elif isinstance(field.default, list):
            default_str = f"`{', '.join(field.default)}`"
        else:
            default_str = f"`{field.default}`"

        metadata_rows.append(
            [
                f"`{key}`",
                field.label.replace(" (optional, press Enter to skip):", "").replace(
                    ":", ""
                ),
                f"`{field.prompt_type}`",
                default_str,
            ]
        )
    _write_fixture(
        "table_metadata.md", _format_markdown_table(metadata_headers, metadata_rows)
    )

    # License mappings matrix
    license_headers = ["License Identifier", "License File", "PyPI Trove Classifier"]
    license_rows = [
        [
            f"`{license_key}`",
            f"`{filename}`",
            f"`{classifier}`",
        ]
        for license_key, (filename, classifier) in LICENSE_MAP.items()
    ]
    _write_fixture(
        "table_licenses.md", _format_markdown_table(license_headers, license_rows)
    )

    # CLI Global options table
    global_headers = ["Flag", "Shorthand", "Description"]
    global_rows = [
        [
            "`--json`",
            "*None*",
            "Position-independent flag. Emits structured JSON to `stdout` and redirects human-readable logging to `stderr`.",
        ],
        [
            "`--dry-run`",
            "*None*",
            "Executes the read-only `plan()` phase to preview planned files, AST merges, and system tasks without touching disk.",
        ],
        [
            "`--verbose`",
            "`-v`",
            "Enables debug-level logging and uncapped Python tracebacks for triage.",
        ],
        [
            "`--version`",
            "*None*",
            "Displays the installed Protostar version string.",
        ],
        [
            "`--help`",
            "`-h`",
            "Displays top-level help and available subcommands.",
        ],
    ]
    _write_fixture(
        "table_cli_global.md",
        _format_markdown_table(global_headers, global_rows),
    )

    # Configuration Environment Settings Table
    config_env_headers = ["Setting", "Type", "Description"]
    config_env_rows = []

    if UserConfig.__doc__:
        doc_lines = UserConfig.__doc__.splitlines()
        in_attributes = False
        for line in doc_lines:
            line = line.strip()
            if line == "Attributes:":
                in_attributes = True
                continue
            if in_attributes and line:
                if ":" in line:
                    # Format: key (type): Description
                    attr_part, desc_part = line.split(":", 1)
                    if "(" in attr_part and ")" in attr_part:
                        attr_name = attr_part.split("(")[0].strip()
                        typ = attr_part.split("(")[1].split(")")[0].strip()
                        desc = desc_part.strip()

                        # Only include simple types or well-known ones for the documentation
                        if attr_name != "templates":
                            # Format type for markdown, wrapping individual components in backticks so pipes stay outside code spans
                            if "IDEType" in typ:
                                typ_formatted = '`"vscode"` \\| `"cursor"` \\| `"none"`'
                            else:
                                typ_formatted = " \\| ".join(
                                    f"`{part.strip()}`" for part in typ.split("|")
                                )
                            config_env_rows.append(
                                [f"`{attr_name}`", typ_formatted, desc]
                            )

    _write_fixture(
        "table_config_env.md",
        _format_markdown_table(config_env_headers, config_env_rows),
    )

    # CLI init core options table
    init_core_headers = ["Option", "Shorthand", "Description"]
    init_core_rows = [
        [
            "`--template <NAME>`",
            "`-t <NAME>`",
            "Scaffold from a built-in template or a registered global alias.",
        ],
        [
            "`--from <TARGET>`",
            "*None*",
            "Scaffold from a local file/directory, raw TOML URL, or remote Git repository archive (`.zip`, `.tar.gz`).",
        ],
        [
            "`--list-templates`",
            "*None*",
            "Lists all available built-in templates and configured global aliases.",
        ],
        [
            "`--python-version <VER>`",
            "*None*",
            "Override the target Python version for this initialization (e.g. `3.13`).",
        ],
        [
            "`--force-merge`",
            "*None*",
            "Non-destructively deep-merge configurations and ignores into existing workspace files without prompting.",
        ],
        [
            "`--force-replace`",
            "*None*",
            "Forcefully overwrite colliding workspace configuration files without prompting.",
        ],
    ]
    _write_fixture(
        "table_cli_init_core.md",
        _format_markdown_table(init_core_headers, init_core_rows),
    )

    # CLI tooling flags table
    tooling_flags_headers = ["Enable Flag", "Disable Flag", "Description"]
    tooling_flags_rows = [
        [
            f"`{mod.cli_flags[0]}`",
            f"`{mod.cli_flags[0].replace('--', '--no-', 1)}`",
            mod.cli_help,
        ]
        for mod in TOOLING_MODULES
        if mod.cli_flags
    ]
    tooling_flags_rows.append(
        [
            "`--docker`",
            "`--no-docker`",
            "Multi-stage `Dockerfile` and `.dockerignore` container scaffolding",
        ]
    )
    _write_fixture(
        "table_cli_tooling_flags.md",
        _format_markdown_table(tooling_flags_headers, tooling_flags_rows),
    )

    # CLI config options table
    config_headers = ["Option", "Description"]
    config_rows = [
        [
            "*(No args)*",
            "Opens `config.toml` in your system's default `$EDITOR`.",
        ],
        [
            "`--reset`",
            "Resets configuration to factory defaults (prompts for confirmation).",
        ],
        [
            "`--force-replace`",
            "Bypasses the confirmation prompt when used with `--reset`.",
        ],
    ]
    _write_fixture(
        "table_cli_config.md",
        _format_markdown_table(config_headers, config_rows),
    )

    # CLI export-schema options table
    export_schema_headers = ["Option", "Description"]
    export_schema_rows = [
        [
            "*(No args)*",
            "Pretty-prints the syntax-highlighted schema to the terminal.",
        ],
        [
            "`--json`",
            "Emits raw JSON schema for piping to files or schema validators.",
        ],
    ]
    _write_fixture(
        "table_cli_export_schema.md",
        _format_markdown_table(export_schema_headers, export_schema_rows),
    )

    # POSIX exit codes table
    exit_code_headers = ["Code", "POSIX Name", "Trigger Condition"]
    exit_code_rows = [
        ["`0`", "`EX_OK`", "Successful execution"],
        ["`1`", "Generic", "Subprocess failure or command timeout"],
        ["`64`", "`os.EX_USAGE`", "Invalid CLI arguments or command usage syntax"],
        [
            "`65`",
            "`os.EX_DATAERR`",
            "Template resolution error (corrupted archive, missing variables)",
        ],
        [
            "`69`",
            "`os.EX_UNAVAILABLE`",
            "Missing required system binary (`uv`, `git`, etc.)",
        ],
        [
            "`70`",
            "`os.EX_SOFTWARE`",
            "Unhandled internal Python bug (prompts automated bug report)",
        ],
        [
            "`74`",
            "`os.EX_IOERR`",
            "Local filesystem read/write or permission failure",
        ],
        [
            "`75`",
            "`os.EX_TEMPFAIL`",
            "Transient network failure during remote template download",
        ],
        [
            "`77`",
            "`os.EX_NOPERM`",
            "Security violation (e.g., path traversal Zip Slip)",
        ],
        [
            "`78`",
            "`os.EX_CONFIG`",
            "Invalid TOML syntax or conflicting CLI configuration",
        ],
        [
            "`130`",
            "Shell Signal",
            "You aborted interactive wizard prompt (Ctrl+C)",
        ],
    ]
    _write_fixture(
        "table_exit_codes.md",
        _format_markdown_table(exit_code_headers, exit_code_rows),
    )


def generate_manifest_state() -> None:
    """Simulates an initialization sequence to compute a deterministic JSON manifest."""
    manifest = EnvironmentManifest()

    # Simulate: `protostar init --template astro --ruff`
    bootstrap_mods: list[BootstrapModule] = [PythonCore(), RuffModule()]
    for b_mod in bootstrap_mods:
        b_mod.build(manifest)

    # Load and apply the built-in astro template
    target = importlib.resources.files("protostar.templates").joinpath("astro.toml")
    if target.is_file():
        blueprint = TemplateBlueprint.load(str(target))
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
        for filepath, content in blueprint.files.items():
            manifest.filesystem.add_file_injection(filepath, content)
        for payload in blueprint.pyproject_injections.values():
            manifest.filesystem.add_file_append("pyproject.toml", payload)

    # Override machine-specific IDE paths to guarantee stable JSON diffs in CI
    manifest.ide_settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }

    state_json = json.dumps(manifest, cls=ManifestEncoder, indent=4)
    _write_fixture("manifest_state.json", state_json)


def generate_agent_payloads() -> None:
    """Generates JSON payloads for the Agent & Machine Interface documentation."""
    # 1. Planned payload computed dynamically from an EnvironmentManifest
    manifest = EnvironmentManifest(
        metadata={
            "description": "High-velocity CLI application.",
            "author_name": "Demo Author",
            "license": "MIT",
        }
    )
    bootstrap_mods: list[BootstrapModule] = [
        SystemWorkspaceModule(),
        PythonCore(),
        RuffModule(),
    ]
    for b_mod in bootstrap_mods:
        b_mod.build(manifest)

    # Set mock IDE settings for stable deterministic fixtures
    manifest.ide_settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }

    planned_payload = {
        "api_version": protostar.cli.CLI_API_VERSION,
        "status": "planned",
        "manifest": manifest.to_dict(),
    }
    _write_fixture("agent_payload_planned.json", json.dumps(planned_payload, indent=2))

    # 2. Success payload generated dynamically using ExecutionResult
    result = ExecutionResult(
        touched_paths=frozenset(
            [
                ".gitignore",
                "pyproject.toml",
                "src/my_app/__init__.py",
                "tests/test_cli.py",
            ]
        ),
        diagnostics=(),
    )
    success_payload = {
        "api_version": protostar.cli.CLI_API_VERSION,
        "status": "success",
        "result": result.to_dict(),
    }
    _write_fixture("agent_payload_success.json", json.dumps(success_payload, indent=2))

    # 3. Error payload generated dynamically using WorkspaceCollisionError
    err = WorkspaceCollisionError(paths=frozenset([Path("pyproject.toml")]))
    error_dict: dict[str, Any] = {
        "type": type(err).__name__,
        "message": str(err),
    }
    if err.hint:
        error_dict["hint"] = err.hint
    if err.docs_url:
        error_dict["docs_url"] = err.docs_url
    if isinstance(err, WorkspaceCollisionError):
        error_dict["paths"] = sorted(str(p) for p in err.paths)

    error_payload = {
        "api_version": protostar.cli.CLI_API_VERSION,
        "status": "error",
        "error": error_dict,
    }
    _write_fixture("agent_payload_error.json", json.dumps(error_payload, indent=2))


def generate_tree(dir_path: Path) -> str:
    """Executes the tree CLI utility to generate a clean directory structure text representation."""
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    result = subprocess.run(
        [
            "tree",
            "-a",
            "-I",
            ".git",
            "--gitignore",
            "--noreport",
            "--charset=utf-8",
            ".",
        ],
        cwd=dir_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def _execute_fixture_scenario(
    commands: list[list[str]], cwd: Path, env: dict[str, str]
) -> None:
    """Executes a defined sequence of Protostar commands within an isolated environment.

    Args:
        commands: Argument vectors to pass to the CLI.
        cwd: Target directory for execution.
        env: Isolated environment variables map.
    """
    for flags in commands:
        try:
            subprocess.run(
                ["protostar", "init", *flags],
                cwd=cwd,
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Scenario command failed: {' '.join(e.cmd)}", file=sys.stderr)
            if e.stdout:
                print(f"STDOUT:\n{e.stdout}", file=sys.stderr)
            if e.stderr:
                print(f"STDERR:\n{e.stderr}", file=sys.stderr)
            raise


def _extract_and_write_targets(source_dir: Path, fixture_name: str) -> None:
    """Extracts target files from a completed execution scenario and writes them to disk.

    Args:
        source_dir: Populated workspace directory containing generated artifacts.
        fixture_name: Prefix assigned to the output documentation fixtures.
    """
    tree_output = generate_tree(source_dir)
    _write_fixture(f"tree_{fixture_name}.txt", tree_output)

    for file_path in sorted(source_dir.rglob("*")):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(source_dir)
        # Exclude VCS internal databases, ephemeral cache artifacts, and lockfiles
        if any(
            part
            in (
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                ".ruff_cache",
                ".mypy_cache",
                "uv.lock",
            )
            for part in rel_path.parts
        ):
            continue

        target_rel_path = rel_path
        if rel_path.name == ".pre-commit-config.yaml":
            target_rel_path = rel_path.with_name("pre-commit-config.fixture.yaml")

        target_path = FIXTURES_DIR / fixture_name / target_rel_path
        content = file_path.read_text(encoding="utf-8")

        # Freeze mutable dependencies and VCS revisions if updating an existing file
        if target_path.exists():
            old_content = target_path.read_text(encoding="utf-8")

            if rel_path.name == "pyproject.toml":
                content = _freeze_pyproject_deps(old_content, content)
            elif target_rel_path.name == "pre-commit-config.fixture.yaml":
                content = _freeze_pre_commit_hooks(old_content, content)
        elif target_rel_path.name == "pre-commit-config.fixture.yaml":
            legacy_target = FIXTURES_DIR / fixture_name / rel_path
            if legacy_target.exists():
                old_content = legacy_target.read_text(encoding="utf-8")
                content = _freeze_pre_commit_hooks(old_content, content)

        _write_fixture(target_path, content)


def _get_host_uv_cache_dir() -> Path:
    """Resolves the user's host uv cache directory for sharing with isolated environments."""
    if env_dir := os.environ.get("UV_CACHE_DIR"):
        return Path(env_dir).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "uv"
    if sys.platform == "win32":
        local_app_data = os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )
        return Path(local_app_data) / "uv" / "cache"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "uv"
    return Path.home() / ".cache" / "uv"


def _build_fixture_scenario(
    name: str,
    commands: list[list[str]],
    clean_env: dict[str, str],
    host_cache_dir: str,
) -> None:
    """Builds a single fixture scenario in an isolated temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # --- Override host config paths for the subprocess ---
        isolated_env = clean_env.copy()
        isolated_env["HOME"] = tmpdir
        isolated_env["USERPROFILE"] = tmpdir
        isolated_env["XDG_CONFIG_HOME"] = tmpdir
        isolated_env["UV_CACHE_DIR"] = host_cache_dir
        isolated_env["UV_NO_PROGRESS"] = "1"

        # Create a static working directory to prevent random project names
        static_cwd = Path(tmpdir) / "demo_project"
        static_cwd.mkdir()

        _execute_fixture_scenario(commands, static_cwd, isolated_env)
        _extract_and_write_targets(static_cwd, name)
        print(f"  ✔ Scenario [{name}] fixtures generated")


def build_fixtures() -> None:
    """Iterates through predefined scenarios concurrently and extracts artifacts."""
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    cache_path = _get_host_uv_cache_dir()
    cache_path.mkdir(parents=True, exist_ok=True)
    host_cache_dir = str(cache_path)

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                _build_fixture_scenario, name, commands, clean_env, host_cache_dir
            )
            for name, commands in FIXTURES.items()
        ]
        for future in futures:
            future.result()


def generate_cli_help_svgs() -> None:
    """Captures isolated SVG snapshots of the Protostar CLI help menus via Rich."""
    original_global_console = protostar.cli.console
    original_formatter_console = getattr(
        protostar.cli.ProtoHelpFormatter, "console", None
    )

    def _render_svg(
        target_parser: argparse.ArgumentParser, prompt_cmd: str, filename: str
    ) -> None:
        """Records terminal output and exports the resulting render to an SVG file."""
        record_console = Console(
            record=True,
            width=100,
            force_terminal=True,
            color_system="truecolor",
            legacy_windows=False,
            file=io.StringIO(),
        )

        prompt = Text.assemble(
            ("❯ ", "bold magenta"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{prompt_cmd}\n", "white"),
        )
        record_console.print(prompt)

        # Dispatch based on the parser's structure to handle custom table
        # rendering versus standard rich-argparse string formatting.
        is_custom_table = (
            hasattr(target_parser, "print_help")
            and hasattr(target_parser.print_help, "__func__")
            and target_parser.print_help.__func__.__name__ == "print_table_help"
        )

        if is_custom_table:
            protostar.cli.console = record_console
            target_parser.print_help()
        else:
            protostar.cli.ProtoHelpFormatter.console = record_console  # type: ignore[method-assign, assignment]
            ansi_str = target_parser.format_help()
            record_console.print(Text.from_ansi(ansi_str, no_wrap=True))

        # Re-map primary colors to match project theme defaults
        ansi_colors = [
            (color.red, color.green, color.blue)
            for color in DEFAULT_TERMINAL_THEME.ansi_colors  # type: ignore[attr-defined]
        ]
        ansi_colors[4] = (97, 175, 239)
        ansi_colors[12] = (97, 175, 239)
        ansi_colors[6] = (34, 211, 238)
        ansi_colors[14] = (34, 211, 238)

        protostar_theme = TerminalTheme(
            background=(10, 15, 31),
            foreground=(220, 225, 235),
            normal=ansi_colors[:8],
            bright=ansi_colors[8:16],
        )

        svg_content = record_console.export_svg(
            title="zsh",
            theme=protostar_theme,
            unique_id=filename.replace(".svg", ""),
        )

        clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
        _write_fixture(filename, clean_svg)

    try:
        parser = protostar.cli.build_parser()

        # Generate base root help SVG
        _render_svg(parser, "help", "cli_help.svg")

        # Generate specific subparser help SVG if available
        subparsers = next(
            (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
            None,
        )
        if subparsers and "init" in subparsers.choices:
            init_parser = subparsers.choices["init"]
            _render_svg(init_parser, "help init", "cli_init_help.svg")

        if subparsers and "config" in subparsers.choices:
            config_parser = subparsers.choices["config"]
            _render_svg(config_parser, "help config", "cli_config_help.svg")

    finally:
        # Restore the native consoles
        protostar.cli.console = original_global_console
        if original_formatter_console is None:
            protostar.cli.ProtoHelpFormatter.console = None  # type: ignore[assignment]
        else:
            protostar.cli.ProtoHelpFormatter.console = original_formatter_console  # type: ignore[method-assign]


def generate_cli_dry_run_svg() -> None:
    """Captures an SVG snapshot of the dry-run CLI telemetry preview via Rich."""
    original_global_console = protostar.cli.console

    record_console = Console(
        record=True,
        width=100,
        force_terminal=True,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
    )

    prompt = Text.assemble(
        ("❯ ", "bold magenta"),  # noqa: RUF001
        ("protostar ", "bold cyan"),
        ("init --template cli --dry-run\n", "white"),
    )
    record_console.print(prompt)

    try:
        protostar.cli.console = record_console

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                target = importlib.resources.files("protostar.templates").joinpath(
                    "cli.toml"
                )
                blueprint = TemplateBlueprint.load(str(target))
                user_config = UserConfig()
                modules: list[BootstrapModule] = [
                    SystemWorkspaceModule(),
                    PythonCore(),
                ]
                for mod in TOOLING_MODULES:
                    is_active = getattr(user_config, mod.config_key, False)
                    if blueprint and mod.config_key in blueprint.tooling_overrides:
                        is_active = blueprint.tooling_overrides[mod.config_key]
                    if is_active:
                        modules.append(mod)

                request = InitRequest(template_blueprint=blueprint)
                engine = Orchestrator(modules, user_config, request=request)
                manifest = engine.plan()
                protostar.cli._print_dry_run_summary(manifest)
            finally:
                os.chdir(orig_cwd)

        ansi_colors = [
            (color.red, color.green, color.blue)
            for color in DEFAULT_TERMINAL_THEME.ansi_colors  # type: ignore[attr-defined]
        ]
        ansi_colors[4] = (97, 175, 239)
        ansi_colors[12] = (97, 175, 239)
        ansi_colors[6] = (34, 211, 238)
        ansi_colors[14] = (34, 211, 238)

        protostar_theme = TerminalTheme(
            background=(10, 15, 31),
            foreground=(220, 225, 235),
            normal=ansi_colors[:8],
            bright=ansi_colors[8:16],
        )

        svg_content = record_console.export_svg(
            title="zsh",
            theme=protostar_theme,
            unique_id="cli_dry_run",
        )

        clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
        _write_fixture("cli_dry_run.svg", clean_svg)
    finally:
        protostar.cli.console = original_global_console


def generate_diagnostic_panel_svg() -> None:
    """Captures an SVG snapshot of a styled Rich Diagnostic Summary panel."""
    record_console = Console(
        record=True,
        width=90,
        force_terminal=True,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
    )

    events = [
        DiagnosticEvent(
            phase="Git",
            message="Initialized fresh git repository in workspace.",
            severity=Severity.INFO,
        ),
        DiagnosticEvent(
            phase="Direnv",
            message="Auto-activation hook skipped; binary not found in PATH.",
            severity=Severity.SKIP,
            detail="Install direnv to enable seamless directory traversal activation.",
        ),
        DiagnosticEvent(
            phase="MarkdownLint",
            message="Linter configuration scaffolded with relaxed schema rules.",
            severity=Severity.WARNING,
            detail="Install markdownlint-cli2 to enable git hook verification.",
        ),
    ]

    lines = []
    has_warnings = False

    for event in events:
        if event.severity == Severity.WARNING:
            has_warnings = True
            lines.append(f"[yellow]⚠ [{event.phase}][/yellow] {event.message}")
        elif event.severity == Severity.SKIP:
            lines.append(
                rf"[dim white]\[i] [{event.phase}] {event.message}[/dim white]"
            )
        else:
            lines.append(f"[blue]• [{event.phase}][/blue] {event.message}")

        if event.detail:
            lines.append(f"  [dim]{event.detail}[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="[bold]Diagnostic Summary",
        border_style="yellow" if has_warnings else "blue",
        expand=False,
        padding=(1, 2),
    )

    record_console.print(panel)

    ansi_colors = [
        (color.red, color.green, color.blue)
        for color in DEFAULT_TERMINAL_THEME.ansi_colors  # type: ignore[attr-defined]
    ]
    ansi_colors[4] = (97, 175, 239)
    ansi_colors[12] = (97, 175, 239)
    ansi_colors[6] = (34, 211, 238)
    ansi_colors[14] = (34, 211, 238)

    protostar_theme = TerminalTheme(
        background=(10, 15, 31),
        foreground=(220, 225, 235),
        normal=ansi_colors[:8],
        bright=ansi_colors[8:16],
    )

    svg_content = record_console.export_svg(
        title="Diagnostic Telemetry",
        theme=protostar_theme,
        unique_id="diagnostic_panel",
    )

    clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
    _write_fixture("diagnostic_panel.svg", clean_svg)


def main() -> None:
    """Primary execution pipeline for documentation artifact generation."""
    parser = argparse.ArgumentParser(description="Generate documentation fixtures.")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow combinatorial subprocess executions (e.g., Protostar init).",
    )
    args = parser.parse_args()

    # --- Isolate in-process configuration ---
    # Monkeypatch the config path so in-process calls (like generate_manifest_state)
    # evaluate against a missing file and default to base settings.
    import protostar.config

    protostar.config.CONFIG_FILE = (
        Path(tempfile.gettempdir()) / "non_existent_protostar_config.toml"
    )
    protostar.config.UserConfig._instance = None

    try:
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

        print("Generating static documentation fixtures...")
        generate_cli_help_svgs()
        generate_cli_dry_run_svg()
        generate_default_config()
        generate_capability_tables()
        generate_manifest_state()
        generate_agent_payloads()
        generate_template_schema_fixture()
        generate_diagnostic_panel_svg()
        print("✔ Static fixtures generated.\n")

        # Slow executions (disk I/O and subprocess isolation)
        if not args.fast:
            print("Generating scenario fixtures...")
            build_fixtures()
            print("✔ Scenario fixtures generated.")
        else:
            print("Skipping scenario fixture builds (--fast enabled).")

        print("\nDocumentation fixtures updated successfully!")

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting gracefully.")
        sys.exit(130)


if __name__ == "__main__":
    main()
