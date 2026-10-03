"""Markdown capability matrices, configuration schemas, and template documentation generators."""

from __future__ import annotations

import importlib.resources
import json
import re
import tomllib
from dataclasses import fields
from typing import Any

import tomlkit
from tomlkit.items import String, StringType, Trivia

from protostar.config import (
    TemplateBlueprint,
    TemplateSource,
    UserConfig,
    default_config_content,
)
from protostar.documents import community, pyproject
from protostar.fs import atomic_write_text
from protostar.manifest import EnvironmentManifest
from protostar.metadata import METADATA_FIELDS
from protostar.modules import (
    LICENSE_MAP,
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    RuffModule,
)
from protostar.options import Condition
from scripts._common import OutputStyle, report
from scripts.generate_docs_assets.common import (
    REPO_ROOT,
    ManifestEncoder,
    _format_markdown_table,
    _write_generated_doc,
)


def generate_default_config() -> None:
    """Writes the default global TOML configuration to a generated documentation fixture."""
    _write_generated_doc("default_config.toml", default_config_content())


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
        "tiers",
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
            elif f.name == "tiers":
                doc.add(tomlkit.comment("--- Tiers ---"))

            if f.name != "pyproject_injections":
                doc.add(tomlkit.comment(f.metadata["description"]))

        if f.name == "tooling_overrides":
            doc.add(
                tomlkit.comment(
                    "Dynamic precedence: CLI Flags > Template Opinions > Global UserConfig"
                )
            )
            # A tool the tiers set is set there, never also at the root.
            tiered = set(fields_by_name["tiers"].metadata["example"]["workbench"])
            tooling_keys = sorted(
                [mod.config_key for mod in TOOLING_MODULES if mod.config_key]
            )
            for key in tooling_keys:
                if key not in tiered:
                    doc.add(key, key == "ruff")
            doc.add(tomlkit.nl())
            doc.add(
                tomlkit.comment(
                    "The tier a project follows until it chooses one; requires [tiers]."
                )
            )
            doc.add("tier", "workbench")
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
        if test_manifest.tooling.wants_docker:
            files.extend(["Dockerfile", ".dockerignore"])
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
            mod.info.summary,
            _get_module_scaffolded_files(mod),
        ]
        for mod in TOOLING_MODULES
    ]
    _write_generated_doc(
        "table_tooling.md", _format_markdown_table(tool_headers, tool_rows)
    )

    # Built-in Template matrix
    template_headers = [
        "Template",
        "Description",
        "Default tier",
        "Invocation",
        "Dependencies",
    ]
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
                        str(content.get("tier", "*None*")).capitalize(),
                        f"`protostar init --template {name}`",
                        deps_formatted,
                    ]
                )
    except Exception as e:
        report(
            f"Warning: Failed to load built-in templates: {e}", style=OutputStyle.ERROR
        )

    _write_generated_doc(
        "table_templates.md", _format_markdown_table(template_headers, template_rows)
    )

    # Interactive setup project metadata fields matrix
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

    # Tools are described once, by their modules.
    defaults = UserConfig()
    for module in TOOLING_MODULES:
        default = str(getattr(defaults, module.config_key)).lower()
        config_env_rows.append(
            [
                f"`{module.config_key}`",
                "`bool`",
                f"{module.info.summary}. Default: `{default}`.",
            ]
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
            mod.info.summary,
        ]
        for mod in TOOLING_MODULES
        if mod.cli_flags
    ]
    _write_generated_doc(
        "table_cli_tooling_flags.md",
        _format_markdown_table(tooling_flags_headers, tooling_flags_rows),
    )

    # CLI config options table
    config_headers = ["Option", "Description"]
    config_rows = [
        [
            "*(No args)*",
            "Opens a form for your identity, editor, Python version, and tool defaults, and saves only what changed. Needs an interactive terminal.",
        ],
        [
            "`--edit`",
            "Opens `config.toml` in your system's default `$EDITOR`, seeding the default template if it is missing.",
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
            "You cancelled interactive setup or interrupted execution (Ctrl+C)",
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
        # Gated content applies as a default init would decide: ruff on, the
        # template's default tier.
        tier = blueprint.tiers.default.value if blueprint.tiers else None
        options = {"tier": tier} if tier else {}

        def holds(condition: Condition | None) -> bool:
            return condition is None or condition.holds({"ruff"}, options)

        def ships(path: str) -> bool:
            blocks = [block for block in blueprint.optional if block.covers(path)]
            return not blocks or any(holds(block.requires) for block in blocks)

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
            if ships(filepath):
                manifest.filesystem.add_file_injection(filepath, content)
        manifest.template_reference = blueprint.reference
        for identity, payload in blueprint.pyproject_injections.items():
            if not holds(payload.requires):
                continue
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
