from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from protostar.documents import codecov, pre_commit, readthedocs, renovate, zensical
from protostar.intent import DependencyGroup, StructuredFormat
from protostar.manifest import DiagnosticEvent, DiagnosticPhase, Severity
from protostar.metadata import MetadataKey
from protostar.registry import RemoteHook
from protostar.system_deps import GlobalExecutable
from protostar.workflows import CIFlag, HookRunner
from protostar.workspace import PythonVersion

from .base import (
    BootstrapModule,
    PathSignal,
    RequirementSignal,
    SectionSignal,
    TableSignal,
    ToolInfo,
)

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")

AGENTS_TARGET = "AGENTS.md"


class DirenvModule(BootstrapModule):
    """Configures a .envrc file and evaluates it via direnv."""

    cli_flags = ("--direnv",)
    info = ToolInfo(
        summary="Activate the project's environment whenever you enter its folder",
        adds=(
            "An .envrc file that creates the virtual environment if it is "
            "missing and puts its commands on your PATH, plus .gitignore "
            "entries for direnv's local files."
        ),
        workflow=(
            "Entering the project folder in a terminal activates the "
            "environment, and leaving deactivates it, so you never run `source "
            ".venv/bin/activate`. It needs the direnv program installed and "
            "hooked into your shell."
        ),
        docs_url="https://direnv.net/",
    )
    config_key = "direnv"
    signals = (PathSignal(".envrc"),)
    executables = (GlobalExecutable.DIRENV,)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "direnv"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends direnv context ignores, injects the .envrc, and queues evaluation."""
        logger.debug("Building direnv tooling layer.")
        manifest.filesystem.add_vcs_ignore(".envrc.local")
        manifest.filesystem.add_vcs_ignore(".direnv/")

        content = (
            "# Ensure the venv exists\n"
            'if [ ! -d ".venv" ]; then\n'
            "    uv sync\n"
            "fi\n\n"
            "# Activate properly — direnv captures env changes, not shell functions\n"
            'export VIRTUAL_ENV="$(pwd)/.venv"\n'
            "PATH_add .venv/bin\n\n"
            "# Local overrides (not committed to git)\n"
            "source_env_if_exists .envrc.local\n"
        )

        manifest.filesystem.add_file_injection(".envrc", content)
        if manifest.is_missing(GlobalExecutable.DIRENV):
            manifest.diagnostics.append(
                DiagnosticEvent(
                    DiagnosticPhase.DIRENV,
                    "Skipping `direnv allow`; direnv is not installed. "
                    "Run it in the project once direnv is installed.",
                    Severity.SKIP,
                )
            )
            return
        manifest.tasks.add_post_install_task(
            ["direnv", "allow"], description="Authorizing direnv workspace"
        )


class MarkdownLintModule(BootstrapModule):
    """Configures a relaxed, pragmatic .markdownlint-cli2.yaml ruleset."""

    cli_flags = ("--markdownlint",)
    info = ToolInfo(
        summary="Check Markdown files for formatting mistakes, with relaxed rules",
        adds=(
            "A .markdownlint-cli2.yaml configuration, a git hook, and a CI step "
            "that lint every Markdown file."
        ),
        workflow=(
            "Committing a Markdown file checks it and fixes what it can; a "
            "problem it can't fix stops the commit until you do."
        ),
        docs_url="https://github.com/DavidAnson/markdownlint-cli2",
    )
    config_key = "markdownlint"
    signals = tuple(
        PathSignal(name)
        for name in (
            ".markdownlint-cli2.yaml",
            ".markdownlint-cli2.jsonc",
            ".markdownlint-cli2.cjs",
            ".markdownlint-cli2.mjs",
            ".markdownlint.yaml",
            ".markdownlint.yml",
            ".markdownlint.json",
            ".markdownlint.jsonc",
        )
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "MarkdownLint"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Injects the .markdownlint-cli2.yaml boilerplate file and pre-commit hook."""
        logger.debug("Building MarkdownLint tooling layer.")

        manifest.tooling.add_ide_extension("DavidAnson.vscode-markdownlint")

        hook_payload = f"""  # Markdown linting
  - repo: {RemoteHook.MARKDOWNLINT.value}
    rev: {RemoteHook.MARKDOWNLINT.placeholder}
    hooks:
      - id: markdownlint-cli2
        args: ["--fix"]"""
        manifest.tooling.add_pre_commit_hook(hook_payload)

        manifest.tooling.add_ci_step(
            "      - name: Run MarkdownLint\n"
            "        uses: DavidAnson/markdownlint-cli2-action@v24"
        )

        lint_cmd = (
            "if command -v markdownlint-cli2 >/dev/null 2>&1; then \\\n"
            '        markdownlint-cli2 "**/*.md"; \\\n'
            "    elif command -v npx >/dev/null 2>&1; then \\\n"
            '        npx --yes markdownlint-cli2 "**/*.md"; \\\n'
            "    else \\\n"
            '        printf "⚠ markdownlint-cli2 not found. Skipping markdown linting.\\n"; \\\n'
            "    fi"
        )
        manifest.tooling.just_lint_commands.append(lint_cmd)

        content = """gitignore: true

config:

  # Inherit default rules
  default: true

  # --- Disabled Rules ---

  # MD013: Line length
  # Rationale: Hard-wrapping text disrupts IDE reading flow, breaks URLs, and creates arbitrary diff churn.
  MD013: false

  # MD033: Inline HTML
  # Rationale: Required for layout elements unsupported by strict Markdown (e.g., <details> blocks, complex tables).
  MD033: false

  # --- Refined Rules ---

  # MD024: Multiple headings with the same content
  # Rationale: Allows duplicate subheadings (e.g., "Parameters") under different primary function headings.
  MD024:
    siblings_only: true

  # --- AST/Parser Enforcement ---

  # MD031: Fenced code blocks should be surrounded by blank lines
  # Rationale: Prevents strict parsers from rendering backticks as raw text instead of <pre><code> blocks.
  MD031: true

  # MD032: Lists should be surrounded by blank lines
  # Rationale: Prevents contiguous text from merging into lists, ensuring correct AST generation.
  MD032: true

  # --- Structural Consistency ---

  # MD003: Heading style
  # Rationale: Enforces ATX style (# Heading) exclusively.
  MD003:
    style: "atx"

  # MD004: Unordered list style
  # Rationale: Enforces dash markers for consistency across the syntax tree.
  MD004:
    style: "dash"

  # MD009: Trailing spaces
  # Rationale: Allows exactly two spaces for hard line breaks; flags arbitrary whitespace.
  MD009:
    br_spaces: 2
    strict: false

  # MD029: Ordered list item prefix
  # Rationale: Enforces the "one" style (1., 1., 1.) to minimize Git diff noise when rearranging list items.
  MD029:
    style: "one"
"""
        manifest.filesystem.add_file_injection(".markdownlint-cli2.yaml", content)


