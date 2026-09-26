import argparse
import asyncio
import importlib.resources
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from unittest import mock

import tomlkit
from rich.cells import cell_len
from rich.console import Console
from rich.segment import Segment
from rich.text import Text
from tomlkit.items import String, StringType, Trivia

import protostar.cli
from protostar.cli.palette import ANSI
from protostar.config import (
    DEFAULT_CONFIG_CONTENT,
    TemplateBlueprint,
    TemplateSource,
    UserConfig,
)
from protostar.documents import community, pyproject
from protostar.errors import WorkspaceCollisionError
from protostar.fs import atomic_write_text
from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    EnvironmentManifest,
    Severity,
)
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
from protostar.system import ProcessRunner

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import (
    DOCS_GENERATED_DIR as DOCS_GENERATED_DIR,
)
from scripts._common import (
    DOCS_TERMINALS_DIR as DOCS_TERMINALS_DIR,
)
from scripts._common import (
    REPO_ROOT as REPO_ROOT,
)
from scripts._common import (
    SNAPSHOTS_DIR as SNAPSHOTS_DIR,
)


def _write_generated_doc(filepath: str | Path, content: str) -> None:
    """Writes raw unformatted content to a generated documentation file.

    Args:
        filepath: Target filename or Path relative to DOCS_GENERATED_DIR or absolute.
        content: Raw string data to write to disk.
    """
    output_path = (
        DOCS_GENERATED_DIR / filepath if isinstance(filepath, str) else filepath
    )
    content = content.rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, content)


def _format_markdown_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> str:
    """Constructs a Markdown-formatted table from headers and row values."""
    header_row = f"| {' | '.join(headers)} |"
    separator_row = f"| {' | '.join([':---'] * len(headers))} |"
    table = [header_row, separator_row]
    for row in rows:
        table.append(f"| {' | '.join(row)} |")
    return "\n".join(table)


