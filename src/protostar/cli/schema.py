"""JSON schemas Protostar publishes: templates, capabilities, and review output.

``protostar export-schema`` prints the template schema; the others document
the ``--json`` payloads agents read.
"""

import argparse
import json
import sys
from typing import Any

CLI_API_VERSION = 2


def handle_export_schema(args: argparse.Namespace) -> None:
    """Handles the 'export-schema' subcommand to output the template JSON schema."""
    import dataclasses

    from rich.json import JSON

    from protostar.cli import ui
    from protostar.config import TemplateBlueprint
    from protostar.modules import TOOLING_MODULES
    from protostar.tiers import Tier

    properties: dict[str, Any] = {}
    dev_properties: dict[str, Any] = {}
    name_pattern = "^[A-Za-z_][A-Za-z0-9_]*$"
    choice_pattern = "^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    term = {
        "type": "string",
        "pattern": "^[A-Za-z_][A-Za-z0-9_]*(=[A-Za-z0-9][A-Za-z0-9_.-]*)?$",
    }
    requires = {
        "oneOf": [term, {"type": "array", "items": term, "minItems": 1}],
        "description": 'A tool, a bool option, "option=value", or "tier=workbench" or "tier=production", or an array of them that must all hold.',
    }
    strings = {"type": "array", "items": {"type": "string"}}

    for f in dataclasses.fields(TemplateBlueprint):
        if f.name == "reference":
            continue
        desc = f.metadata.get("description", "")
        if f.name == "tooling_overrides":
            for mod in TOOLING_MODULES:
                if mod.config_key:
                    properties[mod.config_key] = {
                        "type": "boolean",
                        "description": mod.info.summary,
                    }
            continue
        if f.name == "tiers":
            flags = sorted(
                [mod.config_key for mod in TOOLING_MODULES if mod.config_key]
            )
            tier_flags = {
                "type": "object",
                "propertyNames": {"enum": flags},
                "additionalProperties": {"type": "boolean"},
                "minProperties": 1,
            }
            properties["tier"] = {
                "enum": [tier.value for tier in Tier],
                "description": "The tier a project follows until it chooses one; requires [tiers].",
            }
            properties["tiers"] = {
                "type": "object",
                "properties": {tier.value: tier_flags for tier in Tier},
                "required": [tier.value for tier in Tier],
                "additionalProperties": False,
                "description": desc,
            }
            continue

        type_str = str(f.type)
        if f.name == "appends":
            prop = {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "propertyNames": {"pattern": "^[A-Za-z0-9_][A-Za-z0-9_.:/-]*$"},
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "requires": requires,
                        },
                        "required": ["content"],
                        "additionalProperties": False,
                    },
                },
            }
        elif f.name == "options":
            prop = {
                "type": "object",
                "propertyNames": {"pattern": name_pattern},
                "additionalProperties": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "default": {"type": "boolean"},
                            },
                            "required": ["default"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "choices": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "pattern": choice_pattern,
                                    },
                                    "minItems": 2,
                                    "uniqueItems": True,
                                },
                                "default": {"type": "string"},
                            },
                            "required": ["choices", "default"],
                            "additionalProperties": False,
                        },
                    ]
                },
            }
        elif f.name == "optional":
            prop = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "requires": requires,
                        "dependencies": strings,
                        "dev_dependencies": strings,
                        "docs_dependencies": strings,
                        "files": strings,
                    },
                    "required": ["requires"],
                    "minProperties": 2,
                    "additionalProperties": False,
                },
            }
        elif f.name == "pyproject_injections":
            prop = {
                "type": "object",
                "additionalProperties": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "requires": requires,
                            },
                            "required": ["content"],
                            "additionalProperties": False,
                        },
                    ]
                },
            }
        elif f.name == "dependency_includes":
            prop = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "group": {"enum": ["dev", "docs"]},
                        "include": {"enum": ["dev", "docs"]},
                    },
                    "required": ["group", "include"],
                    "additionalProperties": False,
                },
            }
        elif f.name == "migrations":
            renames = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                    },
                    "required": ["from", "to"],
                    "additionalProperties": False,
                },
            }
            prop = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "version": {"type": "string"},
                        "rename": renames,
                        "remove": {"type": "array", "items": {"type": "string"}},
                        "rename_variables": renames,
                    },
                    "required": ["version"],
                    "additionalProperties": False,
                },
            }
        elif "list[list[str]]" in type_str:
            prop = {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
            }
        elif "dict[str, list[str]]" in type_str:
            prop = {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            }
        elif "list[str]" in type_str:
            prop = {"type": "array", "items": {"type": "string"}}
        elif "dict[str, str]" in type_str:
            prop = {"type": "object", "additionalProperties": {"type": "string"}}
        elif "dict[str, bool]" in type_str:
            prop = {"type": "object", "additionalProperties": {"type": "boolean"}}
        elif "bool" in type_str:
            prop = {"type": "boolean"}
        else:
            prop = {"type": "string"}

        target_pattern = r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*(?:^|/)(?:protostar\.lock|uv\.lock)(?:/|$)).+$"
        if f.name in ("files", "appends"):
            prop["propertyNames"] = {"pattern": target_pattern}
        if f.name == "files":
            prop["propertyNames"] = {
                "allOf": [
                    {"pattern": target_pattern},
                    {"not": {"enum": ["pyproject.toml"]}},
                ]
            }
        if f.name == "appends":
            prop["propertyNames"] = {
                "allOf": [{"pattern": target_pattern}, {"not": {"pattern": r"\.toml$"}}]
            }
        if f.name == "directories":
            prop["items"] = {"type": "string", "pattern": target_pattern}
        if desc:
            prop["description"] = desc

        if f.name == "dev_dependencies":
            dev_properties["dev_dependencies"] = prop
        elif f.name == "pyproject_injections":
            dev_properties["pyproject"] = prop
        else:
            properties[f.name] = prop

    properties["variables"] = {
        "type": "object",
        "description": "Descriptions shown when asking for custom variables' values.",
        "propertyNames": {"pattern": name_pattern},
        "additionalProperties": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
            "additionalProperties": False,
        },
    }

    if dev_properties:
        properties["dev"] = {
            "type": "object",
            "properties": dev_properties,
            "additionalProperties": False,
            "description": "Development environment configurations.",
        }

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://protostar.dev/schema/template/experimental-v{CLI_API_VERSION}.json",
        "title": "Protostar Template Schema",
        "description": "Experimental JSON Schema for validating Protostar TOML templates.",
        "type": "object",
        "properties": properties,
        "dependentRequired": {"tier": ["tiers"], "tiers": ["tier"]},
        "additionalProperties": False,
    }

    if ui.is_json_mode:
        # In JSON mode, stdout should be compact for agents
        print(json.dumps(schema, separators=(",", ":")))  # noqa: T201
    else:
        # Human mode: pretty print with syntax highlighting
        ui.console.print(JSON.from_data(schema))

    sys.exit(0)


