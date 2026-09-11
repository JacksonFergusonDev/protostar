from collections.abc import Generator

import pytest

from protostar.config import (
    TemplateBlueprint,
    UserConfig,
    clear_user_config_cache,
)
from protostar.errors import (
    ConfigurationError,
    TemplateResolutionError,
)


@pytest.fixture(autouse=True)
def clear_config_cache() -> Generator[None, None, None]:
    """Clears the UserConfig singleton cache before and after each test.

    Ensures that disk I/O mocks in individual tests are evaluated correctly
    rather than returning a polluted instance from a previous test run.
    """
    clear_user_config_cache()
    yield
    clear_user_config_cache()


def test_user_config_ruff_toggle(mocker):
    """Test that the 'ruff' toggle correctly sets config.ruff = False."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mocker.patch("protostar.config.Path.read_text", return_value="[env]\nruff = false")

    config = UserConfig.load(force_reload=True)
    assert config.ruff is False


def test_user_config_parse_and_merge_handles_malformed_toml(mocker, tmp_path):
    """Test that a malformed TOML file raises a ConfigurationError."""
    mock_global_config = tmp_path / "config.toml"
    mock_global_config.write_text("invalid [ toml syntax === \n")

    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)

    with pytest.raises(
        ConfigurationError, match="Syntax error in configuration source"
    ):
        UserConfig.load(force_reload=True)


def test_user_config_raises_on_parsing_errors(tmp_path, monkeypatch) -> None:
    """Test that the parser hard-fails on unknown root keys."""
    mock_config_path = tmp_path / "config.toml"
    monkeypatch.setattr("protostar.config.CONFIG_FILE", mock_config_path)

    # Write a config with an invalid root key and an invalid type
    mock_config_path.write_text(
        "[unknown_root]\nfoo = 'bar'\n\n[env]\ndirenv = 'this-should-be-a-bool'\n"
    )

    with pytest.raises(ConfigurationError, match="Unrecognized root keys"):
        UserConfig.load(force_reload=True)


def test_user_config_runtime_type_validation() -> None:
    """Test that the parser catches invalid types and aborts execution."""
    payload_str = """
    [env]
    ide = 42
    direnv = "yes"
    python_version = ["3.12"]
    """
    with pytest.raises(ConfigurationError, match=r"Type mismatch.*ide"):
        UserConfig._parse_and_merge(payload_str, "dummy.toml", UserConfig())


def test_user_config_unknown_root_keys() -> None:
    """Test that the parser strictly enforces allowed root blocks."""
    payload_str = """
    [env]
    ide = "cursor"

    [presetz]
    latex = "minimal"

    [unknown_block]
    foo = "bar"
    """
    with pytest.raises(ConfigurationError, match="Unrecognized root keys") as exc_info:
        UserConfig._parse_and_merge(payload_str, "dummy.toml", UserConfig())

    # Assert both keys are present in the error message without relying on order
    error_msg = str(exc_info.value)
    assert "presetz" in error_msg
    assert "unknown_block" in error_msg


def test_user_config_ruff_invalid_type(mocker) -> None:
    """Test that an invalid type for the 'ruff' boolean triggers a ConfigurationError."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mocker.patch("protostar.config.Path.read_text", return_value='[env]\nruff = "yes"')

    with pytest.raises(ConfigurationError, match=r"Type mismatch.*ruff"):
        UserConfig.load(force_reload=True)


def test_template_blueprint_load_remote_target(mocker, tmp_path):
    """Test that HTTP/HTTPS override targets route to the network module."""
    # Patch the global variable to point to a sandboxed path that doesn't exist
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    def mock_resolve(url, temp_workspace):
        (temp_workspace / "protostar.toml").write_text(
            "[env]\nide = 'cursor'", encoding="utf-8"
        )
        return temp_workspace

    mock_resolve_patch = mocker.patch(
        "protostar.config.resolve_remote_template", side_effect=mock_resolve
    )

    config = TemplateBlueprint.load(target="https://example.com/config.toml")

    mock_resolve_patch.assert_called_once()
    assert mock_resolve_patch.call_args[0][0] == "https://example.com/config.toml"
    assert isinstance(config, TemplateBlueprint)


