from collections.abc import Generator

import pytest

from protostar.config import (
    ConfigOrigin,
    TemplateAliasConfig,
    TemplateBlueprint,
    TemplateSource,
    UserConfig,
    active_config_source,
    clear_user_config_cache,
    select_config_source,
)
from protostar.errors import (
    ConfigurationError,
    MissingTemplateVariablesError,
    TemplateResolutionError,
)
from protostar.intent import PyprojectPayload
from protostar.options import Condition, Term


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


def test_template_blueprint_load_remote_target(forge):
    """Test that HTTP/HTTPS override targets route to the network module."""
    forge.plain["https://example.com/config.toml"] = b"[env]\nide = 'cursor'"

    config = TemplateSource.load("https://example.com/config.toml").render({})

    assert forge.requests == ["https://example.com/config.toml"]
    assert isinstance(config, TemplateBlueprint)


def test_template_blueprint_load_local_target_missing(mocker, tmp_path):
    """Test that a missing local override target raises a TemplateResolutionError."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    with pytest.raises(TemplateResolutionError, match="Configuration file not found"):
        TemplateSource.load("definitely_does_not_exist_12345.toml")


def test_template_blueprint_load_local_target_with_context(mocker, tmp_path):
    """Test loading a local target with template placeholders satisfied by context."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    # Create a real sandboxed TOML file with a placeholder
    target = tmp_path / "custom.toml"
    target.write_text('[env]\npython_version = "<%py_ver%>"\n')

    config = TemplateSource.load(str(target)).render({"py_ver": "3.14"})

    assert isinstance(config, TemplateBlueprint)


def test_template_source_reports_its_custom_variables(mocker, tmp_path):
    """A caller can learn what to ask for before rendering anything."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    target = tmp_path / "custom.toml"
    target.write_text(
        '[env]\npython_version = "<%py_ver%>"\nname = "<% PROJECT_NAME %>"\n'
    )

    assert TemplateSource.load(str(target)).variables == {"py_ver"}


def test_template_source_render_missing_vars_raises(mocker, tmp_path):
    """Verify that rendering without a value for a custom variable raises."""
    # Patch global config file so we don't pick up the user's actual config
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "nonexistent.toml")

    target = tmp_path / "templated.toml"
    target.write_text('[env]\npython_version = "<%py_ver%>"\n')

    with pytest.raises(MissingTemplateVariablesError, match="py_ver"):
        TemplateSource.load(str(target)).render({})


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

    source = TemplateSource.load(str(target))
    assert source.variables == frozenset()
    assert isinstance(source.render({}), TemplateBlueprint)


def test_variables_table_declares_descriptions(tmp_path):
    target = tmp_path / "template.toml"
    target.write_text(
        '[files]\n"a.txt" = "<% REGION %> <% TIER %>"\n'
        '[variables.REGION]\ndescription = "Deployment region"\n'
    )

    source = TemplateSource.load(str(target))

    assert source.variables == frozenset({"REGION", "TIER"})
    assert source.descriptions == {"REGION": "Deployment region"}
    assert source.render({"REGION": "eu", "TIER": "gold"}).files == {"a.txt": "eu gold"}


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ('variables = "REGION"\n', "malformed"),
        ('[variables]\nREGION = "Deployment region"\n', "malformed"),
        ("[variables.REGION]\ndescription = 3\n", "malformed"),
        ('[variables.REGION]\ndescription = "x"\ndefault = "eu"\n', "malformed"),
        (
            '[variables.REGION]\ndescription = "x"\n[variables.ZONE]\ndescription = "y"\n',
            "never uses: ZONE",
        ),
        ('[variables.PROJECT_NAME]\ndescription = "x"\n', "never uses: PROJECT_NAME"),
    ],
)
def test_invalid_variables_table_stops_rendering(tmp_path, table, message):
    target = tmp_path / "template.toml"
    target.write_text(f'{table}[files]\n"a.txt" = "<% REGION %>"\n')
    source = TemplateSource.load(str(target))

    with pytest.raises(TemplateResolutionError, match=message):
        _ = source.descriptions
    with pytest.raises(TemplateResolutionError, match=message):
        source.render({"REGION": "eu"})


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
    assert blueprint.pyproject_injections["custom_ruff"] == PyprojectPayload(
        "[tool.ruff]\nline-length = 100"
    )
    assert blueprint.files["test.txt"] == "hello"


def test_template_blueprint_parses_a_tool_bound_payload():
    blueprint = TemplateBlueprint._parse(
        """