def _build_capabilities_schema(
    parser: argparse.ArgumentParser, command: str | None = None
) -> dict[str, Any]:
    """Introspects the parser to build a dynamic capabilities schema.

    Generates a structured description of all available subcommands and their
    flags by walking the parser's action groups. This is the payload emitted
    when ``--help --json``, ``help <command> --json``, or bare ``--json`` is invoked.

    Args:
        parser: The fully constructed root argument parser.
        command: Optional specific subcommand name to filter capabilities for.

    Returns:
        A JSON-serializable capabilities dictionary.
    """
    commands: dict[str, Any] = {}
    subparsers_action = next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )
    if subparsers_action is not None:
        choices = (
            {command: subparsers_action.choices[command]}
            if command and command in subparsers_action.choices
            else subparsers_action.choices
        )
        for name, subparser in choices.items():
            flags: list[dict[str, Any]] = []
            for action in subparser._actions:
                if isinstance(action, argparse._HelpAction):
                    continue
                if action.help == argparse.SUPPRESS:
                    continue
                flag_entry: dict[str, Any] = {
                    "names": action.option_strings or [action.dest],
                    "help": action.help or "",
                }
                if action.metavar:
                    flag_entry["metavar"] = action.metavar
                if (
                    isinstance(
                        action,
                        (
                            argparse.BooleanOptionalAction,
                            argparse._StoreTrueAction,
                            argparse._StoreFalseAction,
                        ),
                    )
                    or action.nargs == 0
                ):
                    flag_entry["type"] = "bool"
                else:
                    flag_entry["type"] = "str"
                flags.append(flag_entry)
            commands[name] = {
                "description": subparser.description or "",
                "flags": flags,
            }
    return {
        "commands": commands,
        "review_schema": review_schema(),
        "application_schema": application_schema(),
    }


