import argparse
import io
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.terminal_theme import DEFAULT_TERMINAL_THEME, TerminalTheme
from rich.text import Text

import protostar.cli
from protostar.config import DEFAULT_CONFIG_CONTENT, ProtostarConfig
from protostar.generators import GENERATOR_REGISTRY
from protostar.manifest import EnvironmentManifest
from protostar.modules import (
    LANG_MODULES,
    TOOLING_MODULES,
    BootstrapModule,
    PythonModule,
    RuffModule,
)
from protostar.presets import PRESETS, AstroPreset, PresetModule

# Define matrices for combinatorial CLI execution scenarios
FIXTURES = {
    "cli": [
        ["--python", "--cli", "--mypy", "--pytest", "--pre-commit", "--markdownlint"],
    ],
    "astro": [["--python", "--astro"]],
    "ml": [["--python", "--ml", "--docker"]],
    "ml_merged": [
        ["--python", "--ml", "--docker"],
        ["--python", "--astro", "--mypy", "--docker", "--force"],
    ],
}

# Define target files to extract from the generated environments
TARGETS = [
    "pyproject.toml",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".dockerignore",
    ".markdownlint.yaml",
    ".gitattributes",
]

# Resolve absolute path to prevent os.chdir() related pathing errors
INCLUDES_DIR = Path("docs/includes").resolve()


def _write_fixture(filename: str, content: str, language: str | None = None) -> None:
    """Writes formatted content to a fixture file in the documentation includes directory.

    Args:
        filename: Target filename for the output payload.
        content: Raw string data to write to disk.
        language: Optional identifier for a Markdown fenced code block. If provided,
            the content is wrapped in the specified syntax highlighting.
    """
    output_path = INCLUDES_DIR / filename

    if not content.endswith("\n"):
        content += "\n"

    formatted_content = f"```{language}\n{content}```\n" if language else content

    output_path.write_text(formatted_content)
    print(f"Generated: {output_path.name}")


def _freeze_pyproject_deps(old_content: str, new_content: str) -> str:
    """Preserves dependency versions from an existing pyproject.toml.

    Prevents arbitrary diff churn during documentation regeneration by extracting
    and injecting prior semantic version pins into the newly generated payload.

    Args:
        old_content: Existing documentation fixture string.
        new_content: Newly generated configuration string.

    Returns:
        The updated string containing the frozen dependency versions.
    """
    frozen_deps: dict[str, str] = dict(
        re.findall(r'"([a-zA-Z0-9_-]+)>=([^"]+)"', old_content)
    )

    def repl_deps(match: re.Match[str]) -> str:
        package_name = match.group(1)
        new_version = match.group(2)
        frozen_version = frozen_deps.get(package_name, new_version)
        return f'"{package_name}>={frozen_version}"'

    return re.sub(r'"([a-zA-Z0-9_-]+)>=([^"]+)"', repl_deps, new_content)


def _freeze_pre_commit_hooks(old_content: str, new_content: str) -> str:
    """Preserves Git hook revisions from an existing .pre-commit-config.yaml.

    Prevents unnecessary documentation churn by extracting prior repository
    revisions and injecting them into the new configuration string.

    Args:
        old_content: Existing documentation fixture string.
        new_content: Newly generated configuration string.

    Returns:
        The updated string containing the frozen Git hook revisions.
    """
    frozen_hooks: dict[str, str] = dict(
        re.findall(r"repo:\s*([^\n]+)\n\s*rev:\s*([^\n]+)", old_content)
    )

    def repl_hooks(match: re.Match[str]) -> str:
        repo_url = match.group(1)
        indentation = match.group(2)
        new_rev = match.group(3)
        frozen_rev = frozen_hooks.get(repo_url, new_rev)
        return f"repo: {repo_url}\n{indentation}rev: {frozen_rev}"

    return re.sub(r"repo:\s*([^\n]+)\n(\s*)rev:\s*([^\n]+)", repl_hooks, new_content)


def _resolve_markdown_language(filename: str) -> str:
    """Maps a file extension to its corresponding Markdown syntax identifier.

    Args:
        filename: The filename to evaluate.

    Returns:
        The syntax highlighting identifier for Markdown.
    """
    ext = Path(filename).suffix.lstrip(".").lower()

    language_map = {
        "py": "python",
        "hpp": "cpp",
        "txt": "text",
    }

    return language_map.get(ext, ext or "text")


def _format_markdown_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> str:
    """Constructs a Markdown-formatted table from headers and row values.

    Args:
        headers: Sequence of column header names.
        rows: Sequence containing the row data.

    Returns:
        A valid Markdown table string.
    """
    header_row = f"| {' | '.join(headers)} |"
    separator_row = f"| {' | '.join([':---'] * len(headers))} |"

    table = [header_row, separator_row]
    for row in rows:
        table.append(f"| {' | '.join(row)} |")

    return "\n".join(table)


