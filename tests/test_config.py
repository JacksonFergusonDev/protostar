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


def test_parse_and_merge_handles_malformed_toml(mocker, tmp_path):
    """Test that a malformed TOML file does not crash the loading sequence."""
    import protostar.config

    # 1. Create a real, temporary file with deliberately broken TOML syntax
    mock_global_config = tmp_path / "config.toml"
    mock_global_config.write_text("invalid [ toml syntax === \n")

    mock_local_config = tmp_path / ".protostar.toml"
    # We leave local config uncreated so exists() evaluates to False naturally

    # 2. Redirect the module's constants to point to our temporary sandboxed files
    mocker.patch("protostar.config.CONFIG_FILE", mock_global_config)
    mocker.patch("protostar.config.LOCAL_CONFIG_FILE", mock_local_config)

    # 3. Intercept rich.console.print to verify our error surfaced
    mock_print = mocker.patch("protostar.config.console.print")

    # Execute the load sequence
    config = protostar.config.ProtostarConfig.load()

    # The config should gracefully fall back to default values
    assert config.ide == "vscode"

    # Verify that the user was explicitly warned about the syntax error
    mock_print.assert_called_once()
    printed_text = mock_print.call_args[0][0]

    assert "[bold red]Config Error:[/bold red]" in printed_text
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
