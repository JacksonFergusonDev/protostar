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

TARGETS = [
    "pyproject.toml",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".dockerignore",
    ".markdownlint.yaml",
    ".gitattributes",
]

# Resolve to an absolute path immediately so os.chdir() doesn't break it
INCLUDES_DIR = Path("docs/includes").resolve()


def _write_markdown_snippet(
    filename: str, content: str, language: str | None = None
) -> None:
    """Writes content to a markdown snippet file within the includes directory.

    Args:
        filename: The target filename (e.g., 'default_config.md').
        content: The raw string payload to write to disk.
        language: An optional language identifier for a fenced code block.
            If provided, the content is wrapped in a markdown code block.
            If omitted, the content is written as standard markdown.
    """
    output_path = INCLUDES_DIR / filename

    # Ensure exactly one trailing newline before closing blocks to prevent formatting errors,
    # while preserving intentional multiple trailing newlines from target files.
    if not content.endswith("\n"):
        content += "\n"

    formatted_content = f"```{language}\n{content}```\n" if language else content

    output_path.write_text(formatted_content)
    print(f"Generated: {output_path.name}")


def _freeze_pyproject_deps(old_content: str, new_content: str) -> str:
    """Preserves existing dependency versions from an older pyproject.toml.

    Extracts the semantic version pins from the old content and injects them
    into the newly generated content to prevent arbitrary diff churn during
    documentation regeneration.

    Args:
        old_content: The string content of the existing documentation fixture.
        new_content: The newly generated pyproject.toml string content.

    Returns:
        The merged string content with frozen dependency versions.
    """
    # Build a lookup dictionary mapping package names to their frozen versions
    frozen_deps: dict[str, str] = dict(
        re.findall(r'"([a-zA-Z0-9_-]+)>=([^"]+)"', old_content)
    )

    def repl_deps(match: re.Match[str]) -> str:
        package_name = match.group(1)
        new_version = match.group(2)
        # Fall back to the new version if the package wasn't in the old content
        frozen_version = frozen_deps.get(package_name, new_version)
        return f'"{package_name}>={frozen_version}"'

    return re.sub(r'"([a-zA-Z0-9_-]+)>=([^"]+)"', repl_deps, new_content)


def _freeze_pre_commit_hooks(old_content: str, new_content: str) -> str:
    """Preserves existing git hook revisions from an older .pre-commit-config.yaml.

    Extracts the hook repository revisions from the old content and injects them
    into the newly generated content to prevent arbitrary diff churn.

    Args:
        old_content: The string content of the existing documentation fixture.
        new_content: The newly generated .pre-commit-config.yaml string content.

    Returns:
        The merged string content with frozen hook revisions.
    """
    # Build a lookup dictionary mapping repository URLs to their frozen git tags
    frozen_hooks: dict[str, str] = dict(
        re.findall(r"repo:\s*([^\n]+)\n\s*rev:\s*([^\n]+)", old_content)
    )

    def repl_hooks(match: re.Match[str]) -> str:
        repo_url = match.group(1)
        indentation = match.group(2)
        new_rev = match.group(3)
        # Fall back to the newly generated tag if the repo is new
        frozen_rev = frozen_hooks.get(repo_url, new_rev)
        return f"repo: {repo_url}\n{indentation}rev: {frozen_rev}"

    return re.sub(r"repo:\s*([^\n]+)\n(\s*)rev:\s*([^\n]+)", repl_hooks, new_content)


def _resolve_markdown_language(filename: str) -> str:
    """Resolves the appropriate markdown language tag for a given filename.

    Args:
        filename: The string filename to evaluate (e.g., 'main.cpp', 'pyproject.toml').

    Returns:
        The markdown syntax highlighting identifier.
    """
    # Path().suffix correctly identifies that '.gitignore' has NO suffix,
    # but '.pyrightconfig.json' has the suffix '.json'.
    ext = Path(filename).suffix.lstrip(".").lower()

    language_map = {
        "py": "python",
        "hpp": "cpp",
        "txt": "text",  # Normalize .txt to standard ```text blocks
    }

    # Fallback to the extracted extension, or "text" if there is no extension
    return language_map.get(ext, ext or "text")


def _format_markdown_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> str:
    """Constructs a markdown-formatted table from headers and row data.

    Args:
        headers: A sequence of column header strings.
        rows: A sequence of rows, where each row is a sequence of string values.

    Returns:
        A formatted markdown table string.
    """
    header_row = f"| {' | '.join(headers)} |"
    separator_row = f"| {' | '.join([':---'] * len(headers))} |"

    table = [header_row, separator_row]
    for row in rows:
        table.append(f"| {' | '.join(row)} |")

    return "\n".join(table)


class ManifestEncoder(json.JSONEncoder):
    """Custom JSON encoder for EnvironmentManifest dataclass serialization."""

    def default(self, obj: Any) -> Any:
        """Overrides the default JSON encoder for custom data types."""
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, Enum):
            return obj.value
        # Check that it's an instance, not the class type itself
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


