from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.errors import ConfigurationError, MissingDependencyError
from protostar.workflows import CIFlag

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class DirenvModule(BootstrapModule):
    """Configures a .envrc file and evaluates it via direnv."""

    cli_flags = ("--direnv",)
    cli_help = "Scaffold a .envrc and evaluate the virtual environment"
    config_key = "direnv"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "direnv"

    def pre_flight(self) -> None:
        """Ensures direnv is installed and available before disk mutations occur."""
        if not shutil.which("direnv"):
            hint = (
                "Install it with: brew install direnv\n\n"
                "Once installed, ensure the shell hook is active in your ~/.zshrc:\n"
                '    eval "$(direnv hook zsh)"\n\n'
                "Then re-run: protostar init"
            )
            raise MissingDependencyError(
                dependency="direnv", purpose="direnv integration", install_hint=hint
            )

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for direnv tooling."""
        return [Path(".envrc")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends direnv context ignores, injects the .envrc, and queues evaluation."""
        logger.debug("Building direnv tooling layer.")
        manifest.filesystem.add_vcs_ignore(".envrc.local")
        manifest.filesystem.add_vcs_ignore(".direnv/")

        if manifest.should_skip_file(Path(".envrc")):
            return

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
        manifest.tasks.add_post_install_task(
            ["direnv", "allow"], description="Authorizing direnv workspace"
        )


