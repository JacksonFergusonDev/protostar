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


def test_config_merge_cascade(mocker):
    """Test that local TOML overrides global TOML predictably."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    # Mock the global config payload
    global_payload = {
        "env": {
            "ide": "cursor",
            "direnv": False,
            "python_package_manager": "pip",
            "python_version": "3.11",
            "node_package_manager": "pnpm",
            "ruff": False,
        },
        "presets": {"latex": "minimal", "cpp": "standard"},
    }

    # Mock the local workspace override
    local_payload = {
        "env": {
            "ide": "jetbrains",
            "direnv": True,
            "python_version": "3.12",
            "mypy": True,
            "pytest": True,
        },
        "presets": {"latex": "science"},
    }

    # Intercept tomllib to return our mock payloads sequentially
    mocker.patch(
        "protostar.config.tomllib.load", side_effect=[global_payload, local_payload]
    )

    # Mock open to avoid actual I/O
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load()

    assert config.ide == "jetbrains"
    assert config.direnv is True
    assert config.python_package_manager == "pip"
    assert config.python_version == "3.12"
    assert config.node_package_manager == "pnpm"
    assert config.ruff is False
    assert config.mypy is True
    assert config.pytest is True

    assert config.presets["latex"] == "science"
    assert config.presets["cpp"] == "standard"


def test_config_no_ruff_inversion(mocker):
    """Test that the 'no-ruff' toggle correctly inverts to config.ruff = False."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    payload = {"env": {"no-ruff": True}}

    mocker.patch("protostar.config.tomllib.load", return_value=payload)
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load()
    assert config.ruff is False


def test_parse_and_merge_handles_malformed_toml(mocker, caplog):
    """Test that a malformed TOML file does not crash the loading sequence."""
    import tomllib

    # Side effect sequence: True for global config, False for local config
    mocker.patch("protostar.config.Path.exists", side_effect=[True, False])
    mocker.patch("builtins.open", mocker.mock_open())

    # Force a syntax error
    mocker.patch(
        "protostar.config.tomllib.load",
        side_effect=tomllib.TOMLDecodeError("Invalid syntax", "", 0),
    )

    config = ProtostarConfig.load()

    # Should default gracefully
    assert config.ide == "vscode"
    assert "Config syntax error" in caplog.text
