from protostar.workflows import (
    CIWorkflowSpec,
    DockerfileSpec,
    JustfileSpec,
    generate_ci_workflow,
    generate_dockerfile,
    generate_dockerignore,
    generate_gitignore,
    generate_justfile,
    generate_pre_commit_config,
    generate_release_workflow,
)


def test_generate_pre_commit_config_basic():
    content = generate_pre_commit_config(local_hooks=[], remote_hooks=[])
    assert "repos:" in content
    assert "trailing-whitespace" in content
    assert "end-of-file-fixer" in content
    assert "check-yaml" in content
    assert "check-added-large-files" in content
    assert "repo: local" not in content


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
    )
    assert "repo: local" in content
    assert "uv run ruff check --fix" in content
    assert "https://github.com/astral-sh/ruff-pre-commit" in content


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
        dependencies=["fastapi", "pydantic"],
    )
    assert "          - fastapi\n          - pydantic" in content
    assert "<% MYPY_DEPENDENCIES %>" not in content

    # Without dependencies
    content_empty = generate_pre_commit_config(
        local_hooks=local_hooks,
        remote_hooks=[],
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
    assert "Install dependencies" in content


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


def test_generate_workflows_with_ciflag_enum():
    from protostar.enums import CIFlag, TargetOS

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
        'CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8080"]'
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