class ManifestEncoder(json.JSONEncoder):
    """Custom JSON serialization encoder for the EnvironmentManifest datastructure."""

    def default(self, obj: Any) -> Any:
        """Overrides the default JSON encoder for custom data types."""
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


def generate_default_config() -> None:
    """Writes the default global TOML configuration to a documentation fixture."""
    _write_fixture("default_config.md", DEFAULT_CONFIG_CONTENT, language="toml")


def generate_generator_outputs() -> None:
    """Executes code generators within an isolated directory and extracts outputs."""
    config = ProtostarConfig()

    # Map generator targets to dummy identifiers for execution
    identifiers = {
        "cpp-class": "ExampleClass",
        "tex": "report.tex",
        "pio": "esp32dev",
        "cmake": None,
        "circuitpython": None,
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            for target_name, generator in GENERATOR_REGISTRY.items():
                identifier = identifiers.get(target_name)
                output_paths = generator.execute(identifier, config)

                markdown_blocks = []
                for path in output_paths:
                    lang = _resolve_markdown_language(path.name)
                    file_content = path.read_text().strip()
                    markdown_blocks.append(
                        f"**`{path.name}`**\n\n```{lang}\n{file_content}\n```"
                    )

                _write_fixture(f"gen_{target_name}.md", "\n\n".join(markdown_blocks))
        finally:
            os.chdir(original_cwd)


def generate_capability_tables() -> None:
    """Generates Markdown tables detailing modules, presets, and their CLI footprints."""

    def _format_flags(flags: tuple[str, ...]) -> str:
        return ", ".join(f"`{f}`" for f in flags) if flags else "*None*"

    # Language definitions matrix
    lang_headers = [
        "Language Footprint",
        "CLI Flags",
        "Description",
        "Collision Markers",
    ]
    lang_rows = [
        [
            mod.name,
            _format_flags(mod.cli_flags),
            mod.cli_help,
            ", ".join(f"`{m.name}`" for m in mod.collision_markers) or "*None*",
        ]
        for mod in LANG_MODULES
    ]
    _write_fixture(
        "table_languages.md", _format_markdown_table(lang_headers, lang_rows)
    )

    # Tooling integration matrix
    tool_headers = ["Tooling Module", "CLI Flags", "Description", "Collision Markers"]
    tool_rows = [
        [
            mod.name,
            _format_flags(mod.cli_flags),
            mod.cli_help,
            ", ".join(f"`{m.name}`" for m in mod.collision_markers) or "*None*",
        ]
        for mod in TOOLING_MODULES
    ]
    _write_fixture("table_tooling.md", _format_markdown_table(tool_headers, tool_rows))

    # Dependency preset matrix
    preset_headers = ["Preset", "CLI Flags", "Description", "Default Dependencies"]
    preset_rows = [
        [
            preset.name,
            _format_flags(preset.cli_flags),
            preset.cli_help,
            ", ".join(f"`{d}`" for d in preset.default_dependencies) or "*None*",
        ]
        for preset in PRESETS
    ]
    _write_fixture(
        "table_presets.md", _format_markdown_table(preset_headers, preset_rows)
    )


def generate_manifest_state() -> None:
    """Simulates an initialization sequence to compute a deterministic JSON manifest."""
    manifest = EnvironmentManifest()

    # Simulate: `protostar init --python --astro --ruff`
    bootstrap_mods: list[BootstrapModule] = [PythonModule(), RuffModule()]
    preset_mods: list[PresetModule] = [AstroPreset()]

    for b_mod in bootstrap_mods:
        b_mod.build(manifest)

    for p_mod in preset_mods:
        p_mod.build(manifest)

    # Override machine-specific IDE paths to guarantee stable JSON diffs in CI
    manifest.ide_settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }

    state_json = json.dumps(manifest, cls=ManifestEncoder, indent=4)
    _write_fixture("manifest_state.md", state_json, language="json")


