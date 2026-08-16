import pytest

pytestmark = pytest.mark.exhaustive

BUILTIN_TEMPLATES = [
    "astro",
    "dsp",
    "embedded",
    "ml",
    "api",
    "cli",
]

TEMPLATE_DEPENDENCY_MARKERS = {
    "astro": "photutils",
    "dsp": "librosa",
    "embedded": "pyserial",
    "ml": "torch",
    "api": "fastapi",
    "cli": "typer",
}


@pytest.mark.parametrize("template", BUILTIN_TEMPLATES)
def test_individual_template_scaffolding(run_cli, template):
    """Verifies that every built-in template scaffolds cleanly in isolation."""
    code, stdout, stderr, workspace = run_cli(
        "init",
        "--python-version",
        "3.12",
        "--template",
        template,
    )

    assert code == 0, (
        f"CLI Failed for template {template}.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    )

    pyproject_path = workspace / "pyproject.toml"
    assert pyproject_path.exists(), f"Missing pyproject.toml for template {template}"

    pyproject_data = pyproject_path.read_text()
    expected_dep = TEMPLATE_DEPENDENCY_MARKERS[template]
    assert expected_dep in pyproject_data, (
        f"Expected dependency '{expected_dep}' missing from pyproject.toml for template '{template}'."
    )


def test_malformed_cli_arguments(run_cli):
    """Verifies the CLI parser intercepts invalid boundaries and returns non-zero codes."""
    # 1. Unrecognized CLI flag
    code, *_ = run_cli("init", "--this-flag-is-completely-invalid")
    assert code != 0

    # 2. Mutually exclusive flags: --template and --from together
    code, *_ = run_cli(
        "init", "--template", "cli", "--from", "https://example.com/template.toml"
    )
    assert code != 0

    # 3. Non-existent built-in template
    code, *_ = run_cli("init", "--template", "non_existent_template_xyz")
    assert code != 0

    # 4. Unknown subcommand
    code, *_ = run_cli("unknown_subcommand")
    assert code != 0