def emit_capabilities(
    parser: argparse.ArgumentParser, command: str | None = None
) -> None:
    """Emits the structured capabilities schema in JSON format and exits immediately."""
    from protostar.cli import ui

    ui.emit_json(
        {
            "api_version": CLI_API_VERSION,
            "status": "success",
            "capabilities": _build_capabilities_schema(parser, command=command),
        }
    )
    sys.exit(0)


def described(description: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Returns ``schema`` with the ``description`` agents and the docs read."""
    return {**schema, "description": description}


def review_schema() -> dict[str, Any]:
    """Returns the schema for shipped status/diff JSON review envelopes.

    Every property carries a description: the docs render their field tables
    from it, and agents read it in ``capabilities.review_schema``.
    """
    from protostar.cli.decisions import MEANING
    from protostar.merge import ConflictReason, ResolutionChoice
    from protostar.migrations import MigrationOutcome
    from protostar.network import RefKind
    from protostar.recipe import SelectionLayer, Tool

    string = {"type": "string"}
    strings = {"type": "array", "items": string}
    boolean = {"type": "boolean"}
    nullable_string = {"type": ["string", "null"]}
    count = {"type": "integer", "minimum": 0}

    def record(properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    def records(properties: dict[str, Any]) -> dict[str, Any]:
        return {"type": "array", "items": record(properties)}

    def nullable(schema: dict[str, Any]) -> dict[str, Any]:
        return {"oneOf": [schema, {"type": "null"}]}

    choice = {"enum": [choice.value for choice in ResolutionChoice]}
    # A side is absent (null) or holds text or a decoded value.
    side = nullable(
        record(
            {
                "value": described(
                    "The text of the lines, or the decoded TOML, YAML, or JSON value.",
                    {},
                )
            }
        )
    )
    conflict = {
        "id": described(
            "Names this decision in `--resolve`. It covers the content, so it "
            "changes when the files do.",
            string,
        ),
        "file": described("The file the decision is in, as a POSIX path.", string),
        "keys": described(
            "The key path inside a structured file; empty for a text file "
            "or a whole file.",
            strings,
        ),
        "identity": described(
            "The record it is in when the keys name a list of records, "
            "such as a hook; otherwise `null`.",
            nullable_string,
        ),
        "lines": described(
            "The lines of a text file, numbered as in a unified diff hunk "
            "header; `null` for a structured file.",
            nullable(
                record(
                    {
                        "start": described(
                            "The first line, counting from 1. When `count` is 0, "
                            "the line the span follows (0 before the first).",
                            count,
                        ),
                        "count": described(
                            "The number of local lines; 0 when your file has none there.",
                            count,
                        ),
                    }
                )
            ),
        ),
        "reason": described(
            "Why it is a decision. Each value below says what it means.",
            {
                "oneOf": [
                    {"const": reason.value, "description": MEANING[reason]}
                    for reason in ConflictReason
                ]
            },
        ),
        "choices": described(
            "The choices that settle it: `local` keeps your version, `desired` "
            "takes the update, and `both` keeps both sides of a text hunk.",
            {"type": "array", "items": choice},
        ),
        "sides": described(
            "What each side holds there; `null` when only a person can settle it.",
            nullable(
                record(
                    {
                        "text": described(
                            "Whether the sides are lines of text rather than "
                            "decoded values.",
                            boolean,
                        ),
                        "base": described(
                            "What Protostar last applied; `null` when it never did.",
                            side,
                        ),
                        "local": described(
                            "What your file holds; `null` when you deleted it.", side
                        ),
                        "desired": described(
                            "What the update holds; `null` when it no longer "
                            "includes it.",
                            side,
                        ),
                    }
                )
            ),
        ),
    }
    review = record(
        {
            "edits": described(
                "Every file the run writes or removes.",
                records(
                    {
                        "path": described("The file, as a POSIX path.", string),
                        "before": described(
                            "The file's text now; `null` when it is new.",
                            nullable_string,
                        ),
                        "after": described(
                            "The file's text after the run; `null` when it is removed.",
                            nullable_string,
                        ),
                    }
                ),
            ),
            "directories": described(
                "Directories the run creates, as POSIX paths.", strings
            ),
            "migrations": described(
                "What each template migration does to one file.",
                records(
                    {
                        "version": described("The migration's version.", string),
                        "path": described("The file it names in this project.", string),
                        "target": described(
                            "Where a rename moves the file; `null` for a removal.",
                            nullable_string,
                        ),
                        "outcome": described(
                            "What happened to the file: `moved`, `target-exists`, "
                            "`removed`, `retired`, `forgotten`, or `not-owned`.",
                            {"enum": [outcome.value for outcome in MigrationOutcome]},
                        ),
                    }
                ),
            ),
            "conflicts": described(
                "Open conflicts. Your version stays until each is resolved.",
                records(conflict),
            ),
            "resolved": described(
                "Conflicts settled by `--resolve`, each with the choice made.",
                records(
                    {
                        **conflict,
                        "resolution": described("The choice that settled it.", choice),
                    }
                ),
            ),
            # A proposal without a choice applies.
            "proposals": described(
                "Changes into content Protostar never owned. Each applies "
                "unless resolved with `local`.",
                records(
                    {
                        **conflict,
                        "resolution": described(
                            "The choice made; `null` while it applies.",
                            nullable(choice),
                        ),
                    }
                ),
            ),
            "preserved": described(
                "Your edits and deletions that stay under an unchanged update. "
                "Resolving one with `desired` takes Protostar's version there.",
                records(
                    {
                        **conflict,
                        "deleted": described(
                            "Whether what you kept is a deletion.", boolean
                        ),
                    }
                ),
            ),
            "state_changed": described(
                "Whether the ownership records must advance.", boolean
            ),
            "resolver": described(
                "The package work uv does; its output is never simulated.",
                record(
                    {
                        "requirements": described(
                            "The packages uv adds, by dependency group.",
                            record(
                                {
                                    "main": described("Runtime dependencies.", strings),
                                    "dev": described(
                                        "Development dependencies.", strings
                                    ),
                                    "docs": described(
                                        "Documentation dependencies.", strings
                                    ),
                                }
                            ),
                        ),
                        "lock_required": described(
                            "Whether uv must refresh `uv.lock`.", boolean
                        ),
                        "footprint": described(
                            "The paths uv may write.",
                            record(
                                {
                                    "paths": described(
                                        "The paths, as POSIX paths.", strings
                                    )
                                }
                            ),
                        ),
                        "output": described(
                            "`unknown` when resolver work is pending, else `null`.",
                            {"enum": ["unknown", None]},
                        ),
                    }
                ),
            ),
            "initialization_only": described(
                "Commands only `init` runs, such as `git init`; `sync` never "
                "runs them again.",
                {"type": "array", "items": strings},
            ),
            "initialization_only_ide_probe": described(
                "Whether `init` also checks your IDE for the extensions the tools recommend.",
                boolean,
            ),
            "hooks": described(
                "What `sync` does to this clone's git hooks. They never count "
                "as pending.",
                record(
                    {
                        "install": described(
                            "The command that installs the wanted hooks; `null` "
                            "when none is missing.",
                            nullable(strings),
                        ),
                        "remove": described(
                            "Generated hooks that will be removed, as POSIX paths.",
                            strings,
                        ),
                    }
                ),
            ),
            "missing_tools": missing_tools_schema(),
            "selections": described(
                "Which tools are on, and which layer decided each.",
                records(
                    {
                        "tool": described(
                            "The tool.", {"enum": [tool.value for tool in Tool]}
                        ),
                        "enabled": described("Whether it is on.", boolean),
                        "layer": described(
                            "Where the choice came from: your `project`, the "
                            "`template`, or a `fallback` default.",
                            {"enum": [layer.value for layer in SelectionLayer]},
                        ),
                    }
                ),
            ),
            "producers": described(
                "Which module declared each part of the plan.",
                records(
                    {
                        "producer": described("The module that declared it.", string),
                        "tool": described(
                            "The tool the module belongs to; `null` for the core.",
                            {"enum": [None, *[tool.value for tool in Tool]]},
                        ),
                        "path": described(
                            "The plan section (`dependencies`, `filesystem`, "
                            "`tasks`, or `tooling`), then the keys declared.",
                            strings,
                        ),
                    }
                ),
            ),
        }
    )
    # A repository template's applied ref and what its repository offers.
    template = described(
        "The template's applied ref and what its repository offers; `null` for "
        "a built-in, local, or plain-URL template.",
        nullable(
            record(
                {
                    "ref": described("The tag, branch, or commit applied.", string),
                    "revision": described("The commit the ref names.", string),
                    "kind": described(
                        "What the ref is; `null` when the repository no longer has it.",
                        {"enum": [None, *[kind.value for kind in RefKind]]},
                    ),
                    "newer": described(
                        "The newest release, when there is one; move to it "
                        "with `sync --to`.",
                        nullable_string,
                    ),
                    "moved": described(
                        "The commit a tag or branch names now, when it moved.",
                        nullable_string,
                    ),
                    "reachable": described(
                        "Whether the repository could be reached.", boolean
                    ),
                }
            )
        ),
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Protostar project review v1",
        "type": "object",
        "required": ["api_version", "status", "pending", "template", "review", "diffs"],
        "additionalProperties": False,
        "properties": {
            "api_version": described(
                "The machine protocol version.", {"const": CLI_API_VERSION}
            ),
            "status": described("Always `reviewed`.", {"const": "reviewed"}),
            "pending": described(
                "Whether the project is out of date: files, directories, "
                "ownership, package work, or conflicts. Git hooks never count.",
                {"type": "boolean"},
            ),
            "check_passed": described(
                "Only from `sync --check`: whether nothing is pending.",
                {"type": "boolean"},
            ),
            "template": template,
            "review": described("What the run does and what it asks.", review),
            "diffs": described(
                "A unified diff for each entry in `review.edits`.",
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["path", "diff"],
                        "additionalProperties": False,
                        "properties": {
                            "path": described("The file, as a POSIX path.", string),
                            "diff": described("Its unified diff.", string),
                        },
                    },
                },
            ),
        },
    }


def missing_tools_schema() -> dict[str, Any]:
    """Returns the schema of enabled tools' executables missing from ``PATH``."""
    from protostar.recipe import Tool
    from protostar.system_deps import GlobalExecutable

    return described(
        "Executables a selected tool runs that `PATH` lacks. The steps that run "
        "them are skipped.",
        {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["executable", "tool"],
                "additionalProperties": False,
                "properties": {
                    "executable": described(
                        "The executable that is missing.",
                        {"enum": [item.value for item in GlobalExecutable]},
                    ),
                    "tool": described(
                        "The tool that runs it.",
                        {"enum": [tool.value for tool in Tool]},
                    ),
                },
            },
        },
    )