def test_template_blueprint_load_local_target_missing(mocker, tmp_path):
    """Test that a missing local override target raises a TemplateResolutionError."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    with pytest.raises(TemplateResolutionError, match="Configuration file not found"):
        TemplateBlueprint.load(target="definitely_does_not_exist_12345.toml")


def test_template_blueprint_load_local_target_with_context(mocker, tmp_path):
    """Test loading a local target with template placeholders satisfied by context."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    # Create a real sandboxed TOML file with a placeholder
    target = tmp_path / "custom.toml"
    target.write_text('[env]\npython_version = "<%py_ver%>"\n')

    config = TemplateBlueprint.load(
        target=str(target),
        template_context={"py_ver": "3.14"},
    )

    assert isinstance(config, TemplateBlueprint)


def test_template_blueprint_load_invokes_wizard_for_missing_vars(mocker, tmp_path):
    """Test that missing template variables trigger the interactive wizard via lazy import."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    target = tmp_path / "custom.toml"
    target.write_text('[env]\npython_version = "<%py_ver%>"\n')

    # Patch the source of the lazy import
    mock_wizard = mocker.patch(
        "protostar.wizard.resolve_missing_variables", return_value={"py_ver": "3.15"}
    )

    config = TemplateBlueprint.load(
        target=str(target),
        variable_resolver=mock_wizard,
    )

    mock_wizard.assert_called_once_with(["py_ver"])
    assert isinstance(config, TemplateBlueprint)


def test_template_blueprint_load_missing_vars_without_resolver_raises(mocker, tmp_path):
    """Verify that missing template variables raise an error when no resolver is provided."""
    # Patch global config file so we don't pick up the user's actual config
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "nonexistent.toml")

    target = tmp_path / "templated.toml"
    target.write_text('[env]\npython_version = "<%py_ver%>"\n')

    with pytest.raises(TemplateResolutionError, match="requires variables"):
        TemplateBlueprint.load(target=str(target))


def test_template_blueprint_load_late_binding_vars_do_not_prompt(mocker, tmp_path):
    """Verify that built-in late-binding variables (e.g. CURRENT_YEAR, AUTHOR_NAME) do not prompt."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "nonexistent.toml")

    target = tmp_path / "late_binding.toml"
    target.write_text(
        "[env]\n"
        'python_version = "<%PYTHON_VERSION%>"\n'
        'project_name = "<%PROJECT_NAME%>"\n'
        'package_name = "<%PACKAGE_NAME%>"\n'
        'current_year = "<%CURRENT_YEAR%>"\n'
        'author = "<%AUTHOR_NAME%>"\n'
    )

    blueprint = TemplateBlueprint.load(target=str(target))
    assert isinstance(blueprint, TemplateBlueprint)


def test_user_config_commitizen_defaults_to_false():
    """Test that commitizen defaults to False when not set in config."""
    config = UserConfig()
    assert config.commitizen is False


def test_user_config_commitizen_parsed_from_env(tmp_path):
    """Test that commitizen = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\ncommitizen = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.commitizen is True


def test_user_config_codecov_defaults_to_false():
    """Test that codecov defaults to False when not set in config."""
    config = UserConfig()
    assert config.codecov is False


def test_user_config_codecov_parsed_from_env(tmp_path):
    """Test that codecov = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\ncodecov = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.codecov is True


def test_user_config_zensical_defaults_to_false():
    """Test that zensical defaults to False when not set in config."""
    config = UserConfig()
    assert config.zensical is False