class ManifestEncoder(json.JSONEncoder):
    """Custom JSON serialization encoder for the EnvironmentManifest datastructure."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (set, frozenset)):
            return sorted(obj)
        if isinstance(obj, Path):
            return obj.as_posix()
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj) and not isinstance(obj, type):
            return {
                f.name: getattr(obj, f.name)
                for f in fields(obj)
                if f.name
                not in {"observe", "producer_contributions", "selections", "recipe"}
            }
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


def _calculate_content_width(console: Console, min_width: int = 1) -> int:
    """Calculates the maximum visible column width across all lines in the console buffer."""
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
                # A heading's rule fills whatever width it is given; the export
                # crops it to the widest content instead.
                if rstripped and set(rstripped) != {"─"}:
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
    """Shrinkwraps recorded console output and writes a clean deterministic SVG to DOCS_TERMINALS_DIR."""
    content_width = _calculate_content_width(console)
    if content_width > 0:
        console.width = content_width

    svg_content = console.export_svg(
        title=title,
        theme=ANSI,
        unique_id=unique_id or filename.replace(".svg", ""),
    )

    clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
    output_path = DOCS_TERMINALS_DIR / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, clean_svg)


def generate_default_config() -> None:
    """Writes the default global TOML configuration to a generated documentation fixture."""
    _write_generated_doc("default_config.toml", DEFAULT_CONFIG_CONTENT)


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
                elif isinstance(v, dict):
                    table.add(k, _python_to_tomlkit(v))
                else:
                    table.add(k, v)
            return table
        return val

    blueprint_fields = list(fields(TemplateBlueprint))
    # Tables come last: root keys after a table header would belong to it.
    table_fields = {
        "files",
        "pyproject_injections",
        "appends",
        "dev",
        "options",
        "optional",
        "migrations",
    }
    ordered_fields = [f for f in blueprint_fields if f.name not in table_fields] + [
        f for f in blueprint_fields if f.name in table_fields
    ]

    # These live under the [dev] table, which is emitted once, with pyproject.
    dev_table_fields = ("dev_dependencies",)
    fields_by_name = {f.name: f for f in blueprint_fields}

    for f in ordered_fields:
        if f.name in dev_table_fields:
            continue
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
                doc.add(tomlkit.comment("--- Development Environment ([dev]) ---"))
            elif f.name == "appends":
                doc.add(tomlkit.comment("--- File Appends ---"))
            elif f.name == "options":
                doc.add(tomlkit.comment("--- Options ---"))
            elif f.name == "optional":
                doc.add(tomlkit.comment("--- Optional Content ---"))
            elif f.name == "tooling_overrides":
                doc.add(tomlkit.comment("--- Tooling Opinions & Overrides ---"))

            if f.name != "pyproject_injections":
                doc.add(tomlkit.comment(f.metadata["description"]))

        if f.name == "tooling_overrides":
            doc.add(
                tomlkit.comment(
                    "Dynamic precedence: CLI Flags > Template Opinions > Global UserConfig"
                )
            )
            tooling_keys = sorted(
                [mod.config_key for mod in TOOLING_MODULES if mod.config_key]
                + ["docker"]
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
                for name in dev_table_fields:
                    meta = fields_by_name[name].metadata
                    dev_table.add(tomlkit.comment(meta["description"]))
                    dev_table.add(name, _python_to_tomlkit(meta["example"]))
                    dev_table.add(tomlkit.nl())
                dev_table.add(tomlkit.comment("--- pyproject.toml AST Injections ---"))
                dev_table.add(tomlkit.comment(f.metadata["description"]))
                dev_table.add("pyproject", _python_to_tomlkit(example))
                doc.add("dev", dev_table)
            elif f.name in ("migrations", "optional"):
                blocks = tomlkit.aot()
                for block in example:
                    blocks.append(_python_to_tomlkit(block))
                doc.add(f.name, blocks)
            else:
                doc.add(f.name, _python_to_tomlkit(example))
            doc.add(tomlkit.nl())

    doc.add(tomlkit.comment("--- Custom Variables ---"))
    doc.add(
        tomlkit.comment(
            "Optional descriptions shown when asking for a custom variable's value."
        )
    )
    variables = tomlkit.table(is_super_table=True)
    variables.add("REGION", {"description": "Deployment region, e.g. eu-west-1"})
    doc.add("variables", variables)

    out_str = doc.as_string().strip() + "\n"
    _write_generated_doc("template_schema.toml", out_str)


def generate_capability_tables() -> None:
    """Generates Markdown tables detailing modules, templates, and their CLI footprints."""

    def _format_flags(flags: tuple[str, ...]) -> str:
        return ", ".join(f"`{f}`" for f in flags) if flags else "*None*"

    def _get_module_scaffolded_files(mod: BootstrapModule) -> str:
        test_manifest = EnvironmentManifest()
        mod.build(test_manifest)
        # pyproject.toml is shared by every tool rather than scaffolded by one.
        files = sorted(
            test_manifest.filesystem.file_injections.keys()
            | (test_manifest.filesystem.structured.keys() - {pyproject.TARGET})
        )
        if test_manifest.tooling.wants_hooks:
            files.append(".pre-commit-config.yaml")
        if test_manifest.tooling.wants_ci:
            files.append(".github/workflows/ci.yml")
        if test_manifest.tooling.wants_release:
            files.append(".github/workflows/release.yml")
        if test_manifest.tooling.wants_just:
            files.append("justfile")
        if test_manifest.tooling.wants_agents:
            files.append("AGENTS.md")
        if test_manifest.tooling.wants_community:
            files.extend([community.CONTRIBUTING_TARGET, community.PULL_REQUEST_TARGET])
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
    _write_generated_doc(
        "table_tooling.md", _format_markdown_table(tool_headers, tool_rows)
    )

    # Built-in Template matrix
    template_headers = ["Template", "Description", "Invocation", "Dependencies"]
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
                        content.get("description", ""),
                        f"`protostar init --template {name}`",
                        deps_formatted,
                    ]
                )
    except Exception as e:
        print(f"Warning: Failed to load built-in templates: {e}")

    _write_generated_doc(
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
                field.label,
                f"`{field.prompt_type}`",
                default_str,
            ]
        )
    _write_generated_doc(
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
    _write_generated_doc(
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
            "`--config <path>`",
            "*None*",
            "Reads global configuration from this file instead of the default location. Missing files are an error.",
        ],
        [
            "`--no-config`",
            "*None*",
            "Ignores global configuration entirely and runs on built-in defaults.",
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
    _write_generated_doc(
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
                    attr_part, desc_part = line.split(":", 1)
                    if "(" in attr_part and ")" in attr_part:
                        attr_name = attr_part.split("(")[0].strip()
                        typ = attr_part.split("(")[1].split(")")[0].strip()
                        desc = desc_part.strip()

                        if attr_name != "templates":
                            if "IDEType" in typ:
                                typ_formatted = '`"vscode"` \\| `"cursor"` \\| `"none"`'
                            else:
                                typ_formatted = " \\| ".join(
                                    f"`{part.strip()}`" for part in typ.split("|")
                                )
                            config_env_rows.append(
                                [f"`{attr_name}`", typ_formatted, desc]
                            )

    _write_generated_doc(
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
            "`--one-shot`",
            "*None*",
            "Scaffold once without recording a Protostar recipe or ownership state; uv.lock remains separate.",
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
    _write_generated_doc(
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
    _write_generated_doc(
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
    _write_generated_doc(
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
    _write_generated_doc(
        "table_cli_export_schema.md",
        _format_markdown_table(export_schema_headers, export_schema_rows),
    )

    # CLI check-template options table
    check_template_headers = ["Option", "Description"]
    check_template_rows = [
        [
            "`<source>`",
            "A template directory, a template TOML file, or an HTTPS URL. Defaults to the current directory.",
        ],
        [
            "`--strict`",
            "Fails on warnings as well as errors.",
        ],
        [
            "`--output-format <format>`",
            "`text` (default) for people, or `github` for GitHub Actions annotations on each finding's file and line. Cannot be combined with `--json`.",
        ],
        [
            "`--json`",
            "Emits the findings as a JSON payload with `status` `passed` or `failed`.",
        ],
    ]
    _write_generated_doc(
        "table_cli_check_template.md",
        _format_markdown_table(check_template_headers, check_template_rows),
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
    _write_generated_doc(
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
            "`MissingDependencyError`",
            "Missing required system binary (`uv` or `git`)",
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
            "Security violation (e.g., path traversal Zip Slip, or a template variable value that looks like a credential)",
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
    _write_generated_doc(
        "table_exit_codes.md",
        _format_markdown_table(exit_code_headers, exit_code_rows),
    )

    # Sync table into CONTRIBUTING.md if present
    contributing_path = REPO_ROOT / "CONTRIBUTING.md"
    if contributing_path.exists():
        contrib_content = contributing_path.read_text(encoding="utf-8")
        markdown_table = _format_markdown_table(exit_code_headers, exit_code_rows)
        import re

        new_content = re.sub(
            r"<!-- BEGIN_EXIT_CODES -->.*<!-- END_EXIT_CODES -->",
            f"<!-- BEGIN_EXIT_CODES -->\n\n{markdown_table}\n\n<!-- END_EXIT_CODES -->",
            contrib_content,
            flags=re.DOTALL,
        )
        atomic_write_text(contributing_path, new_content)


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
        blueprint = TemplateSource.load(str(target), built_in="astro").render({})
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
                payload.content,
                producer=f"template:{blueprint.reference.identity if blueprint.reference else 'unresolved'}:{identity}",
            )

    # Override machine-specific IDE paths to guarantee stable JSON diffs in CI
    manifest.ide_settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }

    state_json = json.dumps(manifest, cls=ManifestEncoder, indent=4)
    _write_generated_doc("manifest_state.json", state_json)


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

            # Analysis reads a separate example project, so the manifest above
            # stays that of a new one.
            from protostar.analysis import analyze_project

            existing = Path(tmp_dir, "existing")
            existing.mkdir()
            (existing / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nrequires-python = ">=3.12"\n'
                'authors = [{ name = "Demo Author" }]\n'
                'dependencies = []\n\n[dependency-groups]\ndev = ["pytest"]\n\n'
                "[tool.ruff]\nline-length = 100\n"
            )
            (existing / "LICENSE").write_text(
                "MIT License\n\nCopyright (c) 2024 Demo Author\n"
            )
            planned_payload = {
                "api_version": protostar.cli.schema.CLI_API_VERSION,
                "status": "planned",
                "manifest": manifest.to_dict(),
                "analysis": analyze_project(existing).to_dict(),
            }
            _write_generated_doc(
                "agent_payload_planned.json", json.dumps(planned_payload, indent=2)
            )
        finally:
            os.chdir(orig_cwd)

    # Lifecycle examples use the shipped preparation and presentation path.
    from protostar.cli.reviews import review_payload
    from protostar.preparation import prepare_review
    from protostar.sync_state import serialize_state

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            baseline = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
            baseline.filesystem.add_file_injection(
                ".github/renovate.json", '{"value": "original"}\n'
            )
            initial = prepare_review(baseline, UserConfig(), hook_revisions=())
            Path("protostar.lock").write_text(serialize_state(initial.candidate_state))
            manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
            manifest.filesystem.add_file_injection("safe.txt", "accepted\n")
            manifest.filesystem.add_file_injection(
                ".github/renovate.json", '{"value": "desired"}\n'
            )
            Path(".github").mkdir()
            Path(".github/renovate.json").write_text('{"value": "local"}\n')
            review = prepare_review(manifest, UserConfig(), hook_revisions=())
            payload = review_payload(review)
            _write_generated_doc(
                "agent_payload_reviewed.json", json.dumps(payload, indent=2)
            )
            payload["check_passed"] = not review.pending
            _write_generated_doc(
                "agent_payload_check.json", json.dumps(payload, indent=2)
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
    _write_generated_doc(
        "agent_payload_success.json", json.dumps(success_payload, indent=2)
    )

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
    _write_generated_doc(
        "agent_payload_error.json", json.dumps(error_payload, indent=2)
    )


def generate_cli_help_svgs() -> None:
    """Captures isolated SVG snapshots of the Protostar CLI help menus via Rich."""
    original_global_console = protostar.cli.ui.console

    def _render_svg(
        target_parser: argparse.ArgumentParser, prompt_cmd: str, filename: str
    ) -> None:
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
            ("❯ ", "bright_black"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{prompt_cmd}\n", "white"),
        )
        record_console.print(prompt)

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
        _render_svg(parser, "help", "cli_help.svg")

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
        if subparsers:
            for command in ("status", "diff", "sync", "guide"):
                _render_svg(
                    subparsers.choices[command],
                    f"help {command}",
                    f"cli_{command}_help.svg",
                )
    finally:
        protostar.cli.ui.console = original_global_console


def _recording_console(*, terminal: bool = True) -> Console:
    """Builds a byte-stable recording console for terminal SVG capture."""
    return Console(
        record=True,
        width=100,
        force_terminal=terminal,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
        _environ={},
    )


def _print_prompt(console: Console, arguments: str) -> None:
    """Prints a shell prompt invoking protostar with the given arguments."""
    console.print(
        Text.assemble(
            ("❯ ", "bright_black"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{arguments}\n", "white"),
        )
    )


@contextmanager
def _demo_project() -> Iterator[None]:
    """Runs the body inside a fresh, fixed-name project directory.

    Paths render with the directory's name, so it is fixed for byte-stable output;
    the regression snapshots use the same name.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_cwd = os.getcwd()
        project_dir = Path(tmpdir) / "demo_project"
        project_dir.mkdir()
        os.chdir(project_dir)
        try:
            yield
        finally:
            os.chdir(orig_cwd)