def generate_default_config() -> None:
    """Extracts the default global TOML configuration."""
    _write_markdown_snippet(
        "default_config.md", DEFAULT_CONFIG_CONTENT, language="toml"
    )


def generate_generator_outputs() -> None:
    """Executes target generators in a sandbox and dumps their outputs."""
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

                output_path = INCLUDES_DIR / f"gen_{target_name}.md"
                output_path.write_text("\n\n".join(markdown_blocks) + "\n")
                print(f"Generated: {output_path.name}")
        finally:
            os.chdir(original_cwd)


def generate_capability_tables() -> None:
    """Parses modules and presets to generate markdown tables."""

    def _format_flags(flags: tuple[str, ...]) -> str:
        return ", ".join(f"`{f}`" for f in flags) if flags else "*None*"

    # 1. Languages Table
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
    _write_markdown_snippet(
        "table_languages.md", _format_markdown_table(lang_headers, lang_rows)
    )

    # 2. Tooling Table
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
    _write_markdown_snippet(
        "table_tooling.md", _format_markdown_table(tool_headers, tool_rows)
    )

    # 3. Presets Table
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
    _write_markdown_snippet(
        "table_presets.md", _format_markdown_table(preset_headers, preset_rows)
    )


def generate_manifest_state() -> None:
    """Computes and serializes a standard EnvironmentManifest state matrix."""
    manifest = EnvironmentManifest()

    # Simulate: `protostar init --python --astro --ruff`
    bootstrap_mods: list[BootstrapModule] = [PythonModule(), RuffModule()]
    preset_mods: list[PresetModule] = [AstroPreset()]

    for b_mod in bootstrap_mods:
        b_mod.build(manifest)

    for p_mod in preset_mods:
        p_mod.build(manifest)

    # --- STABILIZE ARTIFACTS ---
    # Override machine-specific paths and user-specific global configs
    # to ensure deterministic JSON output in both local and CI environments.
    manifest.ide_settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }
    # ---------------------------

    state_json = json.dumps(manifest, cls=ManifestEncoder, indent=4)
    _write_markdown_snippet("manifest_state.md", state_json, language="json")


def generate_tree(dir_path: Path) -> str:
    """Generates a text representation of the directory tree with a cleaned root and no footer."""
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
    """Executes a sequence of Protostar CLI commands in a given directory.

    Args:
        commands: A list of flag arrays to append to `protostar init`.
        cwd: The isolated working directory for the subprocess execution.
        env: The environment variables passed to the subprocess.
    """
    for flags in commands:
        subprocess.run(
            ["protostar", "init", *flags],
            cwd=cwd,
            check=True,
            env=env,
        )


def _extract_and_write_targets(source_dir: Path, fixture_name: str) -> None:
    """Extracts the directory tree and target files, formatting them as markdown.

    Args:
        source_dir: The populated workspace directory to inspect.
        fixture_name: The namespace identifier for the output markdown files
            (e.g., 'cli', 'astro', 'ml_merged').
    """
    # 1. Extract and write the directory tree
    tree_output = generate_tree(source_dir)
    _write_markdown_snippet(f"{fixture_name}_tree.md", tree_output, language="text")

    # 2. Extract and write specific target files
    for target in TARGETS:
        target_file = source_dir / target
        if not target_file.exists():
            continue

        lang = _resolve_markdown_language(target)
        content = target_file.read_text()
        snippet_filename = f"{fixture_name}_{target.replace('.', '')}.md"
        snippet_path = INCLUDES_DIR / snippet_filename

        # --- THE SELF-FREEZING LOGIC ---
        if snippet_path.exists():
            old_content = snippet_path.read_text()

            if target == "pyproject.toml":
                content = _freeze_pyproject_deps(old_content, content)
            elif target == ".pre-commit-config.yaml":
                content = _freeze_pre_commit_hooks(old_content, content)
        # -------------------------------

        _write_markdown_snippet(snippet_filename, content, language=lang)


def build_fixtures() -> None:
    """Iterates through predefined fixture scenarios and extracts their artifacts."""
    # Strip the parent VIRTUAL_ENV so it doesn't leak into the isolated temp dir
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    for name, commands in FIXTURES.items():
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a static working directory to prevent random project names
            static_cwd = Path(tmpdir) / "demo_project"
            static_cwd.mkdir()

            _execute_fixture_scenario(commands, static_cwd, clean_env)
            _extract_and_write_targets(static_cwd, name)


def main() -> None:
    """Main execution pipeline."""
    INCLUDES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating documentation fixtures...")
    generate_default_config()
    generate_generator_outputs()
    generate_capability_tables()
    generate_manifest_state()
    build_fixtures()
    print("\nDocumentation fixtures updated successfully!")


if __name__ == "__main__":
    main()
