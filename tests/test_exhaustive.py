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

    # Ensure no generated files contain trailing whitespace or lack a trailing newline
    for file_path in workspace.rglob("*"):
        if (
            file_path.is_file()
            and not file_path.name.endswith((".pyc", ".png", ".gif", ".ico", ".lock"))
            and ".git" not in file_path.parts
            and ".venv" not in file_path.parts
            and ".cache" not in file_path.parts
        ):
            text = file_path.read_text(encoding="utf-8")
            for line_idx, line in enumerate(text.splitlines(), 1):
                assert not line.endswith(" "), (
                    f"Trailing space in {file_path.relative_to(workspace)}:{line_idx}: {line!r}"
                )
                assert not line.endswith("\t"), (
                    f"Trailing tab in {file_path.relative_to(workspace)}:{line_idx}: {line!r}"
                )
            if text:
                assert text.endswith("\n"), (
                    f"Missing trailing newline in {file_path.relative_to(workspace)}"
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
