from collections.abc import Generator
from typing import cast

import pytest

import protostar.config
from protostar.config import ProtostarConfig
from protostar.errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ConfigurationError,
    FileSystemError,
    MissingDependencyError,
    ProtostarError,
)


@pytest.fixture(autouse=True)
def clear_config_cache() -> Generator[None, None, None]:
    """Clears the ProtostarConfig singleton cache before and after each test.

    Ensures that disk I/O mocks in individual tests are evaluated correctly
    rather than returning a polluted instance from a previous test run.
    """
    ProtostarConfig._instance = None
    yield
    ProtostarConfig._instance = None


def test_config_advanced_overrides_parsing(mocker, tmp_path):
    """Test that dynamic parsing correctly extracts presets, dev tools, and raw TOML injections."""

    # Construct a complex configuration payload using the new schemas
    mock_global_config = tmp_path / "config.toml"
    mock_global_config.write_text(
        "[env]\n"
        'ide = "cursor"\n\n'
        "[presets.astro]\n"
        'dependencies = ["custom-astro-pkg"]\n'
        'dev_dependencies = ["pytest-benchmark"]\n'
        'directories = ["custom/data"]\n\n'
        "[dev]\n"
        'extra_dependencies = ["bump-my-version"]\n\n'
        "[dev.pyproject]\n"
        'custom_ruff = "[tool.ruff]\\nline-length = 100"\n'
    )

    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)

    config = protostar.config.ProtostarConfig.load()

    # 1. Verify dynamic field mapping (standard attributes)
    assert config.ide == "cursor"

    # 2. Verify nested preset dictionary extraction
    assert isinstance(config.presets["astro"], dict)
    assert config.presets["astro"]["dependencies"] == ["custom-astro-pkg"]
    assert config.presets["astro"]["dev_dependencies"] == ["pytest-benchmark"]
    assert config.presets["astro"]["directories"] == ["custom/data"]

    # 3. Verify global dev injections mapping
    assert config.global_dev_dependencies == ["bump-my-version"]

    # 4. Verify pyproject raw string injections mapping
    assert "custom_ruff" in config.pyproject_injections
    assert (
        config.pyproject_injections["custom_ruff"] == "[tool.ruff]\nline-length = 100"
    )


def test_protostar_error_hint_binding():
    err = ProtostarError("Failure summary", hint="Try turning it off and on again")
    assert err.hint == "Try turning it off and on again"
    assert str(err) == "Failure summary"


def test_missing_dependency_error_formatting():
    err = MissingDependencyError(
        dependency="direnv",
        purpose="environment switching",
        install_hint="brew install direnv",
    )
    assert err.dependency == "direnv"
    assert "required for environment switching" in str(err)
    assert err.hint == "brew install direnv"


def test_command_execution_error_properties():
    err = CommandExecutionError(["uv", "sync"], returncode=2, stderr="Resolution error")
    assert err.command == ["uv", "sync"]
    assert err.returncode == 2
    assert err.stderr == "Resolution error"


def test_command_timeout_error_defaults():
    err = CommandTimeoutError(["git", "clone"], timeout=30)
    assert err.timeout == 30
    # Cast to str to satisfy static analysis, as we know hint is not None here
    assert "stalled network request" in cast(str, err.hint)


def test_filesystem_error_unwraps_os_error():
    os_err = PermissionError(13, "Permission denied")
    err = FileSystemError("write", ".envrc", os_err)
    assert err.operation == "write"
    assert err.path == ".envrc"
    assert "Permission denied" in str(err)
    assert err.original == os_err


def test_config_ruff_toggle(mocker):
    """Test that the 'ruff' toggle correctly sets config.ruff = False."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mocker.patch("protostar.config.Path.read_text", return_value="[env]\nruff = false")

    config = ProtostarConfig.load(force_reload=True)
    assert config.ruff is False


def test_parse_and_merge_handles_malformed_toml(mocker, tmp_path):
    """Test that a malformed TOML file raises a ConfigurationError."""
    mock_global_config = tmp_path / "config.toml"
    mock_global_config.write_text("invalid [ toml syntax === \n")

    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)

    with pytest.raises(
        ConfigurationError, match="Syntax error in configuration source"
    ):
        ProtostarConfig.load(force_reload=True)


def test_config_raises_on_parsing_errors(tmp_path, monkeypatch) -> None:
    """Test that the parser hard-fails on unknown root keys."""
    mock_config_path = tmp_path / "config.toml"
    monkeypatch.setattr("protostar.config.CONFIG_FILE", mock_config_path)

    # Write a config with an invalid root key and an invalid type
    mock_config_path.write_text(
        "[unknown_root]\nfoo = 'bar'\n\n[env]\ndirenv = 'this-should-be-a-bool'\n"
    )

    with pytest.raises(ConfigurationError, match="Unrecognized root keys"):
        ProtostarConfig.load(force_reload=True)


def test_config_runtime_type_validation(mocker) -> None:
    """Test that the parser catches invalid types and aborts execution."""
    payload_str = """
    [env]
    ide = 42
    direnv = "yes"
    python_version = ["3.12"]
    """
    with pytest.raises(ConfigurationError, match=r"Type mismatch.*ide"):
        ProtostarConfig._parse_and_merge(payload_str, "dummy.toml", ProtostarConfig())


def test_config_unknown_root_keys(mocker) -> None:
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
        ProtostarConfig._parse_and_merge(payload_str, "dummy.toml", ProtostarConfig())

    # Assert both keys are present in the error message without relying on order
    error_msg = str(exc_info.value)
    assert "presetz" in error_msg
    assert "unknown_block" in error_msg


def test_config_ruff_invalid_type(mocker) -> None:
    """Test that an invalid type for the 'ruff' boolean triggers a ConfigurationError."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mocker.patch("protostar.config.Path.read_text", return_value='[env]\nruff = "yes"')

    with pytest.raises(ConfigurationError, match=r"Type mismatch.*ruff"):
        ProtostarConfig.load(force_reload=True)


