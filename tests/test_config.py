from protostar.config import ProtostarConfig


def test_config_load_defaults(mocker):
    """Test configuration falls back to defaults if no config files exist."""
    # Patch the class-level method
    mocker.patch("protostar.config.Path.exists", return_value=False)

    config = ProtostarConfig.load()
    assert config.ide == "vscode"
    assert config.node_package_manager == "npm"
    assert config.presets == {}


def test_config_merge_cascade(mocker):
    """Test that local TOML overrides global TOML predictably."""
    mocker.patch("protostar.config.Path.exists", return_value=True)

    # Mock the global config payload
    global_payload = {
        "env": {"ide": "cursor", "node_package_manager": "pnpm"},
        "presets": {"latex": "minimal", "cpp": "standard"},
    }

    # Mock the local workspace override
    local_payload = {"env": {"ide": "jetbrains"}, "presets": {"latex": "science"}}

    # Intercept tomllib to return our mock payloads sequentially
    mocker.patch(
        "protostar.config.tomllib.load", side_effect=[global_payload, local_payload]
    )

    # Mock open to avoid actual I/O
    mocker.patch("builtins.open", mocker.mock_open())

    config = ProtostarConfig.load()

    # Verify the cascade execution
    assert config.ide == "jetbrains"  # Overridden by local
    assert config.node_package_manager == "pnpm"  # Persisted from global

    # Verify the presets dictionary was merged, not clobbered
    assert config.presets["latex"] == "science"
    assert config.presets["cpp"] == "standard"


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
