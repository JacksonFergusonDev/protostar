"""The CLI reference's usage lines and option tables, read from the parser.

Every row comes from ``build_parser()``, so an option and its help text have one
source: the same text ``--help`` prints. A new flag reaches the reference by
regenerating it, never by editing a table.
"""

from __future__ import annotations

import argparse

from protostar.cli.parser import build_parser, format_invocation
from protostar.modules import TOOLING_MODULES
from scripts.generate_docs_assets.common import (
    _format_markdown_table,
    _write_generated_doc,
)

GLOBAL_FIXTURE = "cli_global.md"
TOOL_FLAGS_FIXTURE = "cli_init_tools.md"

# Tool flags are listed once, in their own table, rather than in init's.
_TOOL_DESTS = frozenset(type(mod).__name__ for mod in TOOLING_MODULES if mod.cli_flags)


def command_fixture(command: str) -> str:
    """Returns the generated file that holds a command's usage line and options."""
    return f"cli_{command.replace('-', '_')}.md"


def subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Returns every subcommand's parser, in the order ``--help`` lists them."""
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return dict(action.choices)


def _documented(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    """Returns the arguments a parser shows in ``--help``, in their order."""
    return [
        action
        for action in parser._actions
        if action.help != argparse.SUPPRESS
        and not isinstance(action, argparse._HelpAction | argparse._SubParsersAction)
    ]


def _cell(text: str) -> str:
    """Escapes text for a Markdown table cell."""
    return text.replace("|", "\\|")


def _rows(actions: list[argparse.Action]) -> list[list[str]]:
    return [
        [f"`{_cell(format_invocation(action))}`", _cell(str(action.help or ""))]
        for action in actions
    ]


def _usage(command: str, actions: list[argparse.Action]) -> str:
    """Returns a command's synopsis, such as ``protostar completion [<shell>]``."""
    parts = ["protostar", command]
    for action in actions:
        if not action.option_strings:
            name = format_invocation(action)
            parts.append(f"[{name}]" if action.nargs == "?" else name)
    if any(action.option_strings for action in actions):
        parts.append("[options]")
    return " ".join(parts)


def generate_cli_tables() -> None:
    """Writes the global options table, and each command's usage line and options."""
    parser = build_parser()
    global_actions = _documented(parser)
    global_dests = {action.dest for action in global_actions}
    _write_generated_doc(
        GLOBAL_FIXTURE,
        _format_markdown_table(["Option", "Description"], _rows(global_actions)),
    )

    for command, subparser in subcommands(parser).items():
        actions = [
            action
            for action in _documented(subparser)
            if action.dest not in global_dests
        ]
        tools = [action for action in actions if action.dest in _TOOL_DESTS]
        own = [action for action in actions if action.dest not in _TOOL_DESTS]
        content = f"```text\n{_usage(command, actions)}\n```"
        if own:
            content += "\n\n" + _format_markdown_table(
                ["Option", "Description"], _rows(own)
            )
        _write_generated_doc(command_fixture(command), content)
        if tools:
            _write_generated_doc(
                TOOL_FLAGS_FIXTURE,
                _format_markdown_table(["Flag", "Description"], _rows(tools)),
            )