def _cli_template_engine(alias: str = "cli") -> tuple[Orchestrator, InitRequest]:
    """Builds the engine `protostar init --template <alias>` would run with defaults."""
    target = importlib.resources.files("protostar.templates").joinpath(f"{alias}.toml")
    blueprint = TemplateSource.load(str(target), built_in=alias).render({})
    user_config = UserConfig()
    modules: list[BootstrapModule] = [SystemWorkspaceModule(), PythonCore()]
    for mod in TOOLING_MODULES:
        is_active = getattr(user_config, mod.config_key, False)
        if blueprint and mod.config_key in blueprint.tooling_overrides:
            is_active = blueprint.tooling_overrides[mod.config_key]
        if is_active:
            modules.append(mod)
    request = InitRequest(template_blueprint=blueprint)
    return Orchestrator(modules, user_config, request=request), request


def generate_cli_dry_run_svg() -> None:
    """Captures an SVG snapshot of the dry-run CLI diagnostics preview via Rich."""
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console()
    _print_prompt(record_console, "init --template cli --dry-run")

    try:
        protostar.cli.ui.console = record_console
        with _demo_project():
            engine, _ = _cli_template_engine()
            protostar.cli.ui.print_dry_run_summary(engine.plan())

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_dry_run.svg",
            unique_id="cli_dry_run",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def _stub_subprocess(_runner: ProcessRunner, command: list[str], **_: Any) -> None:
    """Stands in for every engine subprocess, creating only what later steps probe."""
    if command[:2] == ["git", "init"]:
        Path(".git").mkdir()


