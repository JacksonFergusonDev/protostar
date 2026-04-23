import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

from protostar.config import DEFAULT_CONFIG_CONTENT, ProtostarConfig
from protostar.generators import GENERATOR_REGISTRY
from protostar.manifest import EnvironmentManifest
from protostar.modules import LANG_MODULES, TOOLING_MODULES, PythonModule, RuffModule
from protostar.presets import PRESETS, AstroPreset

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
    if language:
        formatted_content = f"```{language}\n{content.strip()}\n```\n"
    else:
        formatted_content = f"{content.strip()}\n"

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


class ManifestEncoder(json.JSONEncoder):
    """Custom JSON encoder for EnvironmentManifest dataclass serialization."""

    def default(self, obj):
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
                    file_ext = path.suffix.lstrip(".") or "text"
                    if file_ext == "py":
                        file_ext = "python"
                    elif file_ext in ("hpp", "cpp"):
                        file_ext = "cpp"
                    elif file_ext == "ini":
                        file_ext = "ini"

                    file_content = path.read_text().strip()
                    markdown_blocks.append(
                        f"**`{path.name}`**\n\n```{file_ext}\n{file_content}\n```"
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
    lang_lines = [
        "| Language Footprint | CLI Flags | Description | Collision Markers |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for mod in LANG_MODULES:
        markers = ", ".join(f"`{m.name}`" for m in mod.collision_markers) or "*None*"
        lang_lines.append(
            f"| {mod.name} | {_format_flags(mod.cli_flags)} | {mod.cli_help} | {markers} |"
        )
    _write_markdown_snippet("table_languages.md", "\n".join(lang_lines))

    # 2. Tooling Table
    tool_lines = [
        "| Tooling Module | CLI Flags | Description | Collision Markers |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for mod in TOOLING_MODULES:
        markers = ", ".join(f"`{m.name}`" for m in mod.collision_markers) or "*None*"
        tool_lines.append(
            f"| {mod.name} | {_format_flags(mod.cli_flags)} | {mod.cli_help} | {markers} |"
        )
    _write_markdown_snippet("table_tooling.md", "\n".join(tool_lines))

    # 3. Presets Table
    preset_lines = [
        "| Preset | CLI Flags | Description | Default Dependencies |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for preset in PRESETS:
        deps = ", ".join(f"`{d}`" for d in preset.default_dependencies) or "*None*"
        preset_lines.append(
            f"| {preset.name} | {_format_flags(preset.cli_flags)} | {preset.cli_help} | {deps} |"
        )
    _write_markdown_snippet("table_presets.md", "\n".join(preset_lines))


def generate_manifest_state() -> None:
    """Computes and serializes a standard EnvironmentManifest state matrix."""
    manifest = EnvironmentManifest()

    # Simulate: `protostar init --python --astro --ruff`
    modules = [PythonModule(), AstroPreset(), RuffModule()]

    for mod in modules:
        mod.build(manifest)

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


def build_fixtures():
    # Strip the parent VIRTUAL_ENV so it doesn't leak into the isolated temp dir
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    for name, commands in FIXTURES.items():
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Create a static working directory to prevent random project names
            static_cwd = Path(tmpdir) / "demo_project"
            static_cwd.mkdir()

            # 2. Run Protostar commands sequentially in the isolated static directory
            for flags in commands:
                subprocess.run(
                    ["protostar", "init", *flags],
                    cwd=static_cwd,
                    check=True,
                    env=clean_env,
                )

            # 3. Extract and write the directory tree
            tree_output = generate_tree(static_cwd)
            tree_path = INCLUDES_DIR / f"{name}_tree.md"
            tree_path.write_text(f"```text\n{tree_output}\n```\n")
            print(f"Generated: {tree_path.name}")

            # 4. Extract and write specific target files
            for target in TARGETS:
                target_file = static_cwd / target
                if target_file.exists():
                    lang = (
                        "toml"
                        if target.endswith(".toml")
                        else "yaml"
                        if target.endswith(".yaml")
                        else "text"
                    )
                    content = target_file.read_text()
                    snippet_path = INCLUDES_DIR / f"{name}_{target.replace('.', '')}.md"

                    # --- THE SELF-FREEZING LOGIC ---
                    if snippet_path.exists():
                        old_content = snippet_path.read_text()

                        if target == "pyproject.toml":
                            content = _freeze_pyproject_deps(old_content, content)
                        elif target == ".pre-commit-config.yaml":
                            content = _freeze_pre_commit_hooks(old_content, content)
                    # -------------------------------

                    snippet_path.write_text(f"```{lang}\n{content}```\n")
                    print(f"Generated: {snippet_path.name}")


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