def application_schema() -> dict[str, Any]:
    """Returns success/partial lifecycle application envelopes with actual results."""
    review = review_schema()["properties"]
    strings = {"type": "array", "items": {"type": "string"}}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Protostar project application v1",
        "type": "object",
        "required": ["api_version", "status", "template", "review", "result"],
        "additionalProperties": False,
        "properties": {
            "api_version": review["api_version"],
            "status": described(
                "`success` when nothing is left to settle; `partial` when safe "
                "updates were committed but conflicts remain.",
                {"enum": ["success", "partial"]},
            ),
            "template": review["template"],
            "review": described("What the run did and what it asks.", review["review"]),
            # Only when a command installs the tools the result lists missing.
            "install_commands": described(
                "The commands that install the missing tools, in order; only "
                "when a package manager was found.",
                strings,
            ),
            "result": described(
                "What the run wrote.",
                {
                    "type": "object",
                    "required": [
                        "created_paths",
                        "mutated_paths",
                        "touched_paths",
                        "diagnostics",
                        "missing_tools",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "created_paths": described("Paths the run created.", strings),
                        "mutated_paths": described(
                            "Paths that existed and the run changed.", strings
                        ),
                        "touched_paths": described(
                            "Every created or mutated path.", strings
                        ),
                        "diagnostics": described(
                            "Non-fatal notes from the run.",
                            {"type": "array", "items": {"type": "object"}},
                        ),
                        "missing_tools": missing_tools_schema(),
                    },
                },
            ),
        },
    }
