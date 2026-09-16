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
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import tomlkit
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from rich.cells import cell_len
from rich.console import Console
from rich.panel import Panel
from rich.segment import Segment
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


@dataclass(frozen=True)
class RegressionScenario:
    """Declarative specification for an end-to-end template regression scenario."""

    name: str
    commands: tuple[tuple[str, ...], ...]
    description: str
    seed_fn: Callable[[Path, dict[str, str]], None] | None = None


def _seed_ml_merged_foreign_content(cwd: Path, env: dict[str, str]) -> None:
    """Adds representative unowned content before the tracked ML rerun."""
    subprocess.run(
        [
            "uv",
            "add",
            "astropy",
            "astroquery",
            "nbdime",
            "photutils",
            "scipy",
            "specutils",
        ],
        cwd=cwd,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    for directory in ("data/catalogs", "data/fits"):
        (cwd / directory).mkdir(parents=True, exist_ok=True)
    with (cwd / ".gitignore").open("a", encoding="utf-8") as stream:
        stream.write("*.csv\n*.fit\n*.fits\n*.fts\n*.parquet\n")


# Define matrices for combinatorial CLI execution scenarios
# NOTE FOR MAINTAINERS:
# Template scenario fixtures should generally have NO flags other than `["--template", "<name>"]`
# to ensure fixtures reflect authentic, out-of-the-box default scaffolding output.
# The `ml` fixture is a purposeful exception to this rule: it includes `--docker` because
# `docs/usage/init.md` specifically showcases containerization for the ML stack and embeds
# the resulting `ml/Dockerfile` and `ml/.dockerignore` snippets into the documentation.
# `ml_merged` exercises same-template reinitialization with foreign workspace
# additions and newly managed tooling.
SCENARIOS: dict[str, RegressionScenario] = {
    "cli": RegressionScenario(
        name="cli",
        commands=(("--template", "cli"),),
        description="Default CLI application template with Typer and Rich.",
    ),
    "astro": RegressionScenario(
        name="astro",
        commands=(("--template", "astro"),),
        description="Astronomy template with scientific python dependencies and ASDF/FITS gitattributes.",
    ),
    "ml": RegressionScenario(
        name="ml",
        commands=(("--template", "ml", "--docker"),),
        description="Machine learning template with Docker containerization.",
    ),
    "ml_merged": RegressionScenario(
        name="ml_merged",
        commands=(
            ("--template", "ml", "--docker"),
            ("--template", "ml", "--mypy", "--docker", "--force-merge"),
        ),
        description="Same-template reinitialization exercising foreign workspace preservation and tooling adoption.",
        seed_fn=_seed_ml_merged_foreign_content,
    ),
    "api": RegressionScenario(
        name="api",
        commands=(("--template", "api"),),
        description="FastAPI application template.",
    ),
    "dsp": RegressionScenario(
        name="dsp",
        commands=(("--template", "dsp"),),
        description="Digital Signal Processing template with audio data sample layouts.",
    ),
    "embedded": RegressionScenario(
        name="embedded",
        commands=(("--template", "embedded"),),
        description="Embedded systems template with hardware board layout.",
    ),
}

FIXTURES: dict[str, list[list[str]]] = {
    name: [list(c) for c in s.commands] for name, s in SCENARIOS.items()
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


def _align_state_dependencies(state_content: str, pyproject_content: str) -> str:
    """Aligns state materializations with dependency versions frozen in a fixture."""
    project = tomllib.loads(pyproject_content)
    requirements: dict[tuple[str, str, str], str] = {}
    groups = {
        "main": project.get("project", {}).get("dependencies", []),
        **project.get("dependency-groups", {}),
    }
    for group, entries in groups.items():
        for entry in entries:
            if not isinstance(entry, str):
                continue
            requirement = Requirement(entry)
            marker = str(requirement.marker) if requirement.marker is not None else ""
            requirements[(group, canonicalize_name(requirement.name), marker)] = entry

    state = tomlkit.parse(state_content)
    for record in state.get("dependencies", []):
        identity = (record["group"], record["name"], record["marker"])
        if materialized := requirements.get(identity):
            record["materialized"] = materialized
    return tomlkit.dumps(state)


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

    def _get_module_scaffolded_files(mod: BootstrapModule) -> str:
        test_manifest = EnvironmentManifest()
        mod.build(test_manifest)
        files = sorted(test_manifest.filesystem.file_injections)
        if test_manifest.tooling.wants_hooks:
            files.append(".pre-commit-config.yaml")
        if test_manifest.tooling.wants_ci:
            files.append(".github/workflows/ci.yml")
        if test_manifest.tooling.wants_release:
            files.append(".github/workflows/release.yml")
        if test_manifest.tooling.wants_just:
            files.append("justfile")
        return ", ".join(f"`{f}`" for f in files) if files else "*None*"

    # Tooling integration matrix
    tool_headers = ["Tooling Module", "CLI Flags", "Description", "Scaffolded Files"]
    tool_rows = [
        [
            mod.name,
            _format_flags(mod.cli_flags),
            mod.cli_help,
            _get_module_scaffolded_files(mod),
        ]
        for mod in TOOLING_MODULES
    ]
    tool_rows.append(
        [
            "Docker",
            "`--docker`",
            "Multi-stage `Dockerfile` and `.dockerignore` container scaffolding",
            "`Dockerfile`, `.dockerignore`",
        ]
    )
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
            "`-f`, `--force`",
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

    # CLI completion options table
    completion_headers = ["Option", "Description"]
    completion_rows = [
        [
            "*(No args)*",
            "Displays tailored setup instructions for the detected shell environment.",
        ],
        [
            "`<shell>`",
            "Target shell (`bash`, `zsh`, `fish`, `powershell`). Emits the raw completion script to stdout.",
        ],
        [
            "`--json`",
            "Emits a structured JSON payload containing the shell script or list of supported shells.",
        ],
    ]
    _write_fixture(
        "table_cli_completion.md",
        _format_markdown_table(completion_headers, completion_rows),
    )

    # POSIX exit codes table
    exit_code_headers = [
        "Exit Code",
        "POSIX Name",
        "Exception Class",
        "Trigger Condition",
    ]
    exit_code_rows = [
        ["`0`", "`EX_OK`", "*None*", "Successful execution"],
        [
            "`1`",
            "Generic Exit",
            "`CommandExecutionError`<br>`CommandTimeoutError`",
            "Subprocess failure or command timeout",
        ],
        [
            "`64`",
            "`os.EX_USAGE`",
            "`InvalidUsageError`",
            "Invalid CLI arguments or command usage syntax",
        ],
        [
            "`65`",
            "`os.EX_DATAERR`",
            "`TemplateResolutionError`",
            "Template resolution error (corrupted archive, missing variables)",
        ],
        [
            "`69`",
            "`os.EX_UNAVAILABLE`",
            "`MissingDependencyError`<br>`AggregatedDependencyError`",
            "Missing required system binary (`uv`, `git`, etc.)",
        ],
        [
            "`70`",
            "`os.EX_SOFTWARE`",
            "*(Unhandled exception)*",
            "Unhandled internal Python bug (prompts automated bug report)",
        ],
        [
            "`74`",
            "`os.EX_IOERR`",
            "`FileSystemError`",
            "Local filesystem read/write or permission failure",
        ],
        [
            "`75`",
            "`os.EX_TEMPFAIL`",
            "`NetworkFetchError`",
            "Transient network failure during remote template download",
        ],
        [
            "`77`",
            "`os.EX_NOPERM`",
            "`SecurityViolationError`",
            "Security violation (e.g., path traversal Zip Slip)",
        ],
        [
            "`78`",
            "`os.EX_CONFIG`",
            "`ConfigurationError`",
            "Invalid TOML syntax or conflicting CLI configuration",
        ],
        [
            "`130`",
            "Shell Signal",
            "`ExecutionAbortedError`<br>`ExecutionInterruptedError`",
            "You aborted interactive wizard prompt or interrupted execution (Ctrl+C)",
        ],
    ]
    _write_fixture(
        "table_exit_codes.md",
        _format_markdown_table(exit_code_headers, exit_code_rows),
    )

    # Inject into CONTRIBUTING.md
    contributing_path = Path("CONTRIBUTING.md")
    if contributing_path.exists():
        contrib_content = contributing_path.read_text()
        markdown_table = _format_markdown_table(exit_code_headers, exit_code_rows)
        import re

        new_content = re.sub(
            r"<!-- BEGIN_EXIT_CODES -->.*<!-- END_EXIT_CODES -->",
            f"<!-- BEGIN_EXIT_CODES -->\n\n{markdown_table}\n\n<!-- END_EXIT_CODES -->",
            contrib_content,
            flags=re.DOTALL,
        )
        contributing_path.write_text(new_content)


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
        blueprint = TemplateBlueprint.load(str(target), built_in="astro")
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
        manifest.template_reference = blueprint.reference
        for identity, payload in blueprint.pyproject_injections.items():
            manifest.filesystem.add_structured(
                "pyproject.toml",
                payload,
                producer=f"template:{blueprint.reference.identity if blueprint.reference else 'unresolved'}:{identity}",
            )

    # Override machine-specific IDE paths to guarantee stable JSON diffs in CI
    manifest.ide_settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }

    state_json = json.dumps(manifest, cls=ManifestEncoder, indent=4)
    _write_fixture("manifest_state.json", state_json)


def generate_agent_payloads() -> None:
    """Generates JSON payloads for the Agent & Machine Interface documentation."""
    orig_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
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
                "api_version": protostar.cli.schema.CLI_API_VERSION,
                "status": "planned",
                "manifest": manifest.to_dict(),
            }
            _write_fixture(
                "agent_payload_planned.json", json.dumps(planned_payload, indent=2)
            )
        finally:
            os.chdir(orig_cwd)

    # 2. Success payload generated dynamically using ExecutionResult
    paths = frozenset(
        [
            ".gitignore",
            "pyproject.toml",
            "src/my_app/__init__.py",
            "tests/test_cli.py",
        ]
    )
    result = ExecutionResult(
        created_paths=paths,
        mutated_paths=frozenset(),
        diagnostics=(),
    )
    success_payload = {
        "api_version": protostar.cli.schema.CLI_API_VERSION,
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
        "api_version": protostar.cli.schema.CLI_API_VERSION,
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

    generated_pyproject = source_dir / "pyproject.toml"
    fixture_pyproject = FIXTURES_DIR / fixture_name / "pyproject.toml"
    frozen_pyproject: str | None = None
    if generated_pyproject.exists():
        frozen_pyproject = generated_pyproject.read_text(encoding="utf-8")
        if fixture_pyproject.exists():
            frozen_pyproject = _freeze_pyproject_deps(
                fixture_pyproject.read_text(encoding="utf-8"), frozen_pyproject
            )

    written_targets: set[Path] = set()
    for file_path in sorted(source_dir.rglob("*")):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(source_dir)
        # Exclude VCS databases, caches, and the external resolver lockfile.
        if any(
            part
            in (
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                ".ruff_cache",
                ".mypy_cache",
                ".rumdl_cache",
                "uv.lock",
            )
            for part in rel_path.parts
        ):
            continue

        target_rel_path = rel_path
        if rel_path.name == ".pre-commit-config.yaml":
            target_rel_path = rel_path.with_name("pre-commit-config.fixture.yaml")

        target_path = FIXTURES_DIR / fixture_name / target_rel_path
        written_targets.add(target_path.resolve())
        content = file_path.read_text(encoding="utf-8")
        if rel_path.name == "pyproject.toml" and frozen_pyproject is not None:
            content = frozen_pyproject
        elif rel_path.name == ".protostar.lock.toml" and frozen_pyproject is not None:
            content = _align_state_dependencies(content, frozen_pyproject)

        # Freeze mutable dependencies and VCS revisions if updating an existing file
        if target_path.exists():
            old_content = target_path.read_text(encoding="utf-8")

            if target_rel_path.name == "pre-commit-config.fixture.yaml":
                content = _freeze_pre_commit_hooks(old_content, content)
        elif target_rel_path.name == "pre-commit-config.fixture.yaml":
            legacy_target = FIXTURES_DIR / fixture_name / rel_path
            if legacy_target.exists():
                old_content = legacy_target.read_text(encoding="utf-8")
                content = _freeze_pre_commit_hooks(old_content, content)

        _write_fixture(target_path, content)

    # Prune stale files no longer generated for this scenario
    fixture_root = FIXTURES_DIR / fixture_name
    if fixture_root.exists():
        for existing_file in list(fixture_root.rglob("*")):
            if (
                existing_file.is_file()
                and existing_file.resolve() not in written_targets
            ):
                existing_file.unlink()


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
    scenario: RegressionScenario,
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

        if scenario.seed_fn is not None:
            _execute_fixture_scenario(
                [list(c) for c in scenario.commands[:1]], static_cwd, isolated_env
            )
            scenario.seed_fn(static_cwd, isolated_env)
            _execute_fixture_scenario(
                [list(c) for c in scenario.commands[1:]], static_cwd, isolated_env
            )
        else:
            _execute_fixture_scenario(
                [list(c) for c in scenario.commands], static_cwd, isolated_env
            )
        _extract_and_write_targets(static_cwd, scenario.name)
        print(f"  ✔ Scenario [{scenario.name}] fixtures generated")


def build_fixtures(scenario_name: str | None = None) -> None:
    """Iterates through predefined scenarios concurrently and extracts artifacts."""
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    cache_path = _get_host_uv_cache_dir()
    cache_path.mkdir(parents=True, exist_ok=True)
    host_cache_dir = str(cache_path)

    if scenario_name is not None:
        if scenario_name not in SCENARIOS:
            valid = ", ".join(sorted(SCENARIOS.keys()))
            raise ValueError(
                f"Unknown scenario '{scenario_name}'. Valid options: {valid}"
            )
        target_scenarios = [SCENARIOS[scenario_name]]
    else:
        target_scenarios = list(SCENARIOS.values())

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                _build_fixture_scenario, scenario, clean_env, host_cache_dir
            )
            for scenario in target_scenarios
        ]
        for future in futures:
            future.result()


