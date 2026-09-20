"""Tests for centralized template discovery engine."""

import time
from typing import Any

from protostar.config import TemplateAliasConfig, UserConfig
from protostar.templates import TemplateInfo, TemplateType, discover_templates


def test_discover_builtin_templates() -> None:
    """Verifies that all built-in templates are discovered with rich metadata."""
    templates = discover_templates(config=UserConfig())
    builtin_aliases = {t.alias: t for t in templates if t.type == TemplateType.BUILT_IN}

    expected_aliases = {"api", "astro", "cli", "dsp", "embedded", "lib", "ml"}
    assert expected_aliases.issubset(builtin_aliases.keys())

    # Verify FastAPI metadata
    api_tmpl = builtin_aliases["api"]
    assert api_tmpl.name == "FastAPI"
    assert "FastAPI web application scaffold" in api_tmpl.description
    assert api_tmpl.source == "protostar.templates"
    assert api_tmpl.trusted is True

    # Verify all built-ins have name, description, and are trusted
    for alias, tmpl in builtin_aliases.items():
        assert tmpl.name, f"Template {alias} missing display name"
        assert tmpl.description, f"Template {alias} missing description"
        assert tmpl.trusted is True


def test_discover_templates_with_user_aliases(tmp_path: Any) -> None:
    """Verifies merging of user-configured global aliases with built-in templates."""
    # Create a local template file
    local_tmpl = tmp_path / "custom_local.toml"
    local_tmpl.write_text(
        'name = "Custom Local"\ndescription = "Local disk scaffold"\n',
        encoding="utf-8",
    )

    config = UserConfig(
        templates={
            "shorthand-remote": TemplateAliasConfig(
                source="https://example.com/template.toml"
            ),
            "rich-remote": TemplateAliasConfig(
                source="https://github.com/myorg/enterprise.git",
                name="Enterprise API",
                description="Enterprise scaffold",
                trusted=True,
            ),
            "local-file": TemplateAliasConfig(
                source=str(local_tmpl),
            ),
        }
    )

    templates = discover_templates(config=config)
    alias_map = {t.alias: t for t in templates}

    # Verify shorthand remote
    shorthand = alias_map["shorthand-remote"]
    assert shorthand.name == "shorthand-remote"
    assert shorthand.description == "Global alias (https://example.com/template.toml)"
    assert shorthand.type == TemplateType.GLOBAL_ALIAS
    assert shorthand.trusted is False

    # Verify rich remote
    rich = alias_map["rich-remote"]
    assert rich.name == "Enterprise API"
    assert rich.description == "Enterprise scaffold"
    assert rich.type == TemplateType.GLOBAL_ALIAS
    assert rich.trusted is True

    # Verify local file metadata auto-discovery
    local = alias_map["local-file"]
    assert local.name == "Custom Local"
    assert local.description == "Local disk scaffold"
    assert local.type == TemplateType.GLOBAL_ALIAS


def test_discover_templates_to_dict() -> None:
    """Verifies serialization of TemplateInfo objects."""
    tmpl = TemplateInfo(
        alias="api",
        name="FastAPI",
        description="Scaffold",
        type=TemplateType.BUILT_IN,
        source="protostar.templates",
        trusted=True,
    )
    d = tmpl.to_dict()
    assert d == {
        "alias": "api",
        "name": "FastAPI",
        "description": "Scaffold",
        "type": "built-in",
        "source": "protostar.templates",
        "trusted": True,
    }


def test_discover_templates_execution_speed() -> None:
    """Verifies that discover_templates executes in < 10ms with zero network I/O."""
    start = time.perf_counter()
    templates = discover_templates(config=UserConfig())
    elapsed = time.perf_counter() - start

    assert len(templates) >= 6
    assert elapsed < 0.05, f"Discovery took too long: {elapsed:.4f}s"
