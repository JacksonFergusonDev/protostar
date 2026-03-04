import contextlib
import sys

import pytest

from protostar.cli import main

# Omit from standard CI; explicitly invoked by Makefile
pytestmark = pytest.mark.benchmark


def safe_main():
    """Wraps main() to trap SystemExit, preventing pytest from tearing down."""
    with contextlib.suppress(SystemExit):
        main()


def test_startup_without_questionary(benchmark, mocker):
    """Benchmarks the fast-path execution (e.g., --help, config)."""
    mocker.patch.object(sys, "argv", ["protostar", "--help"])

    benchmark(safe_main)


def test_startup_with_questionary(benchmark, mocker):
    """Benchmarks the initialization latency when the TUI is triggered."""
    mocker.patch.object(sys, "argv", ["protostar", "init"])

    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = []

    mocker.patch("protostar.cli.Orchestrator")

    benchmark(safe_main)