[dev.pyproject]
always = "[tool.hatch]\\nx = 1"

[dev.pyproject.typing]
requires = "mypy"
content = "[tool.mypy]\\nstrict = true"

[dev.pyproject.unbound_table]
content = "[tool.other]\\ny = 2"
""",
        source="test.toml",
    )

    assert blueprint.pyproject_injections == {
        "always": PyprojectPayload("[tool.hatch]\nx = 1"),
        "typing": PyprojectPayload(
            "[tool.mypy]\nstrict = true", Condition((Term("mypy"),))
        ),
        "unbound_table": PyprojectPayload("[tool.other]\ny = 2"),
    }


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("typing = 5", "Invalid structured payload"),
        ('[dev.pyproject.typing]\nrequires = "mypy"', "Invalid structured payload"),
        ("[dev.pyproject.typing]\ncontent = 5", "Invalid structured payload"),
        (
            '[dev.pyproject.typing]\ncontent = "[tool.x]"\ntool = "mypy"',
            "Invalid structured payload",
        ),
        (
            '[dev.pyproject.typing]\ncontent = "[tool.x]"\nrequires = "flake9"',
            "neither a tool nor a declared option",
        ),
        (
            '[dev.pyproject.typing]\ncontent = "[tool.x]"\nrequires = 5',
            "Invalid requires",
        ),
    ],
)
def test_template_blueprint_rejects_malformed_payloads(entry, message):
    body = entry if entry.startswith("[") else f"[dev.pyproject]\n{entry}"
    with pytest.raises(ConfigurationError, match=message):
        TemplateBlueprint._parse(body, source="test.toml")


def test_template_blueprint_load_interpolation(tmp_path):
    target = tmp_path / "custom.toml"
    target.write_text('[files]\n"test.txt" = "<% greeting %>"\n')

    blueprint = TemplateSource.load(str(target)).render({"greeting": "hello world"})

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


@pytest.mark.parametrize(
    ("content", "expected_err_snippet"),
    [
        ('name = ["not", "a", "string"]', "for 'name'"),
        ("description = 123", "for 'description'"),
        ('dependencies = "fastapi"', "for 'dependencies'"),
        ("dependencies = [123]", "for 'dependencies' elements"),
        ('directories = "src"', "for 'directories'"),
        ("directories = [true]", "for 'directories' elements"),
        ("vcs_ignores = 42", "for 'vcs_ignores'"),
        ("vcs_ignores = [{}]", "for 'vcs_ignores' elements"),
        ('docs_dependencies = "zensical"', "for 'docs_dependencies'"),
        ("docs_dependencies = [3.14]", "for 'docs_dependencies' elements"),
        ('system_tasks = "git init"', "for 'system_tasks'"),
        ('system_tasks = ["git", "init"]', "for 'system_tasks' command elements"),
        ('system_tasks = [["git", 123]]', "for 'system_tasks' command arguments"),
        ("post_install_tasks = true", "for 'post_install_tasks'"),
        (
            'post_install_tasks = ["uv", "sync"]',
            "for 'post_install_tasks' command elements",
        ),
        ('dev = "invalid"', "for '[dev]'"),
        ('dev = { dev_dependencies = "pytest" }', "for '[dev].dev_dependencies'"),
        ("dev = { dev_dependencies = [99] }", "for '[dev].dev_dependencies' elements"),
        ('dev = { pyproject = "not-a-table" }', "for '[dev].pyproject'"),
        ('files = "not-a-table"', "for '[files]'"),
        ('files = { "foo.txt" = 123 }', "for '[files].\"foo.txt\"'"),
        ('appends = "not-a-table"', "for '[appends]'"),
        ('appends = { "pyproject.toml" = 123 }', "for '[appends].pyproject.toml'"),
        (
            'appends = { "pyproject.toml" = [123] }',
            "for '[appends].pyproject.toml'",
        ),
    ],
)
def test_template_blueprint_parse_rejects_wrong_field_types(
    content: str, expected_err_snippet: str
) -> None:
    """Verifies that TemplateBlueprint._parse fails fast with ConfigurationError on type errors."""
    with pytest.raises(ConfigurationError) as exc_info:
        TemplateBlueprint._parse(content, source="invalid_blueprint.toml")

    assert expected_err_snippet in str(exc_info.value)
    assert exc_info.value.hint is not None


def test_template_blueprint_parses_optional_content():
    blueprint = TemplateBlueprint._parse(
        """
