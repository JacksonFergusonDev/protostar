import argparse
import json
import sys
from typing import Any

CLI_API_VERSION = 1


def handle_export_schema(args: argparse.Namespace) -> None:
    """Handles the 'export-schema' subcommand to output the template JSON schema."""
    import dataclasses

    from rich.json import JSON

    from protostar.cli import ui
    from protostar.config import TemplateBlueprint
    from protostar.modules import TOOLING_MODULES

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
        "description": 'A tool, a bool option, or "option=value", or an array of them that must all hold.',
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
                        "description": mod.cli_help,
                    }
            properties["docker"] = {
                "type": "boolean",
                "description": "Containerize workspace environment with Docker.",
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


def review_schema() -> dict[str, Any]:
    """Returns the schema for shipped status/diff JSON review envelopes."""
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

    location = {"file": string, "keys": strings, "identity": nullable_string}
    choice = {"enum": [choice.value for choice in ResolutionChoice]}
    # A side is absent (null) or holds text or a decoded value.
    side = {"oneOf": [record({"value": {}}), {"type": "null"}]}
    conflict = {
        "id": string,
        **location,
        "lines": {
            "oneOf": [
                record({"start": count, "count": count}),
                {"type": "null"},
            ]
        },
        "reason": {"enum": [reason.value for reason in ConflictReason]},
        "choices": {"type": "array", "items": choice},
        "sides": {
            "oneOf": [
                record({"text": boolean, "base": side, "local": side, "desired": side}),
                {"type": "null"},
            ]
        },
    }
    review = record(
        {
            "edits": records(
                {"path": string, "before": nullable_string, "after": nullable_string}
            ),
            "directories": strings,
            "migrations": records(
                {
                    "version": string,
                    "path": string,
                    "target": nullable_string,
                    "outcome": {
                        "enum": [outcome.value for outcome in MigrationOutcome]
                    },
                }
            ),
            "conflicts": records(conflict),
            "resolved": records({**conflict, "resolution": choice}),
            # A proposal without a choice applies.
            "proposals": records(
                {**conflict, "resolution": {"oneOf": [choice, {"type": "null"}]}}
            ),
            "preserved": records({**conflict, "deleted": boolean}),
            "state_changed": boolean,
            "resolver": record(
                {
                    "requirements": record(
                        {"main": strings, "dev": strings, "docs": strings}
                    ),
                    "lock_required": boolean,
                    "footprint": record({"paths": strings}),
                    "output": {"enum": ["unknown", None]},
                }
            ),
            "initialization_only": {"type": "array", "items": strings},
            "initialization_only_ide_probe": boolean,
            "missing_tools": missing_tools_schema(),
            "selections": records(
                {
                    "tool": {"enum": [tool.value for tool in Tool]},
                    "enabled": boolean,
                    "layer": {"enum": [layer.value for layer in SelectionLayer]},
                }
            ),
            "producers": records(
                {
                    "producer": string,
                    "tool": {"enum": [None, *[tool.value for tool in Tool]]},
                    "path": strings,
                }
            ),
        }
    )
    # A repository template's applied ref and what its repository offers.
    template = {
        "oneOf": [
            record(
                {
                    "ref": string,
                    "revision": string,
                    "kind": {"enum": [None, *[kind.value for kind in RefKind]]},
                    "newer": nullable_string,
                    "moved": nullable_string,
                    "reachable": boolean,
                }
            ),
            {"type": "null"},
        ]
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Protostar project review v1",
        "type": "object",
        "required": ["api_version", "status", "pending", "template", "review", "diffs"],
        "additionalProperties": False,
        "properties": {
            "api_version": {"const": CLI_API_VERSION},
            "status": {"const": "reviewed"},
            "pending": {"type": "boolean"},
            "check_passed": {"type": "boolean"},
            "template": template,
            "review": review,
            "diffs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "diff"],
                    "additionalProperties": False,
                    "properties": {
                        "path": {"type": "string"},
                        "diff": {"type": "string"},
                    },
                },
            },
        },
    }


def missing_tools_schema() -> dict[str, Any]:
    """Returns the schema of enabled tools' executables missing from ``PATH``."""
    from protostar.recipe import Tool
    from protostar.system_deps import GlobalExecutable

    return {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["executable", "tool"],
            "additionalProperties": False,
            "properties": {
                "executable": {"enum": [item.value for item in GlobalExecutable]},
                "tool": {"enum": [tool.value for tool in Tool]},
            },
        },
    }


def application_schema() -> dict[str, Any]:
    """Returns success/partial lifecycle application envelopes with actual results."""
    strings = {"type": "array", "items": {"type": "string"}}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Protostar project application v1",
        "type": "object",
        "required": ["api_version", "status", "template", "review", "result"],
        "additionalProperties": False,
        "properties": {
            "api_version": {"const": CLI_API_VERSION},
            "status": {"enum": ["success", "partial"]},
            "template": review_schema()["properties"]["template"],
            "review": review_schema()["properties"]["review"],
            # Only when a command installs the tools the result lists missing.
            "install_commands": strings,
            "result": {
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
                    "created_paths": strings,
                    "mutated_paths": strings,
                    "touched_paths": strings,
                    "diagnostics": {"type": "array", "items": {"type": "object"}},
                    "missing_tools": missing_tools_schema(),
                },
            },
        },
    }
