"""Every tooling module explains itself through one ToolInfo record."""

import argparse
import json

import pytest

from protostar.cli import parser, schema, ui
from protostar.modules import TOOLING_MODULES, ToolInfo


@pytest.mark.parametrize("module", TOOLING_MODULES, ids=lambda module: module.name)
def test_every_tooling_module_has_complete_tool_info(module):
    info = module.info
    assert isinstance(info, ToolInfo)
    assert info.summary
    # The summary is one line for --help and the tooltip, not a paragraph.
    assert "\n" not in info.summary
    assert len(info.summary) <= 72
    assert not info.summary.endswith(".")
    # adds and workflow are sentences in the popup.
    assert info.adds.endswith(".")
    assert info.workflow.endswith(".")
    assert info.docs_url.startswith("https://")
    # Backticks mark commands, which the popup highlights, so they pair up.
    for text in (info.summary, info.adds, info.workflow):
        assert text.count("`") % 2 == 0


def test_flag_help_is_the_tool_summary():
    subparsers = next(
        action
        for action in parser.build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    init = subparsers.choices["init"]
    helps = {
        action.dest: action.help for action in init._actions if action.dest != "help"
    }
    for module in TOOLING_MODULES:
        if module.cli_flags:
            assert helps[module.__class__.__name__] == module.info.summary


def test_schema_describes_each_tool_by_its_summary(monkeypatch, capsys):
    monkeypatch.setattr(ui, "is_json_mode", True)
    with pytest.raises(SystemExit):
        schema.handle_export_schema(argparse.Namespace())
    properties = json.loads(capsys.readouterr().out)["properties"]
    for module in TOOLING_MODULES:
        assert properties[module.config_key]["description"] == module.info.summary