[dev]
dev_dependencies = ["always"]

[[optional]]
requires = "pytest"
dev_dependencies = ["pytest-cov", "httpx"]

[[optional]]
requires = ["mypy", "pytest"]
dependencies = ["typed"]
docs_dependencies = ["docs-extra"]
""",
        source="test.toml",
    )

    assert blueprint.dev_dependencies == ["always"]
    first, second = blueprint.optional
    assert str(first.requires) == "pytest"
    assert first.dev_dependencies == ("pytest-cov", "httpx")
    assert str(second.requires) == "mypy, pytest"
    assert second.dependencies == ("typed",)
    assert second.docs_dependencies == ("docs-extra",)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('[dev.tool_dependencies]\npytest = ["x"]', "Unknown keys"),
        ('[optional]\nrequires = "pytest"', "Expected an array of tables"),
        ('[[optional]]\ndev_dependencies = ["x"]', "Invalid"),
        ('[[optional]]\nrequires = "pytest"', "Invalid"),
        (
            '[[optional]]\nrequires = "flake9"\ndev_dependencies = ["x"]',
            "neither a tool",
        ),
        (
            '[[optional]]\nrequires = "pytest"\ndev_dependencies = "x"',
            "Expected an array",
        ),
        ('[[optional]]\nrequires = []\ndev_dependencies = ["x"]', "Invalid requires"),
        (
            '[[optional]]\nrequires = "a b"\ndev_dependencies = ["x"]',
            "Invalid requires",
        ),
        (
            '[[optional]]\nrequires = "ruff=on"\ndev_dependencies = ["x"]',
            "neither a tool",
        ),
    ],
)
def test_template_blueprint_rejects_malformed_optional_content(body, message):
    with pytest.raises(ConfigurationError, match=message):
        TemplateBlueprint._parse(body, source="test.toml")


def test_template_alias_shadowing_a_builtin_is_rejected():
    """A user alias may not reuse a built-in template name."""
    with pytest.raises(ConfigurationError) as excinfo:
        UserConfig(
            templates={
                "api": TemplateAliasConfig(source="https://example.com/api.toml")
            }
        )

    assert "reserved by the built-in template 'api'" in str(excinfo.value)
    assert excinfo.value.hint is not None


def test_template_alias_shadowing_a_builtin_is_case_insensitive():
    """Lookup folds case, so a case variant shadows the built-in just as badly."""
    with pytest.raises(ConfigurationError) as excinfo:
        UserConfig(
            templates={
                "API": TemplateAliasConfig(source="https://example.com/api.toml")
            }
        )

    assert "'API'" in str(excinfo.value)
    assert "built-in template 'api'" in str(excinfo.value)


def test_template_aliases_differing_only_by_case_are_rejected():
    """Two aliases that fold to one key leave the second unreachable."""
    with pytest.raises(ConfigurationError) as excinfo:
        UserConfig(
            templates={
                "acme": TemplateAliasConfig(source="https://example.com/one.toml"),
                "ACME": TemplateAliasConfig(source="https://example.com/two.toml"),
            }
        )

    assert "differ only by letter case" in str(excinfo.value)


def test_template_aliases_that_do_not_collide_are_accepted():
    """Distinct aliases alongside built-in names remain valid."""
    config = UserConfig(
        templates={
            "acme-api": TemplateAliasConfig(source="https://example.com/one.toml"),
            "acme-cli": TemplateAliasConfig(source="https://example.com/two.toml"),
        }
    )

    assert sorted(config.templates) == ["acme-api", "acme-cli"]


def test_active_config_source_defaults_to_the_standard_path(monkeypatch):
    """With nothing selected, the default location is read."""
    import protostar.config as config_module

    monkeypatch.delenv("PROTOSTAR_CONFIG", raising=False)
    source = active_config_source()

    assert source.origin is ConfigOrigin.DEFAULT
    assert source.path == config_module.CONFIG_FILE


def test_config_env_var_selects_an_explicit_file(monkeypatch, tmp_path):
    """PROTOSTAR_CONFIG redirects the run to a named file."""
    monkeypatch.setenv("PROTOSTAR_CONFIG", str(tmp_path / "team.toml"))
    source = active_config_source()

    assert source.origin is ConfigOrigin.EXPLICIT
    assert source.path == tmp_path / "team.toml"


def test_empty_config_env_var_disables_configuration(monkeypatch):
    """An empty PROTOSTAR_CONFIG is the CI form of --no-config."""
    monkeypatch.setenv("PROTOSTAR_CONFIG", "")
    source = active_config_source()

    assert source.origin is ConfigOrigin.DISABLED
    assert source.path is None


def test_cli_selection_outranks_the_environment(monkeypatch, tmp_path):
    """An explicit --config wins over an inherited PROTOSTAR_CONFIG."""
    monkeypatch.setenv("PROTOSTAR_CONFIG", str(tmp_path / "from_env.toml"))
    select_config_source(str(tmp_path / "from_flag.toml"))

    assert active_config_source().path == tmp_path / "from_flag.toml"


def test_selecting_a_file_and_disabling_together_is_rejected(tmp_path):
    """--config and --no-config express opposite intents."""
    with pytest.raises(ConfigurationError) as excinfo:
        select_config_source(str(tmp_path / "team.toml"), disabled=True)

    assert "Cannot combine" in str(excinfo.value)


def test_selected_config_file_is_loaded(tmp_path):
    """Values come from the selected file rather than the default location."""
    selected = tmp_path / "team.toml"
    selected.write_text('[env]\nauthor_name = "Acme Platform"\n', encoding="utf-8")
    select_config_source(str(selected))

    assert UserConfig.load().author_name == "Acme Platform"


def test_missing_selected_config_file_is_an_error(tmp_path):
    """A typo in an explicit path must not degrade silently to defaults."""
    select_config_source(str(tmp_path / "absent.toml"))

    with pytest.raises(ConfigurationError) as excinfo:
        UserConfig.load()

    assert "does not exist" in str(excinfo.value)
    assert excinfo.value.hint is not None


def test_missing_default_config_file_is_not_an_error(mocker, tmp_path):
    """The default location stays optional; absence just means defaults."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "absent.toml")
    clear_user_config_cache()

    assert UserConfig.load().author_name is None


