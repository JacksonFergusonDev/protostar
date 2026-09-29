"""The flag path and interactive path share one init resolver."""

from dataclasses import replace

import pytest

from protostar.cli.parser import build_parser
from protostar.config import TemplateSource, UserConfig
from protostar.errors import ConfigurationError
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.manifest import CollisionStrategy
from protostar.modules import TOOLING_MODULES
from protostar.orchestrator import Orchestrator
from protostar.recipe import (
    EXCLUSIVE_TOOL_PAIRS,
    TOOL_REQUIREMENTS,
    Tool,
    validate_tools,
)


def test_equivalent_flag_and_editor_drafts_resolve_identically(tmp_path, monkeypatch):
    """Equivalent selections produce the same modules, recipe, and request."""
    monkeypatch.chdir(tmp_path)
    template_path = tmp_path / "template.toml"
    template_path.write_text('name = "Example"\ndescription = "Example"\nruff = true\n')
    template = DraftTemplate(TemplateSource.load(str(template_path)), is_external=True)
    config = UserConfig(ruff=False, mypy=True, author_name="Ada")
    flag_draft = InitDraft(
        template=template,
        tool_overrides=(
            (Tool.DOCKER, True),
            (Tool.RUFF, False),
            (Tool.PYTEST, True),
        ),
        python_version="3.14",
        metadata=(("author_name", "Ada"), ("description", "Example")),
        collision_strategy=CollisionStrategy.MERGE,
    )
    editor_choices = tuple(
        (
            tool,
            False
            if tool is Tool.RUFF
            else True
            if tool in {Tool.PYTEST, Tool.DOCKER}
            else bool(getattr(config, tool)),
        )
        for tool in Tool
    )
    editor_draft = replace(
        flag_draft,
        tool_overrides=(),
        tool_choices=editor_choices,
        metadata=(("description", "Example"), ("author_name", "Ada")),
    )

    flag_modules, flag_request = resolve_init(flag_draft, config)
    editor_modules, editor_request = resolve_init(editor_draft, config)

    assert [type(module) for module in flag_modules] == [
        type(module) for module in editor_modules
    ]
    assert flag_request.recipe == editor_request.recipe
    assert flag_request.to_dict() == editor_request.to_dict()
    assert flag_request.is_external == editor_request.is_external


@pytest.mark.parametrize(
    ("flags", "expected_tools"),
    [
        (("--ruff", "--pytest"), {Tool.RUFF, Tool.PYTEST}),
        (("--mypy",), {Tool.MYPY}),
    ],
)
def test_tool_flag_combinations_plan_dev_dependencies_without_running_commands(
    tmp_path, monkeypatch, mocker, flags, expected_tools
):
    """CLI tool flags select their modules and packages during read-only planning."""
    monkeypatch.chdir(tmp_path)
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess.run"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen"))
    args = build_parser().parse_args(["init", *flags])
    overrides = tuple(
        (Tool(module.config_key), value)
        for module in TOOLING_MODULES
        if (value := getattr(args, module.__class__.__name__, None)) is not None
    )
    config = UserConfig(ruff=False, mypy=False, pytest=False)
    modules, request = resolve_init(
        InitDraft(tool_overrides=overrides, metadata=()), config
    )

    manifest = Orchestrator(modules, config, request=request).plan()

    assert {
        Tool(module.config_key) for module in modules if module.config_key
    } == expected_tools
    assert set(manifest.dependencies.dev_dependencies) & {"ruff", "mypy", "pytest"} == {
        tool.value for tool in expected_tools
    }


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