def test_user_config_zensical_parsed_from_env(tmp_path):
    """Test that zensical = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\nzensical = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.zensical is True


def test_user_config_readthedocs_defaults_to_false():
    """Test that readthedocs defaults to False when not set in config."""
    config = UserConfig()
    assert config.readthedocs is False


def test_user_config_readthedocs_parsed_from_env(tmp_path):
    """Test that readthedocs = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\nreadthedocs = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.readthedocs is True


def test_user_config_prek_defaults_to_false():
    """Test that prek defaults to False when not set in config."""
    config = UserConfig()
    assert config.prek is False


def test_user_config_prek_parsed_from_env(tmp_path):
    """Test that prek = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\nprek = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.prek is True


def test_user_config_ci_defaults_to_false():
    """Test that ci defaults to False when not set in config."""
    config = UserConfig()
    assert config.ci is False


def test_user_config_ci_parsed_from_env(tmp_path):
    """Test that ci = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\nci = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.ci is True


def test_user_config_release_defaults_to_false():
    """Test that release defaults to False when not set in config."""
    config = UserConfig()
    assert config.release is False


def test_user_config_release_parsed_from_env(tmp_path):
    """Test that release = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\nrelease = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.release is True


def test_user_config_ty_defaults_to_false():
    """Test that ty defaults to False when not set in config."""
    config = UserConfig()
    assert config.ty is False


def test_user_config_ty_parsed_from_env(tmp_path):
    """Test that ty = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\nty = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.ty is True


def test_user_config_pyrefly_defaults_to_false():
    """Test that pyrefly defaults to False when not set in config."""
    config = UserConfig()
    assert config.pyrefly is False


def test_user_config_pyrefly_parsed_from_env(tmp_path):
    """Test that pyrefly = true in [env] is correctly parsed into UserConfig."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\npyrefly = true\n")

    config = UserConfig.load(force_reload=True)
    assert config.pyrefly is True


def test_template_blueprint_parse():
    content = """
[dev]
dev_dependencies = ["bump-my-version"]

[dev.pyproject]
custom_ruff = "[tool.ruff]\\nline-length = 100"