def _stub_which(name: str) -> str | None:
    """Reports every required binary present and no IDE CLI to probe."""
    return None if name in ("code", "cursor") else f"/usr/bin/{name}"


def _stub_which_without_tools(name: str) -> str | None:
    """Reports every binary present except the IDE CLIs, direnv, and just."""
    return None if name in ("direnv", "just") else _stub_which(name)


def generate_cli_missing_tools_svg() -> None:
    """Captures an init whose direnv and just are missing, ending with their install command.

    Homebrew is stubbed present, so the command is the same on every host.
    """
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console(terminal=False)
    _print_prompt(record_console, "init --template cli")

    try:
        protostar.cli.ui.console = record_console
        with (
            _demo_project(),
            mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
            mock.patch.object(ProcessRunner, "run", _stub_subprocess),
            mock.patch("shutil.which", _stub_which_without_tools),
        ):
            engine, request = _cli_template_engine()
            protostar.cli.ui._run_engine(engine, request)

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_missing_tools.svg",
            unique_id="cli_missing_tools",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def generate_guide_svgs() -> None:
    """Captures `protostar guide` for a library, a CLI, and a workbench project.

    Each project is scaffolded by the real engine on stubbed subprocesses, so
    the guide reads the recipe, ledger, and pyproject.toml execution wrote.
    """
    from protostar.cli.guide import render_guide
    from protostar.guide import project_guide

    original_global_console = protostar.cli.ui.console
    try:
        for alias in ("lib", "cli", "ml"):
            record_console = _recording_console(terminal=False)
            with (
                _demo_project(),
                mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
                mock.patch.object(ProcessRunner, "run", _stub_subprocess),
                mock.patch("shutil.which", _stub_which),
            ):
                engine, request = _cli_template_engine(alias)
                protostar.cli.ui.console = _recording_console(terminal=False)
                protostar.cli.ui._run_engine(engine, request)
                _print_prompt(record_console, "guide")
                record_console.print(render_guide(project_guide()))

            _render_and_write_svg(
                record_console,
                title="zsh",
                filename=f"cli_guide_{alias}.svg",
                unique_id=f"cli_guide_{alias}",
            )
    finally:
        protostar.cli.ui.console = original_global_console


