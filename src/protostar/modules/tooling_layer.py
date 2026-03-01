import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from protostar.config import ProtostarConfig

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class DirenvModule(BootstrapModule):
    """Configures a .envrc file and evaluates it via direnv."""

    cli_flags: ClassVar[tuple[str, ...]] = ("--direnv",)
    cli_help: ClassVar[str] = "Scaffold a .envrc and evaluate the virtual environment"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "direnv"

    def pre_flight(self) -> None:
        """Ensures direnv is installed and available before disk mutations occur."""
        if not shutil.which("direnv"):
            raise RuntimeError(
                "direnv is not installed. Install it with: brew install direnv\n\n"
                "Once installed, ensure the shell hook is active in your ~/.zshrc:\n"
                '    eval "$(direnv hook zsh)"\n\n'
                "Then re-run: protostar init"
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends direnv context ignores, injects the .envrc, and queues evaluation."""
        logger.debug("Building direnv tooling layer.")
        manifest.add_vcs_ignore(".envrc.local")
        manifest.add_vcs_ignore(".direnv/")

        if Path(".envrc").exists():
            logger.debug("Skipping .envrc generation; file already exists.")
            return

        config = ProtostarConfig.load()
        init_cmd = (
            "uv sync"
            if config.python_package_manager == "uv"
            else "python3 -m venv .venv"
        )

        content = (
            "# Ensure the venv exists\n"
            'if [ ! -d ".venv" ]; then\n'
            f"    {init_cmd}\n"
            "fi\n\n"
            "# Activate properly — direnv captures env changes, not shell functions\n"
            'export VIRTUAL_ENV="$(pwd)/.venv"\n'
            "PATH_add .venv/bin\n\n"
            "# Local overrides (not committed to git)\n"
            "source_env_if_exists .envrc.local\n"
        )

        manifest.add_file_injection(".envrc", content)
        manifest.add_system_task(["direnv", "allow"])


class MarkdownLintModule(BootstrapModule):
    """Configures a relaxed, pragmatic .markdownlint.yaml ruleset."""

    cli_flags: ClassVar[tuple[str, ...]] = ("-m", "--markdownlint")
    cli_help: ClassVar[str] = "Scaffold a relaxed .markdownlint.yaml configuration"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "MarkdownLint"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Injects the .markdownlint.yaml boilerplate file and pre-commit hook."""
        logger.debug("Building MarkdownLint tooling layer.")

        hook_payload = """  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: v0.47.0
    hooks:
      - id: markdownlint
        args: ["--fix"]"""
        manifest.add_pre_commit_hook(hook_payload)

        if Path(".markdownlint.yaml").exists():
            logger.debug("Skipping .markdownlint.yaml generation; file already exists.")
            return

        content = """# Inherit default rules
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
        manifest.add_file_injection(".markdownlint.yaml", content)


class RuffModule(BootstrapModule):
    """Configures the Ruff linter and formatter with a standard baseline."""

    cli_flags: ClassVar[tuple[str, ...]] = ("--ruff",)
    cli_help: ClassVar[str] = "Scaffold Ruff linter and formatter"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Ruff"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues Ruff dev dependency, ignores, hooks, and pyproject.toml config."""
        logger.debug("Building Ruff tooling layer.")
        manifest.add_dev_dependency("ruff")
        manifest.add_vcs_ignore(".ruff_cache/")
        manifest.add_workspace_hide(".ruff_cache/")

        hook_payload = """  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.4
    hooks:
      - id: ruff-format
      - id: ruff
        args: [ --fix ]"""
        manifest.add_pre_commit_hook(hook_payload)

        # Ruff natively inherits its target Python version from project.requires-python
        config = """[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "RUF", # ruff-specific rules
]
ignore = []
"""
        manifest.add_file_append("pyproject.toml", config)


class MypyModule(BootstrapModule):
    """Configures the Mypy static type checker with strict enforcement."""

    cli_flags: ClassVar[tuple[str, ...]] = ("--mypy",)
    cli_help: ClassVar[str] = "Scaffold Mypy static type checker"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Mypy"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues Mypy dev dependency, ignores, hooks, and pyproject.toml config."""
        logger.debug("Building Mypy tooling layer.")
        manifest.add_dev_dependency("mypy")
        manifest.add_vcs_ignore(".mypy_cache/")
        manifest.add_workspace_hide(".mypy_cache/")

        # The MYPY_DEPENDENCIES token is late-bound by the orchestrator
        # to ensure all dynamically added packages are typed.
        hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
{{MYPY_DEPENDENCIES}}"""
        manifest.add_pre_commit_hook(hook_payload)

        config = """[tool.mypy]
python_version = "{{PYTHON_VERSION}}"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
"""
        manifest.add_file_append("pyproject.toml", config)


class PytestModule(BootstrapModule):
    """Configures the Pytest testing framework and coverage artifacts."""

    cli_flags: ClassVar[tuple[str, ...]] = ("--pytest",)
    cli_help: ClassVar[str] = "Scaffold Pytest testing framework"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Pytest"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues Pytest dev dependencies, ignores, and pyproject.toml configuration."""
        logger.debug("Building Pytest tooling layer.")
        manifest.add_dev_dependency("pytest")
        manifest.add_dev_dependency("pytest-cov")
        manifest.add_dev_dependency("pytest-mock")

        artifacts = [".pytest_cache/", ".coverage", "htmlcov/", "coverage.xml"]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)

        config = """[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers"
testpaths = [
    "tests",
]
"""
        manifest.add_file_append("pyproject.toml", config)


class PreCommitModule(BootstrapModule):
    """Configures pre-commit hooks and installs the git hook scripts."""

    cli_flags: ClassVar[tuple[str, ...]] = ("--pre-commit",)
    cli_help: ClassVar[str] = "Scaffold pre-commit hooks and configuration"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Pre-Commit"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Flags pre-commit activation, queues dependencies, and sets up git hooks."""
        logger.debug("Building Pre-Commit tooling layer.")

        # Trigger the orchestrator to assemble and write the YAML file
        manifest.wants_pre_commit = True
        manifest.add_dev_dependency("pre-commit")

        # Git must be initialized before pre-commit can install its hooks
        manifest.add_system_task(["git", "init"])
        manifest.add_system_task(["pre-commit", "install"])
        manifest.add_system_task(["pre-commit", "autoupdate"])
