from collections.abc import Generator
from pathlib import Path
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


def test_config_ruff_toggle(mocker):
    """Test that the 'ruff' toggle correctly sets config.ruff = False."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    payload = {"env": {"ruff": False}}

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    # Ensure we bypass the class cache for a clean read
    config = ProtostarConfig.load(force_reload=True)
    assert config.ruff is False


def test_parse_and_merge_handles_malformed_toml(mocker, tmp_path):
    """Test that a malformed TOML file raises a ConfigurationError instead of a generic ValueError."""

    # 1. Create a real, temporary file with deliberately broken TOML syntax
    mock_global_config = tmp_path / "config.toml"
    mock_global_config.write_text("invalid [ toml syntax === \n")

    # 2. Redirect the module's constants to point to our temporary sandboxed files
    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)

    # Execute the load sequence and expect a ConfigurationError bubbled up
    with pytest.raises(
        ConfigurationError, match="Syntax error in configuration file"
    ) as exc:
        protostar.config.ProtostarConfig.load()

    assert "Syntax error in configuration file" in str(exc.value)
    assert str(mock_global_config) in str(exc.value)


def test_config_advanced_overrides_parsing(mocker, tmp_path):
    """Test that dynamic parsing correctly extracts presets, dev tools, and raw TOML injections."""
    import protostar.config

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


def test_config_runtime_type_validation(mocker):
    """Test that the parser catches invalid types, drops them, and falls back to defaults."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    # Inject deliberately wrong Python primitive types
    payload = {
        "env": {
            "ide": 42,  # Expected string
            "direnv": "yes",  # Expected boolean
            "python_version": ["3.12"],  # Expected string or None
        }
    }

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig._parse_and_merge(Path("dummy.toml"), ProtostarConfig())

    assert config.ide is None
    assert config.direnv is False
    assert config.python_version == "3.13"

    # Verify the warnings told the user exactly what type was expected
    assert len(config._parsing_warnings) == 3


def test_config_unknown_root_keys(mocker):
    """Test that the parser warns about unrecognized or misspelled root blocks."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    payload = {
        "env": {"ide": "cursor"},
        "presetz": {"latex": "minimal"},  # Typo in root key
        "unknown_block": {"foo": "bar"},
    }

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    from pathlib import Path

    config = ProtostarConfig._parse_and_merge(Path("dummy.toml"), ProtostarConfig())

    # Should capture 1 warning for 'presetz' and 'unknown_block' combined (grouped by the parser)
    assert len(config._parsing_warnings) == 1
    assert "presetz" in config._parsing_warnings[0]


def test_config_ruff_invalid_type(mocker):
    """Test that an invalid type for the 'ruff' key triggers a generalized warning."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    # Pass a string instead of a boolean
    payload = {"env": {"ruff": "yes"}}

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load(force_reload=True)

    assert config.ruff is True
    assert len(config._parsing_warnings) == 1


def test_config_complex_generic_type_passthrough(mocker):
    """Test that complex generic types (like dicts/lists) in the env block bypass deep validation."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    # `presets` has a type of `dict[str, Any]` which resolves an origin of `dict`.
    # It should hit the `origin not in (None, types.UnionType, typing.Union)` early-continue block.
    payload = {"env": {"presets": {"custom_preset": "value"}}}

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load()

    # The dictionary should pass through successfully
    assert config.presets == {"custom_preset": "value"}


def test_config_captures_parsing_warnings(tmp_path, monkeypatch) -> None:
    # 1. Mock the CONFIG_FILE to point to our sandbox
    mock_config_path = tmp_path / "config.toml"
    monkeypatch.setattr("protostar.config.CONFIG_FILE", mock_config_path)

    # 2. Write a config with an invalid root key and an invalid type
    mock_config_path.write_text(
        "[unknown_root]\nfoo = 'bar'\n\n[env]\ndirenv = 'this-should-be-a-bool'\n"
    )

    # 3. Load the config (forcing reload to bypass singleton cache)
    config = ProtostarConfig.load(force_reload=True)

    # 4. Verify fallbacks worked
    assert config.direnv is False  # Fell back to default

    # 5. Verify warnings were captured silently without logging
    warnings = getattr(config, "_parsing_warnings", [])
    assert len(warnings) == 2
    assert any("Unrecognized root keys" in w for w in warnings)
    assert any("Invalid type for '[env].direnv'" in w for w in warnings)


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