def _get_protostar_terminal_theme() -> TerminalTheme:
    """Constructs the standard Protostar dark terminal theme."""
    ansi_colors = [
        (color.red, color.green, color.blue)
        for color in DEFAULT_TERMINAL_THEME.ansi_colors  # type: ignore[attr-defined]
    ]
    ansi_colors[4] = (97, 175, 239)
    ansi_colors[12] = (97, 175, 239)
    ansi_colors[6] = (34, 211, 238)
    ansi_colors[14] = (34, 211, 238)

    return TerminalTheme(
        background=(10, 15, 31),
        foreground=(220, 225, 235),
        normal=ansi_colors[:8],
        bright=ansi_colors[8:16],
    )


def _calculate_content_width(console: Console, min_width: int = 1) -> int:
    """Calculates the maximum visible column width across all lines in the console buffer.

    Inspects rendered segments to determine the rightmost column occupied by visible
    text (excluding trailing whitespace) or styled background blocks, providing a
    deterministic width for shrinkwrapping without arbitrary diff churn.

    Args:
        console: The rich Console instance with recorded buffer segments.
        min_width: Minimum allowable width in columns. Defaults to 1.

    Returns:
        The maximum column width required to display the content without clipping.
    """
    segments = list(Segment.filter_control(console._record_buffer))
    lines = list(Segment.split_and_crop_lines(segments, length=10000, pad=False))
    max_col = 0
    for line in lines:
        current_col = 0
        line_max_col = 0
        for seg in line:
            text = seg.text
            if text == "\n":
                continue
            style = seg.style
            has_bg = False
            if style is not None:
                has_bg = bool(
                    style.reverse
                    or (style.bgcolor is not None and not style.bgcolor.is_default)
                )

            if has_bg:
                current_col += cell_len(text)
                line_max_col = current_col
            else:
                rstripped = text.rstrip()
                if rstripped:
                    line_max_col = current_col + cell_len(rstripped)
                current_col += cell_len(text)
        if line_max_col > max_col:
            max_col = line_max_col

    return max(max_col, min_width)


