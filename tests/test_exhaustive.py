import importlib.resources
import os
import re
import subprocess
import tomllib

import pytest

from protostar.config import UserConfig
from protostar.templates import TemplateType, discover_templates

pytestmark = pytest.mark.exhaustive

BUILTIN_TEMPLATES = sorted(
    t.alias
    for t in discover_templates(config=UserConfig())
    if t.type == TemplateType.BUILT_IN
)

TEMPLATE_DEPENDENCY_MARKERS = {
    "astro": "photutils",
    "dsp": "librosa",
    "embedded": "pyserial",
    "ml": "torch",
    "api": "fastapi",
    "cli": "typer",
}


# Commands behind each quality flag, run the way the generated justfile runs them.
GATE_COMMANDS = {
    "ruff": (("ruff", "check", "."), ("ruff", "format", "--check", ".")),
    "mypy": (("mypy", "."),),
    "pytest": (("pytest",),),
}

# Gates that fail on a fresh scaffold today. The test requires the failing set to match
# this exactly, so a new failure is caught and fixing one forces its removal here.
KNOWN_GATE_GAPS: dict[str, set[str]] = {}


def _assert_skeleton_passes_its_gates(template, workspace):
    """A fresh scaffold must satisfy every quality gate its template switches on."""
    flags = tomllib.loads(
        importlib.resources.files("protostar.templates")
        .joinpath(f"{template}.toml")
        .read_text(encoding="utf-8")
    )
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    failures: dict[str, str] = {}
    for flag, commands in GATE_COMMANDS.items():
        if not flags.get(flag):
            continue
        for command in commands:
            result = subprocess.run(
                ["uv", "run", *command],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            if result.returncode != 0:
                failures[flag] = (
                    f"'{' '.join(command)}' exited {result.returncode}\n"
                    f"{result.stdout}\n{result.stderr}"
                )
                break

    expected = KNOWN_GATE_GAPS.get(template, set())
    assert set(failures) == expected, (
        f"{template}: gates failing on a fresh scaffold {sorted(failures)} != "
        f"known gaps {sorted(expected)}.\n" + "\n".join(failures.values())
    )


@pytest.mark.parametrize("template", BUILTIN_TEMPLATES)
def test_individual_template_scaffolding(run_cli, template):
    """Verifies that every built-in template scaffolds cleanly in isolation.

    The same scaffold is then held to its own quality gates, so each template is
    only built once per run (the ML environment alone is several gigabytes).
    """
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

    _assert_skeleton_passes_its_gates(template, workspace)


def test_api_dockerfile_targets_an_importable_app(run_cli):
    """The container's uvicorn target must resolve inside the scaffolded project."""
    code, stdout, stderr, workspace = run_cli(
        "init", "--python-version", "3.12", "--template", "api", "--docker"
    )
    assert code == 0, f"CLI Failed for template api.\n{stdout}\n{stderr}"

    dockerfile = (workspace / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r'CMD \["uvicorn", "([\w.]+):(\w+)"', dockerfile)
    assert match, f"No uvicorn CMD in the generated Dockerfile:\n{dockerfile}"
    module, attribute = match.groups()

    # The image runs `uv sync --no-dev` and then starts uvicorn from that environment.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-dev",
            "python",
            "-c",
            f"import importlib; getattr(importlib.import_module({module!r}), {attribute!r})",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, (
        f"Dockerfile starts uvicorn on '{module}:{attribute}', which cannot be "
        f"imported in the scaffolded project.\n{result.stderr}"
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
