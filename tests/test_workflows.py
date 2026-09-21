from dataclasses import replace

import pytest

from protostar.workflows import (
    AgentsSpec,
    CIFlag,
    CIWorkflowSpec,
    DockerfileSpec,
    HookRunner,
    JustfileSpec,
    YAMLBuilder,
    generate_agents_md,
    generate_ci_workflow,
    generate_dockerfile,
    generate_dockerignore,
    generate_gitignore,
    generate_justfile,
    generate_pre_commit_config,
    generate_release_workflow,
)


def test_generate_pre_commit_config_basic():
    content = generate_pre_commit_config(
        local_hooks=[], remote_hooks=[], core_rev="v6.0.0", gitleaks_rev="v8.24.0"
    )
    assert "repos:" in content
    assert "repo: https://github.com/pre-commit/pre-commit-hooks" in content
    assert "rev: v6.0.0" in content
    assert "check-added-large-files" in content
    assert "check-merge-conflict" in content
    assert "check-case-conflict" in content
    assert "check-symlinks" in content
    assert "check-executables-have-shebangs" in content
    assert "trailing-whitespace" in content
    assert "end-of-file-fixer" in content
    assert "check-yaml" in content
    assert "check-json" in content
    assert "check-toml" in content
    assert "repo: local" in content
    assert "uv-lock-check" in content
    assert "gitleaks" in content

    # Verify structural ordering: generic hooks -> repo: local -> remote repos (gitleaks)
    pos_generic = content.find("repo: https://github.com/pre-commit/pre-commit-hooks")
    pos_local = content.find("repo: local")
    pos_gitleaks = content.find("https://github.com/gitleaks/gitleaks")
    assert pos_generic < pos_local < pos_gitleaks


def test_generate_pre_commit_config_prek():
    content = generate_pre_commit_config(
        local_hooks=[],
        remote_hooks=[],
        core_rev="v6.0.0",
        gitleaks_rev="v8.24.0",
        hook_runner=HookRunner.PREK,
    )
    assert "repos:" in content
    assert "repo: builtin" in content
    assert "check-added-large-files" in content
    assert "check-merge-conflict" in content
    assert "check-case-conflict" in content
    assert "check-symlinks" in content
    assert "check-executables-have-shebangs" in content
    assert "trailing-whitespace" in content
    assert "end-of-file-fixer" in content
    assert "check-yaml" in content
    assert "check-json" in content
    assert "check-toml" in content
    assert "repo: local" in content
    assert "uv-lock-check" in content
    assert "gitleaks" in content

    # Verify structural ordering: builtin -> repo: local -> remote repos (gitleaks)
    pos_builtin = content.find("repo: builtin")
    pos_local = content.find("repo: local")
    pos_gitleaks = content.find("https://github.com/gitleaks/gitleaks")
    assert pos_builtin < pos_local < pos_gitleaks


def test_generate_pre_commit_config_local_and_remote_hooks():
    local_hooks = [
        """      - id: ruff
        name: ruff
        entry: uv run ruff check --fix
        language: system"""
    ]
    remote_hooks = [
        """  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff"""
    ]
    content = generate_pre_commit_config(
        local_hooks=local_hooks,
        remote_hooks=remote_hooks,
        core_rev="v6.0.0",
        gitleaks_rev="v8.24.0",
    )
    assert "repo: local" in content
    assert "uv run ruff check --fix" in content
    assert "https://github.com/astral-sh/ruff-pre-commit" in content

    # Verify structural ordering: generic -> repo: local -> gitleaks -> other remote hooks
    pos_generic = content.find("repo: https://github.com/pre-commit/pre-commit-hooks")
    pos_local = content.find("repo: local")
    pos_gitleaks = content.find("https://github.com/gitleaks/gitleaks")
    pos_custom_remote = content.find("https://github.com/astral-sh/ruff-pre-commit")
    assert pos_generic < pos_local < pos_gitleaks < pos_custom_remote


def test_generate_pre_commit_config_with_commit_msg_hook_type():
    commitizen_hook = """  # Commit message validation
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.8.3
    hooks:
      - id: commitizen
        stages: [commit-msg]"""
    content = generate_pre_commit_config(
        local_hooks=[],
        remote_hooks=[commitizen_hook],
        core_rev="v6.0.0",
        gitleaks_rev="v8.24.0",
        install_hook_types={"commit-msg"},
    )
    expected_header = (
        "default_install_hook_types:\n"
        "  - pre-commit\n"
        "  - commit-msg\n"
        "\n"
        "default_stages:\n"
        "  - pre-commit\n"
        "\n"
        "repos:\n"
    )
    assert content.startswith(expected_header)
    assert "https://github.com/commitizen-tools/commitizen" in content