def _render_and_write_svg(
    console: Console,
    title: str,
    filename: str,
    unique_id: str | None = None,
) -> None:
    """Shrinkwraps recorded console output and writes a clean deterministic SVG fixture.

    Args:
        console: The rich Console instance with recorded buffer segments.
        title: Window title displayed in the SVG terminal chrome.
        filename: Destination SVG filename relative to FIXTURES_DIR.
        unique_id: Optional unique identifier for SVG CSS classes and IDs. Defaults to filename stem.
    """
    content_width = _calculate_content_width(console)
    if content_width > 0:
        console.width = content_width

    svg_content = console.export_svg(
        title=title,
        theme=_get_protostar_terminal_theme(),
        unique_id=unique_id or filename.replace(".svg", ""),
    )

    clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
    _write_fixture(filename, clean_svg)


def generate_cli_help_svgs() -> None:
    """Captures isolated SVG snapshots of the Protostar CLI help menus via Rich."""
    original_global_console = protostar.cli.ui.console

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
            _environ={},
        )

        prompt = Text.assemble(
            ("❯ ", "bold magenta"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{prompt_cmd}\n", "white"),
        )
        record_console.print(prompt)

        # All parsers are JsonAwareParser instances; route directly to print_table_help.
        protostar.cli.ui.console = record_console
        target_parser.print_help()

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename=filename,
            unique_id=filename.replace(".svg", ""),
        )

    try:
        parser = protostar.cli.parser.build_parser()

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
        # Restore the native console
        protostar.cli.ui.console = original_global_console