[files]
"test.txt" = "hello"
"""
    blueprint = TemplateBlueprint._parse(content, source="test.toml")
    assert blueprint.dev_dependencies == ["bump-my-version"]
    assert (
        blueprint.pyproject_injections["custom_ruff"]
        == "[tool.ruff]\nline-length = 100"
    )
    assert blueprint.files["test.txt"] == "hello"


def test_template_blueprint_load_interpolation(tmp_path):
    target = tmp_path / "custom.toml"
    target.write_text('[files]\n"test.txt" = "<% greeting %>"\n')

    blueprint = TemplateBlueprint.load(
        target=str(target),
        template_context={"greeting": "hello world"},
    )

    assert blueprint.files["test.txt"] == "hello world"


def test_user_config_parses_template_aliases() -> None:
    """Verifies that shorthand string [templates] blocks are parsed into TemplateAliasConfig."""
    content = """
    [templates]
    corp-api = "https://raw.githubusercontent.com/org/repo/main/api.toml"
    local-base = "/Users/dev/templates/base.toml"
    """
    config = UserConfig._parse_and_merge(content, source="test", instance=UserConfig())

    assert "corp-api" in config.templates
    assert (
        config.templates["corp-api"].source
        == "https://raw.githubusercontent.com/org/repo/main/api.toml"
    )
    assert config.templates["corp-api"].name == "corp-api"
    assert config.templates["corp-api"].trusted is False
    assert config.templates["local-base"].source == "/Users/dev/templates/base.toml"


def test_user_config_parses_rich_template_table() -> None:
    """Verifies that table-format [templates.<alias>] blocks are parsed with full metadata."""
    content = """
    [templates.enterprise-api]
    name = "Enterprise API"
    source = "https://github.com/myorg/enterprise-template.git"
    description = "Internal enterprise microservice scaffold"
    trusted = true

    [templates.simple-api]
    source = "https://github.com/myorg/simple.git"
    """
    config = UserConfig._parse_and_merge(content, source="test", instance=UserConfig())

    ent = config.templates["enterprise-api"]
    assert ent.name == "Enterprise API"
    assert ent.source == "https://github.com/myorg/enterprise-template.git"
    assert ent.description == "Internal enterprise microservice scaffold"
    assert ent.trusted is True

    simple = config.templates["simple-api"]
    assert simple.name == "simple-api"
    assert simple.source == "https://github.com/myorg/simple.git"
    assert simple.description == ""
    assert simple.trusted is False


def test_user_config_rejects_invalid_templates_type() -> None:
    """Verifies that malformed [templates] blocks raise a ConfigurationError."""
    content = """
    [templates]
    corp-api = ["invalid", "list"]
    """
    with pytest.raises(ConfigurationError, match="Type mismatch"):
        UserConfig._parse_and_merge(content, source="test", instance=UserConfig())


def test_user_config_rejects_missing_source_in_table() -> None:
    """Verifies that [templates.<alias>] missing the 'source' key raises ConfigurationError."""
    content = """
    [templates.bad-alias]
    name = "Bad Alias"
    description = "Missing source key"
    """
    with pytest.raises(
        ConfigurationError, match="Missing or invalid required field 'source'"
    ):
        UserConfig._parse_and_merge(content, source="test", instance=UserConfig())


def test_user_config_rejects_unknown_fields_in_template_table() -> None:
    """Verifies that unrecognized keys in [templates.<alias>] raise ConfigurationError."""
    content = """
    [templates.bad-alias]
    source = "https://example.com"
    unknown_key = 123
    """
    with pytest.raises(
        ConfigurationError, match=r"Unrecognized fields in '\[templates.bad-alias\]'"
    ):
        UserConfig._parse_and_merge(content, source="test", instance=UserConfig())


def test_blueprint_extracts_tooling_overrides() -> None:
    """Verifies that root-level booleans are extracted while structural keys are ignored."""
    content = """
    dependencies = ["requests"]
    directories = ["src"]
    ruff = true
    mypy = false
    """
    blueprint = TemplateBlueprint._parse(content, source="test")

    # Structural keys should map to their respective fields
    assert blueprint.dependencies == ["requests"]
    assert blueprint.directories == ["src"]

    # Booleans should map to tooling_overrides
    assert blueprint.tooling_overrides.get("ruff") is True
    assert blueprint.tooling_overrides.get("mypy") is False

    # Structural keys must NOT bleed into tooling_overrides
    assert "dependencies" not in blueprint.tooling_overrides


def test_template_blueprint_parses_name_and_description() -> None:
    """Verifies that TemplateBlueprint correctly extracts top-level name and description."""
    content = """
    name = "Custom Stack"
    description = "Custom microservice stack description"
    dependencies = ["fastapi"]
    """
    blueprint = TemplateBlueprint._parse(content, source="custom.toml")
    assert blueprint.name == "Custom Stack"
    assert blueprint.description == "Custom microservice stack description"
    assert blueprint.dependencies == ["fastapi"]


def test_user_config_pre_commit_and_prek_mutually_exclusive() -> None:
    """Verifies that configuring both pre_commit and prek raises ConfigurationError."""
    with pytest.raises(
        ConfigurationError,
        match="Cannot configure both 'pre_commit = true' and 'prek = true'",
    ):
        UserConfig(pre_commit=True, prek=True)


def test_user_config_caching_and_cache_clear(mocker) -> None:
    """Verifies that UserConfig memoizes instances and clear_user_config_cache evicts them."""
    mocker.patch("protostar.config.Path.exists", return_value=False)

    cfg1 = UserConfig.load()
    cfg2 = UserConfig.load()
    assert cfg1 is cfg2

    clear_user_config_cache()
    cfg3 = UserConfig.load()
    assert cfg3 is not cfg1

    cfg4 = UserConfig.load(force_reload=True)
    assert cfg4 is not cfg3