class MarkdownLintModule(BootstrapModule):
    """Configures a relaxed, pragmatic .markdownlint-cli2.yaml ruleset."""

    cli_flags = ("--markdownlint",)
    cli_help = "Scaffold a relaxed .markdownlint-cli2.yaml configuration"
    config_key = "markdownlint"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "MarkdownLint"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for markdownlint."""
        return [Path(".markdownlint-cli2.yaml")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Injects the .markdownlint-cli2.yaml boilerplate file and pre-commit hook."""
        logger.debug("Building MarkdownLint tooling layer.")

        manifest.tooling.add_ide_extension("DavidAnson.vscode-markdownlint")

        hook_payload = """  # Markdown linting
  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.23.0
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
            '        printf "{{ yellow }}⚠ markdownlint-cli2 not found. Skipping markdown linting.{{ nc }}\\n"; \\\n'
            "    fi"
        )
        manifest.tooling.just_lint_commands.append(lint_cmd)

        if manifest.should_skip_file(Path(".markdownlint-cli2.yaml")):
            return

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


class RuffModule(BootstrapModule):
    """Configures the Ruff linter and formatter with a standard baseline."""

    cli_flags = ("--ruff",)
    cli_help = "Scaffold Ruff linter and formatter"
    config_key = "ruff"

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
        manifest.filesystem.add_file_append("pyproject.toml", config)


class MypyModule(BootstrapModule):
    """Configures the Mypy static type checker with strict enforcement."""

    cli_flags = ("--mypy",)
    cli_help = "Scaffold Mypy static type checker"
    config_key = "mypy"

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

        hook_payload = """      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        require_serial: true"""
        manifest.tooling.add_pre_commit_local_hook(hook_payload)

        manifest.tooling.add_ci_step(
            "      - name: Run Mypy\n        run: uv run mypy src/"
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
        manifest.filesystem.add_file_append("pyproject.toml", config)


class TyModule(BootstrapModule):
    """Configures the Astral Ty static type checker."""

    cli_flags = ("--ty",)
    cli_help = "Scaffold Ty static type checker"
    config_key = "ty"

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
        manifest.filesystem.add_file_append("pyproject.toml", config)


class PytestModule(BootstrapModule):
    """Configures the Pytest testing framework and coverage artifacts."""

    cli_flags = ("--pytest",)
    cli_help = "Scaffold Pytest testing framework"
    config_key = "pytest"

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
        manifest.filesystem.add_file_append("pyproject.toml", config)


class PreCommitModule(BootstrapModule):
    """Configures pre-commit hooks and installs the git hook scripts."""

    cli_flags = ("--pre-commit",)
    cli_help = "Scaffold pre-commit hooks and configuration"
    config_key = "pre_commit"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Pre-Commit"

    def pre_flight(self) -> None:
        """Verifies that the 'git' executable is available in the system PATH."""
        if not shutil.which("git"):
            raise MissingDependencyError(
                dependency="git",
                purpose="pre-commit hooks",
                install_hint="Please install Git and try again.",
            )

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for pre-commit."""
        return [Path(".pre-commit-config.yaml")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags pre-commit activation, queues dependencies, and sets up git hooks.

        Evaluates the local workspace for an existing Git repository before
        queueing initialization commands to ensure idempotency.
        """
        logger.debug("Building Pre-Commit tooling layer.")

        # Trigger the orchestrator to assemble and write the YAML file
        manifest.tooling.wants_pre_commit = True
        manifest.dependencies.add_dev("pre-commit")

        # `autoupdate` pulls remote git repositories to update hook definitions,
        # requiring a wider time window than a local install.
        manifest.tasks.add_post_install_task(
            ["uv", "run", "pre-commit", "install"],
            description="Installing pre-commit git hooks",
        )
        manifest.tasks.add_post_install_task(
            ["uv", "run", "pre-commit", "autoupdate"],
            timeout=300,
            description="Updating pre-commit hooks to latest versions...",
        )


class PrekModule(BootstrapModule):
    """Configures prek hooks and installs the git hook scripts."""

    cli_flags = ("--prek",)
    cli_help = (
        "Scaffold prek hooks and configuration (faster Rust alternative to pre-commit)"
    )
    config_key = "prek"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Prek"

    def pre_flight(self) -> None:
        """Verifies that the 'git' executable is available in the system PATH."""
        if not shutil.which("git"):
            raise MissingDependencyError(
                dependency="git",
                purpose="prek hooks",
                install_hint="Please install Git and try again.",
            )

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for prek."""
        return [Path(".pre-commit-config.yaml")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags prek activation, queues dependencies, and sets up git hooks.

        Evaluates the local workspace for an existing Git repository before
        queueing initialization commands to ensure idempotency.
        """
        logger.debug("Building Prek tooling layer.")

        # Trigger the orchestrator to assemble and write the YAML file
        manifest.tooling.wants_prek = True
        manifest.dependencies.add_dev("prek")

        manifest.tasks.add_post_install_task(
            ["uv", "run", "prek", "install"],
            description="Installing prek git hooks",
        )
        manifest.tasks.add_post_install_task(
            ["uv", "run", "prek", "update"],
            timeout=300,
            description="Updating prek hooks to latest versions...",
        )


class CommitizenModule(BootstrapModule):
    """Configures commitizen for semantic version bumping and changelog generation."""

    cli_flags = ("--commitizen",)
    cli_help = "Scaffold commitizen version bumping and changelog tooling"
    config_key = "commitizen"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Commitizen"

    def pre_flight(self) -> None:
        """Verifies that the runtime environment satisfies all commitizen prerequisites."""
        return

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for commitizen."""
        return []

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues commitizen dev dependency, gitignore entry, pre-commit hook, and pyproject config.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Commitizen tooling layer.")

        manifest.dependencies.add_dev("commitizen")
        manifest.filesystem.add_environment_artifact(".cz-cache/")
        manifest.filesystem.add_file_injection(
            "CHANGELOG.md",
            "# Changelog\n\nAll notable changes to this project will be documented in this file.\n",
        )

        manifest.tooling.add_pre_commit_hook_type("commit-msg")

        # The cz check hook enforces Conventional Commit message format.
        # Uses the official commitizen pre-commit mirror, which vendors its own
        # Python environment — no venv wiring required beyond what pre-commit handles.
        hook_payload = """  # Commit message validation
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.8.3
    hooks:
      - id: commitizen
        stages: [commit-msg]"""
        manifest.tooling.add_pre_commit_hook(hook_payload)

        # version_provider = "pep621" reads/writes [project].version in pyproject.toml
        # directly — no duplication, no separate version file. This is the correct
        # choice since `uv init` scaffolds a standard PEP 621 pyproject.toml.
        config = """[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "semver2"
tag_format = "v$version"
update_changelog_on_bump = true
changelog_incremental = true
"""
        manifest.filesystem.add_file_append("pyproject.toml", config)


class PyreflyModule(BootstrapModule):
    """Configures the Meta pyrefly static type checker."""

    cli_flags = ("--pyrefly",)
    cli_help = "Scaffold pyrefly static type checker"
    config_key = "pyrefly"

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
        manifest.filesystem.add_file_append("pyproject.toml", config)


class RenovateModule(BootstrapModule):
    """Configures Renovate dependency update tooling."""

    cli_flags = ("--renovate",)
    cli_help = "Scaffold Renovate dependency update configuration"
    config_key = "renovate"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Renovate"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for Renovate."""
        return [Path(".github/renovate.json")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Renovate configuration file and pre-commit validator hook.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Renovate tooling layer.")

        hook_payload = """  # Renovate config validation
  - repo: https://github.com/renovatebot/pre-commit-hooks
    rev: 44.24.3
    hooks:
      - id: renovate-config-validator
        files: '.github/renovate.json'"""
        manifest.tooling.add_pre_commit_hook(hook_payload)

        if manifest.should_skip_file(Path(".github/renovate.json")):
            return

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
        manifest.filesystem.add_file_injection(".github/renovate.json", config)


class CodecovModule(BootstrapModule):
    """Configures opinionated Codecov coverage and status thresholds."""

    cli_flags = ("--codecov",)
    cli_help = "Scaffold Codecov configuration"
    config_key = "codecov"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Codecov"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for Codecov."""
        return [Path(".github/codecov.yml")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Codecov configuration file injection.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Codecov tooling layer.")
        manifest.tooling.add_ci_flag(CIFlag.CODECOV)

        if manifest.should_skip_file(Path(".github/codecov.yml")):
            return

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
        manifest.filesystem.add_file_injection(".github/codecov.yml", config)


class ZensicalModule(BootstrapModule):
    """Configures a minimal Zensical documentation setup."""

    cli_flags = ("--zensical",)
    cli_help = "Scaffold Zensical documentation"
    config_key = "zensical"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Zensical"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for Zensical."""
        return [Path("mkdocs.yml"), Path("docs/")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues Zensical dependencies, scaffolding, and ignore rules."""
        logger.debug("Building Zensical tooling layer.")

        manifest.dependencies.add_docs("mkdocstrings[python]")
        manifest.dependencies.add_docs("zensical")
        manifest.tooling.add_ci_flag(CIFlag.ZENSICAL)

        manifest.filesystem.add_environment_artifact("site/")
        manifest.filesystem.add_directory("docs")

        pyproject_wiring = """[dependency-groups]
dev = [
    { include-group = "docs" },
]
"""
        manifest.filesystem.add_file_append("pyproject.toml", pyproject_wiring)

        if manifest.should_skip_file(Path("docs/index.md")):
            pass
        else:
            index_content = """# Welcome to <% PROJECT_NAME %>

Add your project overview and documentation here.
"""
            manifest.filesystem.add_file_injection("docs/index.md", index_content)

        if manifest.should_skip_file(Path("mkdocs.yml")):
            pass
        else:
            mkdocs_content = """site_name: <% PROJECT_NAME %>
site_description: Add your project description here.

nav:
  - Home: index.md

theme:
  name: material
  features:
    - navigation.instant
    - navigation.top
    - navigation.footer
    - search.suggest
    - search.highlight
    - content.code.copy

markdown_extensions:
  - admonition
  - attr_list
  - def_list
  - pymdownx.details
  - pymdownx.superfences
  - toc:
      permalink: true

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_root_heading: true
            show_source: true

extra:
  generator: false
"""
            manifest.filesystem.add_file_injection("mkdocs.yml", mkdocs_content)


class ReadTheDocsModule(BootstrapModule):
    """Configures Read the Docs build configuration for documentation hosting."""

    cli_flags = ("--readthedocs",)
    cli_help = "Scaffold Read the Docs configuration"
    config_key = "readthedocs"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Read the Docs"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for Read the Docs."""
        return [Path(".readthedocs.yaml")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues .readthedocs.yaml file injection.

        Args:
            manifest: The centralized state object.

        Raises:
            ConfigurationError: If the Zensical module is not enabled.
        """
        logger.debug("Building Read the Docs tooling layer.")

        if not any(
            "zensical" in dep for dep in manifest.dependencies.docs_dependencies
        ):
            raise ConfigurationError(
                "Read the Docs scaffolding requires the Zensical module to be enabled."
            )

        if manifest.should_skip_file(Path(".readthedocs.yaml")):
            return

        config = """version: 2

build:
  os: ubuntu-24.04
  tools:
    python: "3.12"
  jobs:
    pre_create_environment:
      - pip install uv
    create_environment:
      - uv venv "${READTHEDOCS_VIRTUALENV_PATH}"
    install:
      - UV_PROJECT_ENVIRONMENT="${READTHEDOCS_VIRTUALENV_PATH}" uv sync --only-group docs
    build:
      html:
        - mkdir -p "$READTHEDOCS_OUTPUT/html"
        - UV_PROJECT_ENVIRONMENT="${READTHEDOCS_VIRTUALENV_PATH}" uv run zensical build
        - cp -r site/* "$READTHEDOCS_OUTPUT/html/"
"""
        manifest.filesystem.add_file_injection(".readthedocs.yaml", config)


class JustModule(BootstrapModule):
    """Configures the justfile for project commands."""

    cli_flags = ("--just",)
    cli_help = "Scaffold a justfile for command execution"
    config_key = "just"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Just"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for just."""
        return [Path("justfile")]

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags justfile activation for execution."""
        logger.debug("Building Just tooling layer.")
        manifest.tooling.wants_just = True