def test_config_complex_generic_type_passthrough(mocker):
    """Test that complex generic types (like dicts/lists) bypass deep validation."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mocker.patch(
        "protostar.config.Path.read_text",
        return_value='[presets]\ncustom_preset = "value"',
    )

    config = ProtostarConfig.load(force_reload=True)
    assert config.presets.get("custom_preset") == "value"


def test_config_load_remote_target(mocker, tmp_path):
    """Test that HTTP/HTTPS override targets route to the network module."""
    # Patch the global variable to point to a sandboxed path that doesn't exist
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    # Patch the source of the lazy import, not the config module
    mock_fetch = mocker.patch(
        "protostar.config.fetch_remote_config", return_value="[env]\nide = 'cursor'"
    )

    config = ProtostarConfig.load(
        force_reload=True, override_target="https://example.com/config.toml"
    )

    mock_fetch.assert_called_once_with("https://example.com/config.toml")
    assert config.ide == "cursor"


def test_config_load_local_target_missing(mocker, tmp_path):
    """Test that a missing local override target raises a ConfigurationError."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        ProtostarConfig.load(
            force_reload=True, override_target="definitely_does_not_exist_12345.toml"
        )


def test_config_load_local_target_with_context(mocker, tmp_path):
    """Test loading a local target with template placeholders satisfied by context."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    # Create a real sandboxed TOML file with a placeholder
    target = tmp_path / "custom.toml"
    target.write_text('[env]\npython_version = "{{py_ver}}"\n')

    config = ProtostarConfig.load(
        force_reload=True,
        override_target=str(target),
        template_context={"py_ver": "3.14"},
    )

    assert config.python_version == "3.14"


def test_config_load_invokes_wizard_for_missing_vars(mocker, tmp_path):
    """Test that missing template variables trigger the interactive wizard via lazy import."""
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "fake_global.toml")

    target = tmp_path / "custom.toml"
    target.write_text('[env]\npython_version = "{{py_ver}}"\n')

    # Patch the source of the lazy import
    mock_wizard = mocker.patch(
        "protostar.wizard.resolve_missing_variables", return_value={"py_ver": "3.15"}
    )

    config = ProtostarConfig.load(
        force_reload=True,
        override_target=str(target),
        variable_resolver=mock_wizard,
    )

    mock_wizard.assert_called_once_with(["py_ver"])
    assert config.python_version == "3.15"


def test_config_load_missing_vars_without_resolver_raises(mocker, tmp_path):
    """Verify that missing template variables raise an error when no resolver is provided."""
    # Patch global config file so we don't pick up the user's actual config
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "nonexistent.toml")

    target = tmp_path / "templated.toml"
    target.write_text('[env]\npython_version = "{{py_ver}}"\n')

    with pytest.raises(ConfigurationError, match="requires variables"):
        ProtostarConfig.load(force_reload=True, override_target=str(target))


def test_config_active_presets(mocker, tmp_path):
    """Test that active_presets is correctly parsed and footgun protection works."""
    mock_global_config = tmp_path / "valid.toml"
    mock_global_config.write_text('[env]\nactive_presets = ["astro", "cli"]\n')

    # Using as override_target should parse successfully
    config = ProtostarConfig.load(
        override_target=str(mock_global_config), force_reload=True
    )
    assert config.active_presets == ["astro", "cli"]

    # Setting it as the global config file should trigger the footgun trap
    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)
    with pytest.raises(
        ConfigurationError, match="not allowed in the global configuration file"
    ):
        ProtostarConfig.load(force_reload=True, override_target=None)