def test_generate_pre_commit_config_without_commit_msg_hook_type():
    content = generate_pre_commit_config(
        local_hooks=[],
        remote_hooks=[],
        core_rev="v6.0.0",
        gitleaks_rev="v8.24.0",
        install_hook_types=set(),
    )
    assert content.startswith("default_install_hook_types:\n")
    assert "default_install_hook_types:\n  - pre-commit" in content
    assert "default_stages:\n  - pre-commit" in content


def test_generate_pre_commit_config_mypy_dependencies_interpolation():
    local_hooks = [
        """      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        additional_dependencies:
<% MYPY_DEPENDENCIES %>"""
    ]
    # With dependencies
    content = generate_pre_commit_config(
        local_hooks=local_hooks,
        remote_hooks=[],
        core_rev="v6.0.0",
        gitleaks_rev="v8.24.0",
        dependencies=["fastapi", "pydantic"],
    )
    assert "          - fastapi\n          - pydantic" in content
    assert "<% MYPY_DEPENDENCIES %>" not in content

    # Without dependencies
    content_empty = generate_pre_commit_config(
        local_hooks=local_hooks,
        remote_hooks=[],
        core_rev="v6.0.0",
        gitleaks_rev="v8.24.0",
        dependencies=[],
    )
    assert "additional_dependencies:" not in content_empty
    assert "<% MYPY_DEPENDENCIES %>" not in content_empty


def test_generate_ci_workflow_default():
    content = generate_ci_workflow(
        CIWorkflowSpec(
            supported_os=["Linux"],
            min_python="3.13",
            ci_flags=set(),
            ci_steps=[],
        )
    )
    assert 'os: ["ubuntu-latest"]' in content
    assert '"3.13"' in content
    assert "Install uv" in content
    assert "cache-dependency-glob" not in content
    assert "Install dependencies" in content
    assert "uv sync --all-extras --dev --locked" in content


def test_generate_ci_workflow_matrix():
    content = generate_ci_workflow(
        CIWorkflowSpec(
            supported_os=["Linux", "MacOS", "Windows"],
            min_python="3.11",
            ci_flags=set(),
            ci_steps=[],
        )
    )
    assert '"ubuntu-latest"' in content
    assert '"macos-latest"' in content
    assert '"windows-latest"' in content
    assert '"3.11"' in content
    assert '"3.12"' in content
    assert '"3.13"' in content


def test_generate_ci_workflow_pytest_and_codecov():
    # Pytest alone
    content_pytest = generate_ci_workflow(
        CIWorkflowSpec(
            supported_os=["Linux"],
            min_python="3.13",
            ci_flags={"pytest"},
            ci_steps=[],
        )
    )
    assert "Run Tests" in content_pytest
    assert "Upload coverage to Codecov" not in content_pytest

    # Pytest with Codecov
    content_codecov = generate_ci_workflow(
        CIWorkflowSpec(
            supported_os=["Linux", "MacOS"],
            min_python="3.12",
            ci_flags={"pytest", "codecov"},
            ci_steps=["      - name: Lint\n        run: uv run ruff check"],
        )
    )
    assert "Run tests with coverage # (for Codecov)" in content_codecov
    assert "name: Lint & Type Check" in content_codecov
    assert "coverage: true" in content_codecov
    assert "if: matrix.coverage" in content_codecov
    assert "if: ${{ !matrix.coverage }}" in content_codecov
    assert "Upload coverage to Codecov" in content_codecov
    assert "Upload test analytics to Codecov" in content_codecov
    assert (
        "Run: uv run ruff check" in content_codecov
        or "uv run ruff check" in content_codecov
    )


def test_generate_release_workflow():
    content = generate_release_workflow()
    assert "name: Release" in content
    assert 'tags:\n      - "v*"' in content
    assert "pypa/gh-action-pypi-publish" in content
    assert "uv build" in content


