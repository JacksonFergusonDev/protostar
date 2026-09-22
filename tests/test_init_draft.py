"""The flag path and interactive path share one init resolver."""

from dataclasses import replace

import pytest

from protostar.config import TemplateSource, UserConfig
from protostar.errors import ConfigurationError
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.manifest import CollisionStrategy
from protostar.recipe import (
    EXCLUSIVE_TOOL_PAIRS,
    TOOL_REQUIREMENTS,
    Tool,
    validate_tools,
)


def test_equivalent_flag_and_wizard_drafts_resolve_identically(tmp_path, monkeypatch):
    """Equivalent selections produce the same modules, recipe, and request."""
    monkeypatch.chdir(tmp_path)
    template_path = tmp_path / "template.toml"
    template_path.write_text('name = "Example"\ndescription = "Example"\nruff = true\n')
    template = DraftTemplate(TemplateSource.load(str(template_path)), is_external=True)
    config = UserConfig(ruff=False, mypy=True, author_name="Ada")
    flag_draft = InitDraft(
        template=template,
        tool_overrides=((Tool.RUFF, False), (Tool.PYTEST, True)),
        docker=True,
        python_version="3.14",
        metadata=(("author_name", "Ada"), ("description", "Example")),
        collision_strategy=CollisionStrategy.MERGE,
    )
    wizard_choices = tuple(
        (
            tool,
            False
            if tool is Tool.RUFF
            else True
            if tool is Tool.PYTEST
            else bool(getattr(config, tool)),
        )
        for tool in Tool
    )
    wizard_draft = replace(
        flag_draft,
        tool_overrides=(),
        tool_choices=wizard_choices,
        metadata=(("description", "Example"), ("author_name", "Ada")),
    )

    flag_modules, flag_request = resolve_init(flag_draft, config)
    wizard_modules, wizard_request = resolve_init(wizard_draft, config)

    assert [type(module) for module in flag_modules] == [
        type(module) for module in wizard_modules
    ]
    assert flag_request.recipe == wizard_request.recipe
    assert flag_request.to_dict() == wizard_request.to_dict()
    assert flag_request.is_external == wizard_request.is_external


def test_exclusive_tool_table_rejects_each_pair():
    """Every declared exclusive pair is rejected by the shared validator."""
    for pair in EXCLUSIVE_TOOL_PAIRS:
        with pytest.raises(ConfigurationError, match="hook manager"):
            validate_tools(set(pair))


def test_requirement_table_rejects_each_missing_requirement():
    """Every declared requirement is checked by the same validator."""
    for tool, requirements in TOOL_REQUIREMENTS.items():
        for missing in requirements:
            with pytest.raises(ConfigurationError, match="Zensical"):
                validate_tools({tool, *(requirements - {missing})})