def generate_tree(dir_path: Path) -> str:
    """Executes the tree CLI utility to generate a clean directory structure text representation."""
    result = subprocess.run(
        ["tree", "-a", "-I", ".git", "--gitignore", "--noreport", "."],
        cwd=dir_path,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def _execute_fixture_scenario(
    commands: list[list[str]], cwd: Path, env: dict[str, str]
) -> None:
    """Executes a defined sequence of Protostar commands within an isolated environment.

    Args:
        commands: Argument vectors to pass to the CLI.
        cwd: Target directory for execution.
        env: Isolated environment variables map.
    """
    for flags in commands:
        subprocess.run(
            ["protostar", "init", *flags],
            cwd=cwd,
            check=True,
            env=env,
        )


def _extract_and_write_targets(source_dir: Path, fixture_name: str) -> None:
    """Extracts target files from a completed execution scenario and writes them to disk.

    Args:
        source_dir: Populated workspace directory containing generated artifacts.
        fixture_name: Prefix assigned to the output documentation fixtures.
    """
    tree_output = generate_tree(source_dir)
    _write_fixture(f"{fixture_name}_tree.md", tree_output, language="text")

    for target in TARGETS:
        target_file = source_dir / target
        if not target_file.exists():
            continue

        lang = _resolve_markdown_language(target)
        content = target_file.read_text()
        snippet_filename = f"{fixture_name}_{target.replace('.', '')}.md"
        snippet_path = INCLUDES_DIR / snippet_filename

        # Freeze mutable dependencies and VCS revisions if updating an existing file
        if snippet_path.exists():
            old_content = snippet_path.read_text()

            if target == "pyproject.toml":
                content = _freeze_pyproject_deps(old_content, content)
            elif target == ".pre-commit-config.yaml":
                content = _freeze_pre_commit_hooks(old_content, content)

        _write_fixture(snippet_filename, content, language=lang)


def build_fixtures() -> None:
    """Iterates through predefined scenarios, executing commands and extracting artifacts."""
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    for name, commands in FIXTURES.items():
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a static working directory to prevent random project names
            static_cwd = Path(tmpdir) / "demo_project"
            static_cwd.mkdir()

            _execute_fixture_scenario(commands, static_cwd, clean_env)
            _extract_and_write_targets(static_cwd, name)


def generate_cli_help_svgs() -> None:
    """Captures isolated SVG snapshots of the Protostar CLI help menus via Rich."""
    original_global_console = protostar.cli.console
    original_formatter_console = getattr(
        protostar.cli.ProtoHelpFormatter, "console", None
    )

    def _render_svg(
        target_parser: argparse.ArgumentParser, prompt_cmd: str, filename: str
    ) -> None:
        """Records terminal output and exports the resulting render to an SVG file."""
        record_console = Console(
            record=True,
            width=100,
            force_terminal=True,
            color_system="truecolor",
            legacy_windows=False,
            file=io.StringIO(),
        )

        prompt = Text.assemble(
            ("❯ ", "bold magenta"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{prompt_cmd}\n", "white"),
        )
        record_console.print(prompt)

        # Dispatch based on the parser's structure to handle custom table
        # rendering versus standard rich-argparse string formatting.
        is_custom_table = (
            hasattr(target_parser, "print_help")
            and hasattr(target_parser.print_help, "__func__")
            and target_parser.print_help.__func__.__name__ == "print_table_help"
        )

        if is_custom_table:
            protostar.cli.console = record_console
            target_parser.print_help()
        else:
            protostar.cli.ProtoHelpFormatter.console = record_console  # type: ignore[method-assign, assignment]
            ansi_str = target_parser.format_help()
            record_console.print(Text.from_ansi(ansi_str, no_wrap=True))

        # Re-map primary colors to match project theme defaults
        ansi_colors = [
            (color.red, color.green, color.blue)
            for color in DEFAULT_TERMINAL_THEME.ansi_colors  # type: ignore[attr-defined]
        ]
        ansi_colors[4] = (97, 175, 239)
        ansi_colors[12] = (97, 175, 239)
        ansi_colors[6] = (34, 211, 238)
        ansi_colors[14] = (34, 211, 238)

        protostar_theme = TerminalTheme(
            background=(10, 15, 31),
            foreground=(220, 225, 235),
            normal=ansi_colors[:8],
            bright=ansi_colors[8:16],
        )

        svg_content = record_console.export_svg(
            title="zsh",
            theme=protostar_theme,
            unique_id=filename.replace(".svg", ""),
        )

        clean_svg = "\n".join(line.rstrip() for line in svg_content.splitlines()) + "\n"
        _write_fixture(filename, clean_svg)

    try:
        parser = protostar.cli.build_parser()

        # Generate base root help SVG
        _render_svg(parser, "help", "cli_help.svg")

        # Generate specific subparser help SVG if available
        subparsers = next(
            (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
            None,
        )
        if subparsers and "init" in subparsers.choices:
            init_parser = subparsers.choices["init"]
            _render_svg(init_parser, "help init", "cli_init_help.svg")

    finally:
        # Restore the native consoles
        protostar.cli.console = original_global_console
        if original_formatter_console is None:
            protostar.cli.ProtoHelpFormatter.console = None  # type: ignore[method-assign, assignment]
        else:
            protostar.cli.ProtoHelpFormatter.console = original_formatter_console  # type: ignore[method-assign, assignment]


def main() -> None:
    """Primary execution pipeline for documentation artifact generation."""
    INCLUDES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating documentation fixtures...")
    generate_cli_help_svgs()
    generate_default_config()
    generate_generator_outputs()
    generate_capability_tables()
    generate_manifest_state()
    build_fixtures()
    print("\nDocumentation fixtures updated successfully!")


if __name__ == "__main__":
    main()