def test_generate_justfile():
    content = generate_justfile(
        JustfileSpec(
            format_commands=["uv run ruff format src tests"],
            lint_commands=["uv run ruff check src tests"],
            typecheck_commands=["uv run mypy ."],
            ci_flags={"pytest", "zensical"},
            clean_paths=["dist", "build"],
        )
    )
    assert "format: sync" in content
    assert "uv run ruff format src tests" in content
    assert "lint: sync" in content
    assert "uv run ruff check src tests" in content
    assert "typecheck: sync" in content
    assert "uv run mypy ." in content
    assert "test: sync" in content
    assert "test-cov: sync" in content
    assert "ci: lint typecheck test" in content
    assert "clean:" in content
    assert "htmlcov" in content
    assert "serve: sync" in content
    assert "uv run zensical serve -o" in content
    assert "yellow :=" not in content


def test_generate_workflows_with_ciflag_enum():
    from protostar.workflows import CIFlag, TargetOS

    content_ci = generate_ci_workflow(
        CIWorkflowSpec(
            supported_os=[TargetOS.LINUX, TargetOS.MACOS],
            min_python="3.12",
            ci_flags={CIFlag.PYTEST, CIFlag.CODECOV},
            ci_steps=[],
        )
    )
    assert "Run tests with coverage # (for Codecov)" in content_ci
    assert "Upload coverage to Codecov" in content_ci

    content_just = generate_justfile(
        JustfileSpec(
            format_commands=[],
            lint_commands=[],
            typecheck_commands=[],
            ci_flags={CIFlag.PYTEST, CIFlag.ZENSICAL},
            clean_paths=[],
        )
    )
    assert "test: sync" in content_just
    assert "serve: sync" in content_just
    assert "htmlcov" in content_just


def test_generate_dockerignore_fresh_and_existing():
    # Fresh
    res = generate_dockerignore(vcs_ignores={"*.log", ".env"}, has_uv_init=True)
    assert res is not None
    assert ".git/" in res
    assert ".python-version" in res
    assert "*.log" in res
    assert ".env" in res

    # Existing content - no change
    res_none = generate_dockerignore(
        vcs_ignores={"*.log"},
        has_uv_init=False,
        existing_content=res,
    )
    assert res_none is None


def test_generate_dockerfile_variants():
    # Default variant
    df_default = generate_dockerfile(
        DockerfileSpec(
            python_version="3.13",
            project_name="my-app",
            package_name="my_app",
            dependencies=["rich"],
            is_script_or_typer=False,
        )
    )
    assert 'CMD ["python", "-m", "my_app"]' in df_default
    assert "FROM python:3.13-slim-bookworm AS runtime" in df_default

    # FastAPI variant
    df_fastapi = generate_dockerfile(
        DockerfileSpec(
            python_version="3.13",
            project_name="api-server",
            package_name="api_server",
            dependencies=["fastapi", "uvicorn"],
            docker_port="8080",
            is_script_or_typer=False,
        )
    )
    assert "EXPOSE 8080" in df_fastapi
    assert (
        'CMD ["uvicorn", "api_server.main:app", "--host", "0.0.0.0", "--port", "8080"]'
        in df_fastapi
    )

    # Typer / script variant
    df_cli = generate_dockerfile(
        DockerfileSpec(
            python_version="3.13",
            project_name="my-cli",
            package_name="my_cli",
            dependencies=["typer"],
            is_script_or_typer=True,
        )
    )
    assert 'ENTRYPOINT ["my-cli"]' in df_cli


def test_generate_gitignore():
    # Fresh
    res = generate_gitignore(vcs_ignores={".venv", "__pycache__", ".DS_Store"})
    assert res is not None
    lines = [line.strip() for line in res.splitlines() if line.strip()]
    assert lines == [".DS_Store", ".venv", "__pycache__"]

    # Append to existing
    res_appended = generate_gitignore(
        vcs_ignores={"dist/", ".venv"},
        existing_content=".venv\n",
    )
    assert res_appended == ".venv\ndist/\n"

    # Nothing to append
    assert generate_gitignore(vcs_ignores={".venv"}, existing_content=".venv\n") is None


def test_generate_workflows_no_trailing_whitespace():
    """Verifies that generated workflow templates contain zero trailing whitespace and valid newlines."""
    ci_content = generate_ci_workflow(
        CIWorkflowSpec(
            supported_os=["Linux", "MacOS"],
            min_python="3.12",
            ci_flags={"pytest", "codecov"},
            ci_steps=["      - name: Lint\n        run: uv run ruff check"],
        )
    )
    for idx, line in enumerate(ci_content.splitlines(), 1):
        assert not line.endswith(" "), (
            f"Trailing space in CI workflow line {idx}: {line!r}"
        )
        assert not line.endswith("\t"), (
            f"Trailing tab in CI workflow line {idx}: {line!r}"
        )
    assert ci_content.endswith("\n")

    release_content = generate_release_workflow()
    for idx, line in enumerate(release_content.splitlines(), 1):
        assert not line.endswith(" "), (
            f"Trailing space in Release workflow line {idx}: {line!r}"
        )
        assert not line.endswith("\t"), (
            f"Trailing tab in Release workflow line {idx}: {line!r}"
        )
    assert release_content.endswith("\n")