def generate_cli_init_svg() -> None:
    """Captures the init progress trail by running the real engine on stubbed subprocesses.

    The step labels come from the engine itself, so the image cannot drift from the
    CLI. A non-terminal console keeps Rich's animated spinner out of the recording
    while the checklist lines still print.
    """
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console(terminal=False)
    _print_prompt(record_console, "init --template cli")

    try:
        protostar.cli.ui.console = record_console
        with (
            _demo_project(),
            mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
            mock.patch.object(ProcessRunner, "run", _stub_subprocess),
            mock.patch("shutil.which", _stub_which),
        ):
            engine, request = _cli_template_engine()
            protostar.cli.ui._run_engine(engine, request)

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_init.svg",
            unique_id="cli_init",
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

    record_console.print(protostar.cli.ui.diagnostics_report(events))

    _render_and_write_svg(
        record_console,
        title="Diagnostic Summary",
        filename="diagnostic_panel.svg",
        unique_id="diagnostic_panel",
    )


def generate_diff_fixtures() -> None:
    """Generates unified diffs between base and merged scenario snapshots for documentation."""
    diff_targets = [
        ("ml", "ml_merged", "pyproject.toml"),
        ("ml", "ml_merged", ".gitignore"),
    ]

    for base, merged, filename in diff_targets:
        base_path = SNAPSHOTS_DIR / base / filename
        merged_path = SNAPSHOTS_DIR / merged / filename

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
                _write_generated_doc(output_name, clean_diff)


async def _settle(pilot: Any) -> None:
    """Waits for the app's workers, including those a finishing worker starts."""
    from textual.worker import WorkerCancelled

    await pilot.pause()
    for _ in range(10):
        workers = list(pilot.app.workers)
        if not workers:
            break
        for worker in workers:
            try:
                await worker.wait()
            except WorkerCancelled:
                pass
        await pilot.pause()
    await pilot.pause()


def _write_tui_svg(app: Any, filename: str, title: str = "protostar init") -> None:
    """Writes the app's current screen to DOCS_TERMINALS_DIR."""
    svg_content = app.export_screenshot(title=title)
    clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
    atomic_write_text(DOCS_TERMINALS_DIR / filename, clean_svg)


async def _capture_tui_screens() -> None:
    """Drives the recipe editor to the change review, capturing each screen."""
    from protostar.cli.tui.app import DecisionApp
    from protostar.cli.tui.recipe.screen import RecipeScreen
    from protostar.init_draft import DraftTemplate, InitDraft
    from protostar.templates import discover_templates

    config = UserConfig()
    target = importlib.resources.files("protostar.templates").joinpath("cli.toml")
    template = DraftTemplate(TemplateSource.load(str(target), built_in="cli"))
    app = DecisionApp(
        RecipeScreen(InitDraft(template=template), discover_templates(config), config)
    )
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        _write_tui_svg(app, "tui_recipe_editor.svg")
        await pilot.click("#continue")
        await _settle(pilot)
        _write_tui_svg(app, "tui_change_review.svg")
        app.exit(None)


