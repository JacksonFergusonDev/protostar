from collections.abc import Generator
from pathlib import Path

import pytest

import protostar.config
from protostar.config import ProtostarConfig
from protostar.errors import ConfigurationError


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
    mock_logger = mocker.patch("protostar.config.logger.warning")

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

    # Pass the payload directly into the parser
    config = ProtostarConfig._parse_and_merge(Path("dummy.toml"), ProtostarConfig())

    # Assert the malformed inputs were dropped and defaults were maintained
    assert config.ide is None

    assert config.direnv is False
    assert config.python_version == "3.13"

    # Verify the warnings told the user exactly what type was expected
    assert mock_logger.call_count == 3
    logged_text = " ".join(str(call.args[0]) for call in mock_logger.call_args_list)

    assert "Invalid type for '[env].ide'" in logged_text
    assert "Invalid type for '[env].direnv'" in logged_text
    assert "Invalid type for '[env].python_version'" in logged_text


def test_config_unknown_root_keys(mocker):
    """Test that the parser warns about unrecognized or misspelled root blocks."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mock_logger = mocker.patch("protostar.config.logger.warning")

    payload = {
        "env": {"ide": "cursor"},
        "presetz": {"latex": "minimal"},  # Typo in root key
        "unknown_block": {"foo": "bar"},
    }

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    from pathlib import Path

    ProtostarConfig._parse_and_merge(Path("dummy.toml"), ProtostarConfig())

    mock_logger.assert_called()
    logged_text = " ".join(str(call.args[0]) for call in mock_logger.call_args_list)

    assert "Unrecognized root keys" in logged_text
    assert "presetz" in logged_text
    assert "unknown_block" in logged_text


def test_config_ruff_invalid_type(mocker):
    """Test that an invalid type for the 'ruff' key triggers a generalized warning."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mock_logger = mocker.patch("protostar.config.logger.warning")

    # Pass a string instead of a boolean
    payload = {"env": {"ruff": "yes"}}

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load(force_reload=True)

    # Should safely drop the string and fall back to the True default
    assert config.ruff is True

    mock_logger.assert_called()
    logged_text = " ".join(str(call.args[0]) for call in mock_logger.call_args_list)

    # Assert against the dynamic type-checking warning string
    assert "Invalid type for '[env].ruff'" in logged_text
    assert "Expected <class 'bool'>" in logged_text


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
