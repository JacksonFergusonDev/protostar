"""Markdown capability matrices, configuration schemas, and template documentation generators."""

from __future__ import annotations

import importlib.resources
import json
import tomllib
from dataclasses import fields
from typing import Any

import tomlkit
from tomlkit.items import String, StringType, Trivia

from protostar.config import (
    TemplateBlueprint,
    UserConfig,
    default_config_content,
)
from protostar.metadata import METADATA_FIELDS
from protostar.models import InitRequest
from protostar.modules import (
    LICENSE_MAP,
    TOOLING_MODULES,
    PythonCore,
    SystemWorkspaceModule,
)
from protostar.modules.base import ToolModule
from protostar.orchestrator import Orchestrator
from protostar.recipe import TOOL_REQUIREMENTS, Tool
from scripts.generate_docs_assets.common import (
    _format_markdown_table,
    _write_generated_doc,
    cli_json,
    demo_project,
    stable_host,
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
            if isinstance(val[0], dict):
                arr = tomlkit.array()
                for item in val:
                    inline = tomlkit.inline_table()
                    inline.update(item)
                    arr.append(inline)
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
                    "A project's own choices win over the tier, the tier over these, and these over the user's defaults."
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
    variables.add(
        "ORGANIZATION", {"description": "The team that maintains the project"}
    )
    doc.add("variables", variables)

    out_str = doc.as_string().strip() + "\n"
    _write_generated_doc("template_schema.toml", out_str)


def _planned(modules: list[ToolModule]) -> set[str]:
    """Returns every file ``init`` with these tools plans, on a new project."""
    orchestrator = Orchestrator(
        [SystemWorkspaceModule(), PythonCore(), *modules],
        UserConfig(),
        request=InitRequest(),
    )
    return {path.as_posix() for path in orchestrator.plan().planned_files()}


def _scaffolded_files(mod: ToolModule) -> list[str]:
    """Returns the files enabling one tool adds to a new project's plan.

    The tools it requires are on in both plans, so only its own files remain.
    ``pyproject.toml`` and ``uv.lock`` are shared by every tool, not added by one.
    """
    needs = TOOL_REQUIREMENTS.get(Tool(mod.config_key), frozenset())
    required = [m for m in TOOLING_MODULES if m.config_key in needs]
    with demo_project(), stable_host():
        added = _planned([*required, mod]) - _planned(required)
    return sorted(added - {"pyproject.toml", "uv.lock"})


def generate_capability_tables() -> None:
    """Generates Markdown tables detailing modules, templates, and their CLI footprints."""

    def _format_flags(flags: tuple[str, ...]) -> str:
        return ", ".join(f"`{f}`" for f in flags) if flags else "*None*"

    def _get_module_scaffolded_files(mod: ToolModule) -> str:
        files = _scaffolded_files(mod)
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

    # Exit codes table. The names come from BSD's sysexits.h; Python's os.EX_*
    # constants are Unix-only, so ExitCode falls back to the numbers on Windows.
    exit_code_headers = [
        "Exit Code",
        "Name",
        "Error",
        "When",
    ]
    exit_code_rows = [
        ["`0`", "`EX_OK`", "*None*", "The command succeeded"],
        [
            "`1`",
            "General failure",
            "`CommandExecutionError`<br>`CommandTimeoutError`",
            "A command Protostar ran failed or timed out, or `sync --check` found the project out of step",
        ],
        [
            "`64`",
            "`EX_USAGE`",
            "`InvalidUsageError`",
            "The command line is invalid",
        ],
        [
            "`65`",
            "`EX_DATAERR`",
            "`TemplateResolutionError`",
            "The template can't be read, such as a corrupted archive or a missing variable",
        ],
        [
            "`69`",
            "`EX_UNAVAILABLE`",
            "`MissingDependencyError`",
            "`uv` or `git` isn't installed",
        ],
        [
            "`70`",
            "`EX_SOFTWARE`",
            "*(Unhandled exception)*",
            "A bug in Protostar; it prints a link to report it",
        ],
        [
            "`74`",
            "`EX_IOERR`",
            "`FileSystemError`",
            "A file couldn't be read or written, or permission was denied",
        ],
        [
            "`75`",
            "`EX_TEMPFAIL`",
            "`NetworkFetchError`",
            "A remote template couldn't be downloaded; retrying may work",
        ],
        [
            "`77`",
            "`EX_NOPERM`",
            "`SecurityViolationError`",
            "A safety check refused the run, such as a path that escapes the project or a variable value that looks like a credential",
        ],
        [
            "`78`",
            "`EX_CONFIG`",
            "`ConfigurationError`",
            "Invalid TOML, or settings that contradict each other",
        ],
        [
            "`130`",
            "Interrupted (128 + `SIGINT`)",
            "`ExecutionAbortedError`<br>`ExecutionInterruptedError`",
            "You cancelled setup or pressed Ctrl+C",
        ],
    ]
    _write_generated_doc(
        "table_exit_codes.md",
        _format_markdown_table(exit_code_headers, exit_code_rows),
    )


def generate_manifest_state() -> None:
    """Writes the manifest ``protostar init --template astro --dry-run --json`` prints."""
    with demo_project(), stable_host():
        manifest = cli_json("init", "--template", "astro", "--dry-run")["manifest"]
    _write_generated_doc("manifest_state.json", json.dumps(manifest, indent=2))