def test_disabled_configuration_ignores_the_default_file(mocker, tmp_path):
    """--no-config yields built-in defaults even when a config file exists."""
    populated = tmp_path / "config.toml"
    populated.write_text('[env]\nauthor_name = "Ignored"\n', encoding="utf-8")
    mocker.patch("protostar.config.CONFIG_FILE", populated)
    select_config_source(None, disabled=True)

    assert UserConfig.load().author_name is None


def test_user_config_validates_python_version():
    with pytest.raises(ConfigurationError) as exc_info:
        UserConfig(python_version="invalid")
    assert "Invalid Python version: 'invalid'." in str(exc_info.value)
    assert exc_info.value.hint == "Python version must be a float value (e.g., '3.13')."

    with pytest.raises(ConfigurationError) as exc_info:
        UserConfig(python_version="2.7")
    assert "Invalid Python version: '2.7'." in str(exc_info.value)
    assert (
        exc_info.value.hint
        == "Python version is outside the accepted range (3.8 - 3.14)."
    )


def test_user_config_validates_github_username():
    with pytest.raises(ConfigurationError) as exc_info:
        UserConfig(github_username="@octocat")
    assert "Invalid GitHub username: '@octocat'." in str(exc_info.value)
    assert exc_info.value.hint == "Remove the leading '@' from GitHub username."

    with pytest.raises(ConfigurationError) as exc_info:
        UserConfig(github_username="-octocat")
    assert "Invalid GitHub username: '-octocat'." in str(exc_info.value)
    assert exc_info.value.hint is not None
    assert (
        "GitHub username may only contain alphanumeric characters"
        in exc_info.value.hint
    )
