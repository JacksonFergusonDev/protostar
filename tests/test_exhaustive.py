import itertools

import pytest

pytestmark = pytest.mark.exhaustive

# Generate all unique pairs of presets to ensure no configuration collisions occur
PRESET_COMBINATIONS = list(
    itertools.combinations(
        [
            "--scientific",
            "--astro",
            "--dsp",
            "--embedded",
            "--ml",
            "--api",
            "--cli",
        ],
        2,
    )
)


@pytest.mark.parametrize("preset_pair", PRESET_COMBINATIONS)
def test_preset_orthogonality(run_cli, preset_pair):
    """Verifies that loading multiple domain-specific presets does not cause manifest collisions."""
    code, stdout, stderr, workspace = run_cli(
        "init", "--python", "--python-version", "3.12", *preset_pair
    )

    assert code == 0, f"CLI Failed.\nSTDOUT: {stdout}\nSTDERR: {stderr}"

    # Explicitly check existence before reading to preserve string telemetry
    pyproject_path = workspace / "pyproject.toml"
    assert pyproject_path.exists(), (
        f"Missing pyproject.toml\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    )

    pyproject_data = pyproject_path.read_text()

    if "--scientific" in preset_pair:
        assert "numpy" in pyproject_data
    if "--astro" in preset_pair:
        assert "photutils" in pyproject_data
    if "--dsp" in preset_pair:
        assert "librosa" in pyproject_data
    if "--embedded" in preset_pair:
        assert "pyserial" in pyproject_data
    if "--ml" in preset_pair:
        assert "torch" in pyproject_data
    if "--api" in preset_pair:
        assert "fastapi" in pyproject_data
    if "--cli" in preset_pair:
        assert "typer" in pyproject_data


def test_malformed_cli_arguments(run_cli):
    """Verifies the CLI parser intercepts invalid boundaries and returns non-zero codes."""
    # Pass a genuinely unrecognized flag to guarantee argparse terminates with >0
    code, stdout, stderr, _ = run_cli("init", "--this-flag-is-completely-invalid")
    assert code != 0

    code_gen, stdout_gen, stderr_gen, _ = run_cli(
        "generate", "unknown_target", "TestName"
    )
    assert code_gen != 0