def _conflict_manifest(renovate: str, line_length: int, command: str) -> Any:
    """A lifecycle manifest with a JSON value, a TOML key, and a text region."""
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.filesystem.add_file_injection(
        ".github/renovate.json", json.dumps({"extends": [renovate]}) + "\n"
    )
    manifest.filesystem.add_structured(
        "pyproject.toml",
        f"[tool.ruff]\nline-length = {line_length}\n",
        producer="module:ruff",
    )
    manifest.filesystem.add_region(
        "AGENTS.md", f"Run `{command}` before pushing.", identity="demo:commands"
    )
    return manifest


async def _capture_conflict_screen() -> None:
    """Captures the sync conflict screen over three kinds of conflict."""
    from protostar.cli.tui.app import DecisionApp
    from protostar.cli.tui.conflicts.screen import ConflictScreen
    from protostar.executor import SystemExecutor
    from protostar.lifecycle import PreparedProject
    from protostar.preparation import prepare_review

    config = UserConfig()
    baseline = _conflict_manifest("config:recommended", 88, "just test")
    SystemExecutor(
        baseline, config, review=prepare_review(baseline, config, hook_revisions=())
    ).execute()
    renovate = Path(".github/renovate.json")
    renovate.write_text(renovate.read_text().replace("recommended", "base"))
    pyproject = Path("pyproject.toml")
    pyproject.write_text(pyproject.read_text().replace("88", "100"))
    agents = Path("AGENTS.md")
    agents.write_text(agents.read_text().replace("just test", "just check"))
    manifest = _conflict_manifest("config:best-practices", 120, "just ci")
    project = PreparedProject(
        manifest, config, prepare_review(manifest, config, hook_revisions=())
    )
    app = DecisionApp(ConflictScreen(project))
    async with app.run_test(size=(120, 36)) as pilot:
        await _settle(pilot)
        await pilot.press("down", "down", "b")
        await _settle(pilot)
        _write_tui_svg(app, "tui_sync_conflicts.svg", "protostar sync")
        app.exit(None)


def generate_tui_svgs() -> None:
    """Captures the recipe editor, change review, and conflict screen."""
    with (
        _demo_project(),
        mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
        mock.patch("protostar.metadata.get_git_config", return_value=None),
    ):
        asyncio.run(_capture_tui_screens())
    orig_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            asyncio.run(_capture_conflict_screen())
        finally:
            os.chdir(orig_cwd)


def generate_docs_assets() -> None:
    """Generates all static documentation assets (SVGs, Markdown tables, schemas, payloads)."""
    DOCS_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_TERMINALS_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating static documentation assets...")
    generate_cli_help_svgs()
    generate_cli_dry_run_svg()
    generate_cli_init_svg()
    generate_cli_missing_tools_svg()
    generate_guide_svgs()
    generate_tui_svgs()
    generate_default_config()
    generate_capability_tables()
    generate_manifest_state()
    generate_agent_payloads()
    _write_generated_doc(
        "review_schema.json", json.dumps(protostar.cli.schema.review_schema(), indent=2)
    )
    _write_generated_doc(
        "application_schema.json",
        json.dumps(protostar.cli.schema.application_schema(), indent=2),
    )
    generate_template_schema_fixture()
    generate_diagnostic_panel_svg()
    print("✔ Static documentation assets generated.\n")


def main() -> None:
    """CLI entrypoint for standalone documentation asset generation."""
    parser = argparse.ArgumentParser(
        description="Generate documentation presentation assets."
    )
    parser.add_argument(
        "--diffs",
        action="store_true",
        help="Generate diff fixtures between scenario snapshots.",
    )
    args = parser.parse_args()

    # Isolate in-process configuration
    import protostar.config

    protostar.config.CONFIG_FILE = (
        Path(tempfile.gettempdir()) / "non_existent_protostar_config.toml"
    )
    protostar.config.clear_user_config_cache()

    generate_docs_assets()
    if args.diffs:
        generate_diff_fixtures()
    print("Documentation assets updated successfully!")


if __name__ == "__main__":
    main()
