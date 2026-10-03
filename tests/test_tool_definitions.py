"""Tests verifying tool definition and configuration lockstep invariants."""

import dataclasses

import pytest

from protostar.config import UserConfig, default_config_content
from protostar.config_edit import EDITABLE_KEYS, TOOL_KEYS, config_values
from protostar.modules import TOOLING_MODULES
from protostar.recipe import Tool


def test_tooling_modules_and_tool_enum_lockstep() -> None:
    """Verifies that Tool enum members and TOOLING_MODULES are in exact 1-to-1 correspondence."""
    tool_values = {t.value for t in Tool}
    module_keys = {m.config_key for m in TOOLING_MODULES}

    assert tool_values == module_keys, (
        f"Mismatch between Tool enum and TOOLING_MODULES. "
        f"Missing in modules: {tool_values - module_keys}; "
        f"Missing in Tool enum: {module_keys - tool_values}"
    )


def test_user_config_has_all_tool_fields() -> None:
    """Verifies that UserConfig explicitly declares every Tool enum member."""
    field_names = {f.name for f in dataclasses.fields(UserConfig)}
    for tool in Tool:
        assert tool.value in field_names, (
            f"Tool '{tool.value}' is missing from UserConfig fields"
        )


def test_default_config_content_has_all_tools() -> None:
    """Verifies that default_config_content() includes commented toggle entries for all tools."""
    for tool in Tool:
        expected = f"# {tool.value} ="
        assert expected in default_config_content(), (
            f"Tool toggle '{expected}' is missing from default_config_content()"
        )


def test_config_edit_tool_keys_match_tools() -> None:
    """Verifies that TOOL_KEYS in config_edit includes all Tool values."""
    assert set(TOOL_KEYS) == {t.value for t in Tool}


def test_user_config_getattr_fallback_for_tools() -> None:
    """Verifies that UserConfig provides a safe fallback (False) for valid tool names."""
    config = UserConfig()
    # Test an existing tool
    assert config.ruff is True
    assert config.direnv is False

    # Non-tool attributes should still raise AttributeError
    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_setting'"):
        _ = config.nonexistent_setting


def test_config_values_handles_missing_attribute_gracefully() -> None:
    """Verifies that config_values does not crash if a tool attribute is missing from config."""
    # Create a minimal object that lacks some tool attributes
    dummy_config = object()
    values = config_values(dummy_config)  # type: ignore[arg-type]

    for key in EDITABLE_KEYS:
        assert key in values
        if key in TOOL_KEYS:
            assert values[key] is False
        else:
            assert values[key] is None