class RumdlModule(BootstrapModule):
    """Configures the rumdl fast markdown linter and formatter."""

    cli_flags = ("--rumdl",)
    info = ToolInfo(
        summary="Check and format Markdown files quickly",
        adds=(
            "rumdl as a development dependency, its settings in pyproject.toml, "
            "and a git hook that checks and formats Markdown."
        ),
        workflow=(
            "Committing a Markdown file reformats it and reports problems such "
            "as broken heading levels; an unfixed problem stops the commit."
        ),
        docs_url="https://github.com/rvben/rumdl",
    )
    config_key = "rumdl"
    signals = (
        PathSignal(".rumdl.toml"),
        PathSignal("rumdl.toml"),
        TableSignal(("tool", "rumdl")),
        RequirementSignal("rumdl"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Rumdl"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues rumdl dev dependency, ignores, hooks, and pyproject.toml config."""
        logger.debug("Building Rumdl tooling layer.")
        manifest.dependencies.add_dev("rumdl")
        manifest.filesystem.add_environment_artifact(".rumdl_cache/")

        hook_payload = """      - id: rumdl-check
        name: rumdl check
        entry: uv run rumdl check --fix
        language: system
        types: [markdown]
        require_serial: true

      - id: rumdl-fmt
        name: rumdl fmt
        entry: uv run rumdl fmt
        language: system
        types: [markdown]
        require_serial: true"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        manifest.tooling.add_ci_step(
            "      - name: Lint Markdown with rumdl\n"
            "        run: uv run rumdl check --output-format github .\n"
            "\n"
            "      - name: Check Markdown formatting with rumdl\n"
            "        run: uv run rumdl fmt --check --output-format github ."
        )

        manifest.tooling.just_lint_commands.extend(
            ["uv run rumdl check .", "uv run rumdl fmt --check ."]
        )
        manifest.tooling.just_format_commands.extend(
            ["uv run rumdl check --fix .", "uv run rumdl fmt ."]
        )
        manifest.tooling.just_clean_paths.append(".rumdl_cache")
        manifest.tooling.add_ide_extension("rvben.rumdl")

        config = """# ---- rumdl ---- #

[tool.rumdl]
disable = [
    "MD013", # line length - creates unnecessary diff churn
    "MD033", # inline HTML - required for readme and parts of documentation
    "MD077", # continuation line indentation - 4-space visual indent is intentional
]

# --- Heading style ---
# Enforce ATX style (# Heading) exclusively
[tool.rumdl.MD003]
style = "atx"

# --- Unordered list style ---
# Use dash (-) for list markers for consistency and reduced diff noise
[tool.rumdl.MD004]
style = "dash"

# --- Trailing spaces ---
# Allow exactly 2 spaces for hard line breaks; flag other stray whitespace
[tool.rumdl.MD009]
br-spaces = 2
strict = false

# --- Duplicate headings ---
# Allow identical subheadings under different parent headings
[tool.rumdl.MD024]
siblings-only = true

# --- Ordered list numbering ---
# Use "one" style (1., 1., 1.) to minimize Git diff churn on reorders
[tool.rumdl.MD029]
style = "one"

# --- Per-directory overrides for docs/ ---
# Relax rules that conflict with MkDocs / Zensical extensions
[tool.rumdl.per-file-ignores]
"docs/**/*.md" = [
    "MD041", # first line need not be a top-level heading in doc pages
    "MD046", # code block style - MkDocs extensions mix fenced and indented blocks
]
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:RumdlModule"
        )


class RuffModule(BootstrapModule):
    """Configures the Ruff linter and formatter with a sensible baseline.

    The baseline suits casual projects; stricter rule sets belong in templates.
    """

    cli_flags = ("--ruff",)
    info = ToolInfo(
        summary="Find common bugs and style problems in Python code, and format it",
        adds="Ruff as a development dependency and its rules in pyproject.toml.",
        workflow=(
            "`ruff check` reports likely bugs and unused code, and `ruff "
            "format` rewrites files in one consistent style. With a hook "
            "manager, both run on every commit."
        ),
        docs_url="https://docs.astral.sh/ruff/",
    )
    config_key = "ruff"
    signals = (
        PathSignal("ruff.toml"),
        PathSignal(".ruff.toml"),
        TableSignal(("tool", "ruff")),
        RequirementSignal("ruff"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Ruff"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Ruff dev dependency, ignores, hooks, and pyproject.toml config."""
        logger.debug("Building Ruff tooling layer.")
        manifest.dependencies.add_dev("ruff")
        manifest.filesystem.add_environment_artifact(".ruff_cache/")
        manifest.tooling.add_ide_extension("charliermarsh.ruff")

        hook_payload = """      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
        require_serial: true

      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
        require_serial: true"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        manifest.tooling.add_ci_step(
            "      - name: Run Ruff Linter\n"
            "        run: uv run ruff check --output-format=github .\n"
            "\n"
            "      - name: Run Ruff Formatter\n"
            "        run: uv run ruff format --check --output-format=github ."
        )

        manifest.tooling.just_format_commands.extend(
            ["uv run ruff check --fix .", "uv run ruff format ."]
        )
        manifest.tooling.just_lint_commands.extend(
            ["uv run ruff check .", "uv run ruff format --check ."]
        )
        manifest.tooling.just_clean_paths.append(".ruff_cache")

        # Ruff natively inherits its target Python version from project.requires-python
        config = """[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:RuffModule"
        )


class MypyModule(BootstrapModule):
    """Configures the Mypy static type checker with a sensible baseline.

    Strict mode is intentionally left to templates that want it.
    """

    cli_flags = ("--mypy",)
    info = ToolInfo(
        summary="Check type hints to catch mistakes before the code runs",
        adds=("Mypy as a development dependency and its settings in pyproject.toml."),
        workflow=(
            "`mypy` reports calls that don't match their type hints, such as "
            "passing text where a number is expected. Code without hints is "
            "mostly left alone."
        ),
        docs_url="https://mypy.readthedocs.io/en/stable/",
    )
    config_key = "mypy"
    signals = (
        PathSignal("mypy.ini"),
        PathSignal(".mypy.ini"),
        TableSignal(("tool", "mypy")),
        SectionSignal("setup.cfg", "mypy"),
        RequirementSignal("mypy"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Mypy"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Mypy dev dependency, ignores, hooks, and pyproject.toml config."""
        logger.debug("Building Mypy tooling layer.")
        manifest.dependencies.add_dev("mypy")
        manifest.filesystem.add_environment_artifact(".mypy_cache/")
        manifest.tooling.add_ide_extension(
            ("ms-python.mypy-type-checker", "matangover.mypy")
        )

        # Checking only the staged files misses errors they cause elsewhere, so
        # the hook, CI, and `just typecheck` all check the whole project.
        hook_payload = """      - id: mypy
        name: mypy
        entry: uv run mypy .
        language: system
        types: [python]
        pass_filenames: false"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        manifest.tooling.add_ci_step(
            "      - name: Run Mypy\n        run: uv run mypy ."
        )

        manifest.tooling.just_typecheck_commands.append("uv run mypy .")
        manifest.tooling.just_clean_paths.append(".mypy_cache")

        config = """[tool.mypy]
mypy_path = "src"
python_version = "<% PYTHON_VERSION %>"
pretty = true
show_error_codes = true
show_error_context = true
warn_return_any = true
warn_unused_configs = true
check_untyped_defs = true
explicit_package_bases = true
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:MypyModule"
        )


class TyModule(BootstrapModule):
    """Configures the Astral Ty static type checker."""

    cli_flags = ("--ty",)
    info = ToolInfo(
        summary="Check type hints quickly, with Astral's type checker",
        adds="ty as a development dependency and its settings in pyproject.toml.",
        workflow=(
            "`ty check` reports calls that don't match their type hints. It is "
            "newer than Mypy and much faster, and still gaining features."
        ),
        docs_url="https://docs.astral.sh/ty/",
    )
    config_key = "ty"
    signals = (
        PathSignal("ty.toml"),
        TableSignal(("tool", "ty")),
        RequirementSignal("ty"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Ty"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Ty dev dependency, hooks, and pyproject.toml config."""
        logger.debug("Building Ty tooling layer.")
        manifest.dependencies.add_dev("ty")
        manifest.tooling.add_ide_extension("astral-sh.ty")

        hook_payload = """      - id: ty
        name: ty check
        entry: uv run ty check
        language: system
        types: [python]
        pass_filenames: false"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        manifest.tooling.just_typecheck_commands.append("uv run ty check")

        config = """[tool.ty.rules]
missing-type-argument = "error"
redundant-cast = "warn"
unused-ignore-comment = "warn"
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:TyModule"
        )


class PytestModule(BootstrapModule):
    """Configures the Pytest testing framework and coverage artifacts."""

    cli_flags = ("--pytest",)
    info = ToolInfo(
        summary="Run the project's tests",
        adds=(
            "pytest and pytest-mock as development dependencies, a tests/ "
            "directory, and test settings in pyproject.toml."
        ),
        workflow=(
            "`uv run pytest` runs every test in tests/. With a hook manager, "
            "the tests also run before each push, and a failing test stops the "
            "push."
        ),
        docs_url="https://docs.pytest.org/",
    )
    config_key = "pytest"
    signals = (
        PathSignal("pytest.ini"),
        TableSignal(("tool", "pytest")),
        SectionSignal("setup.cfg", "tool:pytest"),
        SectionSignal("tox.ini", "pytest"),
        RequirementSignal("pytest"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Pytest"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Pytest dev dependencies, ignores, and pyproject.toml configuration."""
        logger.debug("Building Pytest tooling layer.")
        manifest.dependencies.add_dev("pytest")
        manifest.dependencies.add_dev("pytest-mock")
        manifest.tooling.add_ci_flag(CIFlag.PYTEST)

        # The suite runs before a push rather than on every commit, and only when
        # a push changes code, tests, or the locked environment.
        manifest.tooling.add_pre_commit_hook_type("pre-push")
        hook_payload = """      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
        files: ^(src/|tests/|pyproject\\.toml|uv\\.lock)
        stages: [pre-push]"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        # Deterministically scaffold the testing directory
        manifest.filesystem.add_directory("tests")

        artifacts = [".pytest_cache/"]
        for artifact in artifacts:
            manifest.filesystem.add_environment_artifact(artifact)

        manifest.tooling.just_clean_paths.append(".pytest_cache")

        config = """[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:PytestModule"
        )


class PreCommitModule(BootstrapModule):
    """Configures pre-commit hooks and installs the git hook scripts."""

    cli_flags = ("--pre-commit",)
    info = ToolInfo(
        summary="Run the project's checks automatically each time you commit",
        adds=(
            "A .pre-commit-config.yaml listing the checks, pre-commit as a "
            "development dependency, and git hooks installed in the repository."
        ),
        workflow=(
            "Checks run when you commit, and a failing check stops the commit. "
            "Many checks fix the file themselves, so you add it again and "
            "commit."
        ),
        docs_url="https://pre-commit.com/",
    )
    config_key = "pre_commit"
    signals = (
        *(
            PathSignal(path)
            for path in pre_commit.LOCATIONS[HookRunner.PRE_COMMIT].paths
        ),
        RequirementSignal("pre-commit"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Pre-Commit"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags pre-commit activation and queues its dependency.

        The orchestrator installs the git hooks once every module has declared
        the hook types it needs.
        """
        logger.debug("Building Pre-Commit tooling layer.")

        # Trigger the orchestrator to assemble and write the YAML file
        manifest.tooling.set_hook_runner(HookRunner.PRE_COMMIT)
        manifest.dependencies.add_dev("pre-commit")


class PrekModule(BootstrapModule):
    """Configures prek hooks and installs the git hook scripts."""

    cli_flags = ("--prek",)
    info = ToolInfo(
        summary=("Run the project's checks automatically each time you commit, faster"),
        adds=(
            "A .pre-commit-config.yaml listing the checks, prek as a "
            "development dependency, and git hooks installed in the repository."
        ),
        workflow=(
            "Checks run when you commit, and a failing check stops the commit. "
            "It reads the same file as pre-commit and runs the same checks, "
            "faster."
        ),
        docs_url="https://github.com/j178/prek",
    )
    config_key = "prek"
    signals = (
        *(PathSignal(path) for path in pre_commit.LOCATIONS[HookRunner.PREK].paths),
        RequirementSignal("prek"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Prek"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags prek activation and queues its dependency.

        The orchestrator installs the git hooks once every module has declared
        the hook types it needs.
        """
        logger.debug("Building Prek tooling layer.")

        # Trigger the orchestrator to assemble and write the YAML file
        manifest.tooling.set_hook_runner(HookRunner.PREK)
        manifest.dependencies.add_dev("prek")


class CommitizenModule(BootstrapModule):
    """Configures commitizen for semantic version bumping and changelog generation."""

    cli_flags = ("--commitizen",)
    info = ToolInfo(
        summary=("Write commit messages in a standard form that sets the next version"),
        adds=(
            "Commitizen as a development dependency, its settings in "
            "pyproject.toml, a CHANGELOG.md, and a hook that checks commit "
            "messages."
        ),
        workflow=(
            "Commit messages must follow Conventional Commits, such as `feat: "
            "add login`, or the commit stops. `cz bump` then raises the version "
            "and updates the changelog from them."
        ),
        docs_url="https://commitizen-tools.github.io/commitizen/",
    )
    config_key = "commitizen"
    signals = (
        *(
            PathSignal(name)
            for name in (".cz.toml", "cz.toml", ".cz.json", "cz.json", ".cz.yaml")
        ),
        TableSignal(("tool", "commitizen")),
        RequirementSignal("commitizen"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Commitizen"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues commitizen dev dependency, gitignore entry, pre-commit hook, and pyproject config.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Commitizen tooling layer.")

        manifest.dependencies.add_dev("commitizen")
        manifest.tooling.adopt_conventional_commits()
        manifest.filesystem.add_environment_artifact(".cz-cache/")
        manifest.filesystem.add_file_injection(
            "CHANGELOG.md",
            "# Changelog\n\nAll notable changes to this project will be documented in this file.\n",
        )

        manifest.tooling.add_pre_commit_hook_type("commit-msg")

        # The cz check hook enforces Conventional Commit message format.
        # Uses the official commitizen pre-commit mirror, which vendors its own
        # Python environment — no venv wiring required beyond what pre-commit handles.
        hook_payload = f"""  # Commit message validation
  - repo: {RemoteHook.COMMITIZEN.value}
    rev: {RemoteHook.COMMITIZEN.placeholder}
    hooks:
      - id: commitizen
        stages: [commit-msg]"""
        manifest.tooling.add_pre_commit_hook(hook_payload)

        config = """[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "semver2"
tag_format = "v$version"
update_changelog_on_bump = true
changelog_incremental = true
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:CommitizenModule"
        )


class PyreflyModule(BootstrapModule):
    """Configures the Meta pyrefly static type checker."""

    cli_flags = ("--pyrefly",)
    info = ToolInfo(
        summary="Check type hints quickly, with Meta's type checker",
        adds=(
            "Pyrefly as a development dependency and its settings in pyproject.toml."
        ),
        workflow=(
            "`pyrefly check` reports calls that don't match their type hints. "
            "It is newer than Mypy and much faster."
        ),
        docs_url="https://pyrefly.org/",
    )
    config_key = "pyrefly"
    signals = (
        PathSignal("pyrefly.toml"),
        TableSignal(("tool", "pyrefly")),
        RequirementSignal("pyrefly"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Pyrefly"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Pyrefly dev dependency, ignores, hooks, and pyproject.toml config."""
        logger.debug("Building Pyrefly tooling layer.")
        manifest.dependencies.add_dev("pyrefly")
        manifest.filesystem.add_environment_artifact(".pyrefly/")
        manifest.tooling.add_ide_extension("meta.pyrefly")

        hook_payload = """      - id: pyrefly-check
        name: pyrefly check
        entry: uv run pyrefly check
        language: system
        types: [python]
        pass_filenames: false"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        manifest.tooling.just_typecheck_commands.append("uv run pyrefly check")
        manifest.tooling.just_clean_paths.append(".pyrefly/")

        config = """[tool.pyrefly]
# "strict" enables the full suite of type error diagnostics
type-checking-mode = "strict"
"""
        manifest.filesystem.add_structured(
            "pyproject.toml", config, producer="module:PyreflyModule"
        )


class RenovateModule(BootstrapModule):
    """Configures Renovate dependency update tooling."""

    cli_flags = ("--renovate",)
    info = ToolInfo(
        summary="Open pull requests that keep dependencies up to date",
        adds="A .github/renovate.json configuration.",
        workflow=(
            "Once the Renovate app is installed on the GitHub repository, it "
            "opens a pull request whenever a dependency, GitHub Action, or hook "
            "has a new version. Nothing happens until the app is installed."
        ),
        docs_url="https://docs.renovatebot.com/",
    )
    config_key = "renovate"
    signals = tuple(PathSignal(path) for path in renovate.LOCATIONS.paths)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Renovate"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Renovate configuration file.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Renovate tooling layer.")

        config = """{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:best-practices",
    ":semanticCommits"
  ],
  "schedule": [
    "before 4am on monday"
  ],
  "internalChecksFilter": "strict",
  "rebaseWhen": "conflicted",
  "vulnerabilityAlerts": {
    "schedule": [
      "at any time"
    ]
  },
  "packageRules": [
    {
      "description": "Require a package to be 2 weeks old before updating, but exclude vulnerability remediation from this wait.",
      "matchUpdateTypes": [
        "major",
        "minor",
        "patch",
        "pin",
        "digest"
      ],
      "minimumReleaseAge": "2 weeks"
    },
    {
      "description": "Group all python dev-dependencies into one PR and automerge them.",
      "matchFileNames": [
        "pyproject.toml"
      ],
      "matchDepTypes": [
        "dependency-groups"
      ],
      "groupName": "python-dev-tools",
      "automerge": true
    },
    {
      "description": "Group GitHub Actions updates into one PR and automerge them.",
      "matchManagers": [
        "github-actions"
      ],
      "groupName": "github-actions",
      "automerge": true
    }
  ]
}
"""
        manifest.filesystem.add_file_injection(renovate.TARGET, config)

        # Renovate reads every one of its configuration names as JSON with
        # comments, which only the JSON5 parser accepts.
        manifest.dependencies.add_dev("check-jsonschema")
        manifest.dependencies.add_dev("json5")
        manifest.tooling.add_pre_commit_local_hook(
            f"""      - id: check-renovate
        name: check renovate config
        entry: uv run check-jsonschema --builtin-schema vendor.renovate --force-filetype json5
        language: system
        files: {pre_commit.document_files(renovate.TARGET)}"""
        )


class CodecovModule(BootstrapModule):
    """Configures opinionated Codecov coverage and status thresholds."""

    cli_flags = ("--codecov",)
    info = ToolInfo(
        summary=(
            "Report how much of the code the tests exercise, on each pull request"
        ),
        adds=(
            "A .github/codecov.yml with coverage targets, and a CI step that "
            "uploads the test coverage report."
        ),
        workflow=(
            "Each pull request gets a coverage comment, and its status check "
            "fails when coverage drops below the target. It needs the Codecov "
            "app and a CODECOV_TOKEN secret on the GitHub repository."
        ),
        docs_url="https://docs.codecov.com/docs",
    )
    config_key = "codecov"
    signals = tuple(PathSignal(path) for path in codecov.LOCATIONS.paths)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Codecov"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Declares managed Codecov YAML configuration.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Codecov tooling layer.")
        manifest.tooling.add_ci_flag(CIFlag.CODECOV)

        config = """coverage:
  precision: 2
  round: down
  range: "80...100"

  status:
    project:
      default:
        target: 80%
        threshold: 2%
        if_not_found: error
        if_ci_failed: error
    patch:
      default:
        target: 80%
        threshold: 2%
        if_not_found: success
        if_ci_failed: error
        informational: false

comment:
  layout: "reach,diff,flags,files"
  behavior: default
  require_changes: true

ignore:
  - "tests/**"
  - "docs/**"
  - "scripts/**"
  - "**/__init__.py"
"""
        manifest.filesystem.add_structured(
            codecov.TARGET,
            config,
            producer="module:codecov",
            document_format=StructuredFormat.YAML,
        )


class ZensicalModule(BootstrapModule):
    """Configures a minimal Zensical documentation setup."""

    cli_flags = ("--zensical",)
    info = ToolInfo(
        summary="Build a documentation website from Markdown files",
        adds=(
            "Zensical as a development dependency, a zensical.toml site "
            "configuration, and a first docs/index.md page."
        ),
        workflow=(
            "Pages are Markdown files in docs/. `zensical serve` previews the "
            "site as you write, and `zensical build` produces the finished "
            "site."
        ),
        docs_url="https://zensical.org/docs/",
    )
    config_key = "zensical"
    # A MkDocs site is a competitor, not Zensical: only its own file counts.
    signals = (
        *(PathSignal(path) for path in zensical.LOCATIONS.editable),
        RequirementSignal("zensical"),
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Zensical"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Zensical dependencies, scaffolding, and ignore rules."""
        logger.debug("Building Zensical tooling layer.")

        manifest.dependencies.add_docs("mkdocstrings[python]")
        manifest.dependencies.add_docs("zensical")
        manifest.tooling.add_ci_flag(CIFlag.ZENSICAL)

        manifest.filesystem.add_environment_artifact("site/")
        manifest.filesystem.add_directory("docs")

        manifest.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)

        index_content = """# Welcome to <% PROJECT_NAME %>

Add your project overview and documentation here.
"""
        manifest.filesystem.add_file_injection("docs/index.md", index_content)

        zensical_content = """[project]
site_name = "<% PROJECT_NAME %>"
site_description = "Add your project description here."

nav = [
    { "Home" = "index.md" },
]

[project.theme]
features = [
    "content.code.copy",
    "content.tabs.link",
    "content.tooltips",
    "navigation.footer",
    "navigation.instant",
    "navigation.instant.prefetch",
    "navigation.top",
    "search.highlight",
]

[project.theme.font]
text = "Inter"
code = "JetBrains Mono"

[[project.theme.palette]]
media = "(prefers-color-scheme)"
toggle.icon = "material/brightness-auto"
toggle.name = "Switch to light mode"

[[project.theme.palette]]
media = "(prefers-color-scheme: light)"
scheme = "default"
primary = "white"
accent = "cyan"
toggle.icon = "material/weather-sunny"
toggle.name = "Switch to dark mode"

[[project.theme.palette]]
media = "(prefers-color-scheme: dark)"
scheme = "slate"
primary = "deep purple"
accent = "cyan"
toggle.icon = "material/weather-night"
toggle.name = "Switch to system preference"

[project.markdown_extensions]
abbr = {}
admonition = {}
attr_list = {}
def_list = {}
footnotes = {}
md_in_html = {}
toc.permalink = true
pymdownx.arithmatex.generic = true
pymdownx.betterem = {}
pymdownx.caret = {}
pymdownx.details = {}
pymdownx.emoji.emoji_generator = "zensical.extensions.emoji.to_svg"
pymdownx.emoji.emoji_index = "zensical.extensions.emoji.twemoji"
pymdownx.highlight.anchor_linenums = true
pymdownx.highlight.line_spans = "__span"
pymdownx.highlight.pygments_lang_class = true
pymdownx.inlinehilite = {}
pymdownx.keys = {}
pymdownx.magiclink = {}
pymdownx.mark = {}
pymdownx.smartsymbols = {}
pymdownx.superfences.custom_fences = [
    { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },
]
pymdownx.tabbed.alternate_style = true
pymdownx.tabbed.combine_header_slug = true
pymdownx.tasklist.custom_checkbox = true
pymdownx.tilde = {}

[project.plugins.mkdocstrings]
handlers.python.options.show_root_heading = true
handlers.python.options.show_source = true

[project.extra]
generator = false
"""
        manifest.filesystem.add_structured(
            zensical.TARGET, zensical_content, producer="module:ZensicalModule"
        )


class ReadTheDocsModule(BootstrapModule):
    """Configures Read the Docs build configuration for documentation hosting."""

    cli_flags = ("--readthedocs",)
    info = ToolInfo(
        summary="Publish the documentation website on Read the Docs",
        adds=("A .readthedocs.yaml that tells Read the Docs how to build the site."),
        workflow=(
            "After you import the repository on readthedocs.org, every push "
            "rebuilds and publishes the documentation. Nothing happens until "
            "then."
        ),
        docs_url="https://docs.readthedocs.com/platform/stable/",
    )
    config_key = "readthedocs"
    signals = tuple(PathSignal(path) for path in readthedocs.LOCATIONS.paths)
    required_metadata = (MetadataKey.MINIMUM_PYTHON,)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Read the Docs"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Declares the managed Read the Docs build configuration.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Read the Docs tooling layer.")

        raw_python = (
            manifest.metadata.get("minimum_python")
            or manifest.metadata.get("python_version")
            or "3.13"
        )
        try:
            min_python = str(PythonVersion.from_string(str(raw_python)))
        except ValueError:
            min_python = str(raw_python)

        config = f"""version: 2

build:
  os: ubuntu-24.04
  tools:
    python: "{min_python}"
  jobs:
    pre_create_environment:
      - pip install uv
    create_environment:
      - uv venv "${{READTHEDOCS_VIRTUALENV_PATH}}"
    install:
      - UV_PROJECT_ENVIRONMENT="${{READTHEDOCS_VIRTUALENV_PATH}}" uv sync --only-group docs
    build:
      html:
        - mkdir -p "$READTHEDOCS_OUTPUT/html"
        - UV_PROJECT_ENVIRONMENT="${{READTHEDOCS_VIRTUALENV_PATH}}" uv run zensical build
        - cp -r site/* "$READTHEDOCS_OUTPUT/html/"
"""
        manifest.filesystem.add_structured(
            readthedocs.TARGET,
            config,
            producer="module:ReadTheDocsModule",
            document_format=StructuredFormat.YAML,
        )

        manifest.dependencies.add_dev("check-jsonschema")
        manifest.tooling.add_pre_commit_local_hook(
            f"""      - id: check-readthedocs
        name: check read the docs config
        entry: uv run check-jsonschema --builtin-schema vendor.readthedocs
        language: system
        files: {pre_commit.document_files(readthedocs.TARGET)}"""
        )


class JustModule(BootstrapModule):
    """Configures the justfile for project commands."""

    cli_flags = ("--just",)
    info = ToolInfo(
        summary="Give the project's common commands short names, like `just test`",
        adds=(
            "A justfile with commands for testing, checking, formatting, and "
            "cleaning up."
        ),
        workflow=(
            "`just --list` shows every command, and `just <name>` runs one. It "
            "needs the just program installed; each command is also a plain `uv "
            "run` you can type yourself."
        ),
        docs_url="https://just.systems/man/en/",
    )
    config_key = "just"
    signals = (PathSignal("justfile"), PathSignal("Justfile"), PathSignal(".justfile"))
    executables = (GlobalExecutable.JUST,)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Just"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags justfile activation for execution."""
        logger.debug("Building Just tooling layer.")
        manifest.tooling.wants_just = True


class AgentsModule(BootstrapModule):
    """Configures a managed AGENTS.md guide for coding agents."""

    cli_flags = ("--agents",)
    info = ToolInfo(
        summary="Tell coding assistants how to work on the project",
        adds=(
            "An AGENTS.md listing the project's commands and conventions, in a "
            "region Protostar keeps up to date."
        ),
        workflow=(
            "Coding assistants such as Claude Code, Codex, and Cursor read it "
            "before changing the project. Text you write outside the managed "
            "region is yours and stays."
        ),
        docs_url="https://agents.md/",
    )
    config_key = "agents"
    signals = (PathSignal(AGENTS_TARGET),)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Agents"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags AGENTS.md activation for planning.

        The guide describes the commands other modules contribute, so its content
        is rendered from the aggregated manifest once every module has built.
        """
        logger.debug("Building Agents tooling layer.")
        manifest.tooling.wants_agents = True
