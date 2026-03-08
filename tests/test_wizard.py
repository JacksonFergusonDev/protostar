import os

from protostar.config import ProtostarConfig
from protostar.modules import LANG_MODULES, TOOLING_MODULES, PythonModule, RuffModule
from protostar.presets import PRESETS
from protostar.presets.scientific import ScientificPreset
from protostar.wizard import (
    _should_run_wizard,
    run_discovery_wizard,
    run_generate_wizard,
    run_init_wizard,
)


def test_should_run_wizard_tty(mocker):
    """Test the TTY gate correctly identifies interactive terminals."""
    # Patch the entire sys module inside the wizard namespace to bypass Pytest's stream capturing
    mock_sys = mocker.patch("protostar.wizard.sys")
    mock_sys.stdin.isatty.return_value = True
    mock_sys.stdout.isatty.return_value = True
    assert _should_run_wizard() is True

    mock_sys.stdin.isatty.return_value = False
    assert _should_run_wizard() is False


def test_discovery_wizard_execution(mocker):
    """Test the discovery multiplexer parses questionary output."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    # Mock the chained questionary.select(...).ask() call
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "init"

    result = run_discovery_wizard()
    assert result == "init"


def test_init_wizard_state_mapping(mocker):
    """Test the init wizard translates checkbox selections to the state dictionary."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch(
        "protostar.wizard.ProtostarConfig.load", return_value=ProtostarConfig()
    )

    mock_checkbox = mocker.patch("questionary.checkbox")

    # Fetch the exact resident instances from the registry arrays to satisfy `item in ...` identity checks
    python_mod = next(m for m in LANG_MODULES if isinstance(m, PythonModule))
    ruff_mod = next(m for m in TOOLING_MODULES if isinstance(m, RuffModule))
    sci_preset = next(p for p in PRESETS if isinstance(p, ScientificPreset))

    # Simulate a user selecting Python, Ruff, the Scientific preset, and Docker
    mock_selections = [python_mod, ruff_mod, sci_preset, "docker"]
    mock_checkbox.return_value.ask.return_value = mock_selections

    result = run_init_wizard()

    assert result is not None
    assert len(result["modules"]) == 2
    assert isinstance(result["modules"][0], PythonModule)
    assert len(result["presets"]) == 1
    assert isinstance(result["presets"][0], ScientificPreset)
    assert result["docker"] is True


def test_generate_wizard_state_mapping(mocker):
    """Test the generate wizard correctly parses target and name strings."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "cpp_class"

    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = " AstroEngine "

    result = run_generate_wizard()

    assert result is not None
    assert result["target"] == "cpp_class"
    assert result["name"] == "AstroEngine"  # Verifies stripping


def test_wizards_abort_on_non_interactive(mocker):
    """Test all wizards safely return None if executed in a CI or piped environment."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=False)

    assert run_discovery_wizard() is None
    assert run_init_wizard() is None
    assert run_generate_wizard() is None


def test_benchmark_env_bypasses_tty_check(mocker):
    """Test that the benchmark env var forcefully passes the TTY gate."""
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})
    # Even if stdin is not a TTY, the benchmark flag overrides it
    mocker.patch("protostar.wizard.sys.stdin.isatty", return_value=False)
    assert _should_run_wizard() is True


def test_run_init_wizard_benchmark_abort(mocker):
    """Test that the init wizard correctly intercepts the benchmark flag before blocking."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})

    result = run_init_wizard()
    assert result is None


def test_run_init_wizard_cancellation(mocker):
    """Test that the init wizard safely handles user cancellation (Ctrl+C)."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch(
        "protostar.wizard.ProtostarConfig.load", return_value=ProtostarConfig()
    )
    mocker.patch.dict(os.environ, {}, clear=True)

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = None

    assert run_init_wizard() is None


def test_run_generate_wizard_cancellation_target(mocker):
    """Test that the generate wizard handles cancellation at the target prompt."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = None  # User aborts here

    assert run_generate_wizard() is None


def test_run_generate_wizard_cancellation_name(mocker):
    """Test that the generate wizard handles cancellation at the naming prompt."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "cpp_class"

    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None  # User aborts here (Ctrl+C)

    assert run_generate_wizard() is None