def test_yaml_builder():
    """Tests the lightweight zero-dependency YAMLBuilder utility."""
    builder = YAMLBuilder()
    builder.append_raw("name: Example")
    builder.append_block(
        """
        jobs:
          build:
            runs-on: ubuntu-latest
        """
    )
    result = builder.build()
    expected = "name: Example\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
    assert result == expected

    # Test with custom indent and empty block handling
    nested_builder = YAMLBuilder()
    nested_builder.append_block("step: 1\nstep: 2", indent=2)
    nested_builder.append_block("")  # should be ignored
    assert nested_builder.build() == "  step: 1\n  step: 2\n"


def _agents_spec(**overrides):
    base = AgentsSpec(
        python_version="3.13",
        hook_runner=HookRunner.NONE,
        wants_just=True,
        format_commands=["uv run ruff format ."],
        lint_commands=["uv run ruff check ."],
        typecheck_commands=["uv run mypy ."],
        ci_flags={CIFlag.PYTEST},
    )
    return replace(base, **overrides)


def test_generate_agents_md_opens_with_a_heading_and_states_the_environment():
    content = generate_agents_md(_agents_spec(python_version="3.12"))

    assert content.startswith("# Agent Guide\n")
    assert content.endswith("\n")
    assert "Python 3.12, managed by uv" in content
    assert "`uv add <package>`" in content
    assert "`protostar sync`" in content


def test_generate_agents_md_lists_just_recipes_matching_the_justfile():
    content = generate_agents_md(_agents_spec())

    for recipe in ("format", "lint", "typecheck", "test"):
        assert f"`just {recipe}`" in content
    assert "`just ci`: run lint, typecheck, test;" in content
    assert "uv run ruff check ." not in content
    assert "```" not in content


def test_generate_agents_md_omits_recipes_the_justfile_lacks():
    content = generate_agents_md(
        _agents_spec(
            format_commands=[], lint_commands=[], typecheck_commands=[], ci_flags=set()
        )
    )

    assert "## Commands" not in content
    assert "`just" not in content


def test_generate_agents_md_ci_follows_available_recipes():
    content = generate_agents_md(_agents_spec(typecheck_commands=[], ci_flags=set()))

    assert "`just ci`: run lint;" in content
    assert "`just typecheck`" not in content
    assert "`just test`" not in content


def test_generate_agents_md_without_just_renders_raw_commands():
    multi_line = "if command -v tool; then \\\n        tool; \\\n    fi"
    content = generate_agents_md(
        _agents_spec(
            wants_just=False, lint_commands=["uv run ruff check .", multi_line]
        )
    )

    assert "`just" not in content
    assert "### Format\n\n```bash\nuv run ruff format .\n```" in content
    assert (
        "### Lint\n\n```bash\nuv run ruff check .\n" + multi_line + "\n```" in content
    )
    assert "### Type Check\n\n```bash\nuv run mypy .\n```" in content
    assert "### Test\n\n```bash\nuv run pytest\n```" in content


def test_generate_agents_md_without_just_or_commands_has_no_commands_section():
    content = generate_agents_md(
        _agents_spec(
            wants_just=False,
            format_commands=[],
            lint_commands=[],
            typecheck_commands=[],
            ci_flags=set(),
        )
    )

    assert "## Commands" not in content


@pytest.mark.parametrize("runner", [HookRunner.PRE_COMMIT, HookRunner.PREK])
def test_generate_agents_md_names_the_hook_runner(runner):
    content = generate_agents_md(_agents_spec(hook_runner=runner))

    assert "## Git Hooks" in content
    assert f"{runner.value} runs the hooks in `.pre-commit-config.yaml`" in content


def test_generate_agents_md_omits_hooks_without_a_runner():
    assert "## Git Hooks" not in generate_agents_md(_agents_spec())


def test_generate_agents_md_never_contains_region_boundaries():
    # The section is framed by region markers; boundary text inside it is rejected.
    content = generate_agents_md(_agents_spec(hook_runner=HookRunner.PREK))

    assert "region:" not in content
