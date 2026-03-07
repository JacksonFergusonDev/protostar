import pytest

from protostar.config import ProtostarConfig


def test_config_load_defaults(mocker):
    """Test configuration falls back to defaults if no config files exist."""
    mocker.patch("protostar.config.Path.exists", return_value=False)

    config = ProtostarConfig.load()
    assert config.ide == "vscode"
    assert config.direnv is False
    assert config.node_package_manager == "npm"
    assert config.python_package_manager == "uv"
    assert config.python_version is None
    assert config.ruff is True
    assert config.mypy is False
    assert config.pytest is False
    assert config.pre_commit is False
    assert config.presets == {}


def test_config_scope_enforcement(mocker):
    """Test that local TOML files cannot override global init blocks (env, presets, dev)."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mock_print = mocker.patch("protostar.config.console.print")

    # Mock the global config payload
    global_payload = {
        "env": {
            "ide": "cursor",
            "python_version": "3.11",
        },
        "presets": {"latex": "minimal"},
    }

    # Mock the local workspace override (these should be stripped!)
    local_payload = {
        "env": {
            "ide": "jetbrains",
            "python_version": "3.12",
        },
        "presets": {"latex": "science"},
    }

    # Intercept tomllib to return our mock payloads sequentially
    mocker.patch(
        "protostar.config.tomllib.load", side_effect=[global_payload, local_payload]
    )
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load()

    # Assert that the global values were preserved and local overrides were actively ignored
    assert config.ide == "cursor"
    assert config.python_version == "3.11"
    assert config.presets["latex"] == "minimal"

    # Verify the scope warning was surfaced to the user
    mock_print.assert_called()
    printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)

    assert "Scope Warning" in printed_text
    assert "env" in printed_text
    assert "presets" in printed_text


def test_config_no_ruff_inversion(mocker):
    """Test that the 'no-ruff' toggle correctly inverts to config.ruff = False."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    payload = {"env": {"no-ruff": True}}

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load()
    assert config.ruff is False


def test_parse_and_merge_handles_malformed_toml(mocker, tmp_path):
    """Test that a malformed TOML file aborts the loading sequence."""
    import protostar.config

    # 1. Create a real, temporary file with deliberately broken TOML syntax
    mock_global_config = tmp_path / "config.toml"
    mock_global_config.write_text("invalid [ toml syntax === \n")

    mock_local_config = tmp_path / ".protostar.toml"

    # 2. Redirect the module's constants to point to our temporary sandboxed files
    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)
    mocker.patch("protostar.config.LOCAL_CONFIG_FILE", mock_local_config)

    # 3. Intercept rich.console.print to verify our error surfaced
    mock_print = mocker.patch("protostar.config.console.print")

    # Execute the load sequence and expect a clean abort
    with pytest.raises(SystemExit) as exc:
        protostar.config.ProtostarConfig.load()

    assert exc.value.code == 1

    # Verify that the user was explicitly warned about the syntax error
    mock_print.assert_called()
    printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)

    assert "Fatal Configuration Error" in printed_text
    assert "Syntax error in" in printed_text
    assert str(mock_global_config) in printed_text


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

    mock_local_config = tmp_path / ".protostar.toml"

    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)
    mocker.patch("protostar.config.LOCAL_CONFIG_FILE", mock_local_config)

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
    mock_print = mocker.patch("protostar.config.console.print")

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
    from pathlib import Path

    config = ProtostarConfig._parse_and_merge(Path("dummy.toml"), ProtostarConfig())

    # Assert the malformed inputs were dropped and defaults were maintained
    assert config.ide == "vscode"
    assert config.direnv is False
    assert config.python_version is None

    # Verify the warnings told the user exactly what type was expected
    assert mock_print.call_count == 3
    printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)

    assert "Invalid type for '[env].ide'" in printed_text
    assert "Invalid type for '[env].direnv'" in printed_text
    assert "Invalid type for '[env].python_version'" in printed_text


def test_config_unknown_root_keys(mocker):
    """Test that the parser warns about unrecognized or misspelled root blocks."""
    mocker.patch("protostar.config.Path.exists", return_value=True)
    mock_print = mocker.patch("protostar.config.console.print")

    payload = {
        "env": {"ide": "cursor"},
        "presetz": {"latex": "minimal"},  # Typo in root key
        "unknown_block": {"foo": "bar"},
    }

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    from pathlib import Path

    ProtostarConfig._parse_and_merge(Path("dummy.toml"), ProtostarConfig())

    mock_print.assert_called()
    printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)

    assert "Unrecognized root keys" in printed_text
    assert "presetz" in printed_text
    assert "unknown_block" in printed_text
