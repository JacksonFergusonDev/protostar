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
    variables.add(
        "ORGANIZATION", {"description": "The team that maintains the project"}
    )
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
