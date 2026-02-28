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
        """Injects the .markdownlint.yaml boilerplate file."""
        logger.debug("Building MarkdownLint tooling layer.")

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