def generate_cli_dry_run_svg() -> None:
    """Captures an SVG snapshot of the dry-run CLI diagnostics preview via Rich."""
    original_global_console = protostar.cli.ui.console

    record_console = Console(
        record=True,
        width=100,
        force_terminal=True,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
        _environ={},
    )

    prompt = Text.assemble(
        ("❯ ", "bold magenta"),  # noqa: RUF001
        ("protostar ", "bold cyan"),
        ("init --template cli --dry-run\n", "white"),
    )
    record_console.print(prompt)

    try:
        protostar.cli.ui.console = record_console

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                target = importlib.resources.files("protostar.templates").joinpath(
                    "cli.toml"
                )
                blueprint = TemplateBlueprint.load(str(target), built_in="cli")
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
                protostar.cli.ui._print_dry_run_summary(manifest)
            finally:
                os.chdir(orig_cwd)

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_dry_run.svg",
            unique_id="cli_dry_run",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def generate_diagnostic_panel_svg() -> None:
    """Captures an SVG snapshot of a styled Rich Diagnostic Summary panel."""
    record_console = Console(
        record=True,
        width=90,
        force_terminal=True,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
        _environ={},
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

    _render_and_write_svg(
        record_console,
        title="Diagnostic Summary",
        filename="diagnostic_panel.svg",
        unique_id="diagnostic_panel",
    )


def generate_diff_fixtures() -> None:
    """Generates unified diffs between base and merged fixtures to illustrate progressive scaffolding."""
    import subprocess

    diff_targets = [
        ("ml", "ml_merged", "pyproject.toml"),
        ("ml", "ml_merged", ".gitignore"),
    ]

    for base, merged, filename in diff_targets:
        base_path = FIXTURES_DIR / base / filename
        merged_path = FIXTURES_DIR / merged / filename

        if base_path.exists() and merged_path.exists():
            result = subprocess.run(
                ["diff", "-u", str(base_path), str(merged_path)],
                capture_output=True,
                text=True,
            )
            diff_lines = result.stdout.splitlines()
            if len(diff_lines) >= 2:
                diff_lines[0] = f"--- a/{filename}"
                diff_lines[1] = f"+++ b/{filename}"
                clean_diff = "\n".join(line.rstrip() for line in diff_lines)

                safe_name = filename.replace(".", "_")
                output_name = f"diff_{base}_{merged}_{safe_name}.diff"
                _write_fixture(output_name, clean_diff)


def check_snapshot_drift(target_dir: Path) -> bool:
    """Verifies that the target fixture directory matches git HEAD.

    If drift is detected, prints the exact formatted diff and deterministic
    action instructions for LLM agents and human developers, then returns False.

    Args:
        target_dir: Directory to verify against git status and diff.

    Returns:
        True if target_dir has no drift against git HEAD, False otherwise.
    """
    rel_target = (
        target_dir.relative_to(Path.cwd())
        if target_dir.is_relative_to(Path.cwd())
        else target_dir
    )

    status_result = subprocess.run(
        ["git", "status", "--porcelain", str(rel_target)],
        capture_output=True,
        text=True,
        check=True,
    )
    status_output = status_result.stdout.strip()
    if not status_output:
        print(f"✔ All snapshots in {rel_target} match expected state.")
        return True

    diff_result = subprocess.run(
        ["git", "diff", "--color=never", str(rel_target)],
        capture_output=True,
        text=True,
        check=True,
    )
    diff_output = diff_result.stdout.strip()

    print("\n" + "=" * 80, file=sys.stderr)
    print(
        f"❌ SNAPSHOT REGRESSION DETECTED (Drift found in {rel_target}/)",
        file=sys.stderr,
    )
    print("=" * 80, file=sys.stderr)
    print("\nModified or untracked snapshot files:", file=sys.stderr)
    for line in status_output.splitlines():
        print(f"  {line}", file=sys.stderr)

    if diff_output:
        print("\n--- Unified Diff ---", file=sys.stderr)
        print(diff_output, file=sys.stderr)

    print("\n" + "=" * 80, file=sys.stderr)
    print("AGENT INSTRUCTIONS:", file=sys.stderr)
    print(
        "- If this diff is INTENDED (you updated templates, flags, or opinions):",
        file=sys.stderr,
    )
    print("    Stage the updated snapshots and commit:", file=sys.stderr)
    print(f"    git add {rel_target}/", file=sys.stderr)
    print(
        "- If this diff is an UNINTENDED REGRESSION:",
        file=sys.stderr,
    )
    print("    Discard modifications and fix your code:", file=sys.stderr)
    print(f"    git restore {rel_target}/", file=sys.stderr)
    print(f"    git clean -fd {rel_target}/", file=sys.stderr)
    print("=" * 80 + "\n", file=sys.stderr)

    return False


def main() -> None:
    """Primary execution pipeline for documentation artifact generation."""
    parser = argparse.ArgumentParser(description="Generate documentation fixtures.")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow combinatorial subprocess executions (e.g., Protostar init).",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Target a specific scenario name (e.g., 'cli', 'ml').",
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip automatic git drift verification after generation.",
    )
    args = parser.parse_args()

    # --- Isolate in-process configuration ---
    # Monkeypatch the config path so in-process calls (like generate_manifest_state)
    # evaluate against a missing file and default to base settings.
    import protostar.config

    protostar.config.CONFIG_FILE = (
        Path(tempfile.gettempdir()) / "non_existent_protostar_config.toml"
    )
    protostar.config.clear_user_config_cache()

    try:
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

        if not args.scenario:
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
            scenario_msg = f" [{args.scenario}]" if args.scenario else "s"
            print(f"Generating scenario fixture{scenario_msg}...")
            build_fixtures(scenario_name=args.scenario)
            generate_diff_fixtures()
            print("✔ Scenario fixtures generated.")
        else:
            print("Skipping scenario fixture builds (--fast enabled).")

        print("\nDocumentation fixtures updated successfully!")

        if not args.no_check:
            print("\nVerifying snapshot drift against git HEAD...")
            if not check_snapshot_drift(FIXTURES_DIR):
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting gracefully.")
        sys.exit(130)


if __name__ == "__main__":
    main()
