import argparse
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import tomlkit

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from protostar.fs import atomic_write_text
from scripts.generate_docs_assets import (
    DOCS_GENERATED_DIR,
    DOCS_TERMINALS_DIR,
    generate_diff_fixtures,
    generate_docs_assets,
)

SNAPSHOTS_DIR = Path("tests/snapshots").resolve()


@dataclass(frozen=True)
class RegressionScenario:
    """Declarative specification for an end-to-end template regression scenario."""

    name: str
    commands: tuple[tuple[str, ...], ...]
    description: str
    seed_fn: Callable[[Path, dict[str, str]], None] | None = None


def _seed_ml_merged_foreign_content(cwd: Path, env: dict[str, str]) -> None:
    """Adds representative unowned content before the tracked ML rerun."""
    subprocess.run(
        [
            "uv",
            "add",
            "astropy",
            "astroquery",
            "nbdime",
            "photutils",
            "scipy",
            "specutils",
        ],
        cwd=cwd,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    for directory in ("data/catalogs", "data/fits"):
        (cwd / directory).mkdir(parents=True, exist_ok=True)
    with (cwd / ".gitignore").open("a", encoding="utf-8") as stream:
        stream.write("*.csv\n*.fit\n*.fits\n*.fts\n*.parquet\n")


SCENARIOS: dict[str, RegressionScenario] = {
    "cli": RegressionScenario(
        name="cli",
        commands=(("--template", "cli"),),
        description="Default CLI application template with Typer and Rich.",
    ),
    "astro": RegressionScenario(
        name="astro",
        commands=(("--template", "astro"),),
        description="Astronomy template with scientific python dependencies and ASDF/FITS gitattributes.",
    ),
    "ml": RegressionScenario(
        name="ml",
        commands=(("--template", "ml", "--docker"),),
        description="Machine learning template with Docker containerization.",
    ),
    "ml_merged": RegressionScenario(
        name="ml_merged",
        commands=(
            ("--template", "ml", "--docker"),
            ("--template", "ml", "--mypy", "--docker", "--force-merge"),
        ),
        description="Same-template reinitialization exercising foreign workspace preservation and tooling adoption.",
        seed_fn=_seed_ml_merged_foreign_content,
    ),
    "api": RegressionScenario(
        name="api",
        commands=(("--template", "api"),),
        description="FastAPI application template.",
    ),
    "dsp": RegressionScenario(
        name="dsp",
        commands=(("--template", "dsp"),),
        description="Digital Signal Processing template with audio data sample layouts.",
    ),
    "embedded": RegressionScenario(
        name="embedded",
        commands=(("--template", "embedded"),),
        description="Embedded systems template with hardware board layout.",
    ),
}

FIXTURES: dict[str, list[list[str]]] = {
    name: [list(c) for c in s.commands] for name, s in SCENARIOS.items()
}


def _write_snapshot_file(filepath: Path, content: str) -> None:
    """Writes content to a snapshot file ensuring trailing newline and directory existence."""
    content = content.rstrip() + "\n"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(filepath, content)


def _freeze_pyproject_deps(old_content: str, new_content: str) -> str:
    """Preserves dependency versions from an existing pyproject.toml."""
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
    """Preserves Git hook revisions from an existing .pre-commit-config.yaml."""
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


def _align_state_dependencies(state_content: str, pyproject_content: str) -> str:
    """Aligns state materializations with dependency versions frozen in a fixture."""
    project = tomllib.loads(pyproject_content)
    requirements: dict[tuple[str, str, str], str] = {}
    groups = {
        "main": project.get("project", {}).get("dependencies", []),
        **project.get("dependency-groups", {}),
    }
    for group, entries in groups.items():
        for entry in entries:
            if not isinstance(entry, str):
                continue
            requirement = Requirement(entry)
            marker = str(requirement.marker) if requirement.marker is not None else ""
            requirements[(group, canonicalize_name(requirement.name), marker)] = entry

    state = tomlkit.parse(state_content)
    for record in state.get("dependencies", []):
        identity = (record["group"], record["name"], record["marker"])
        if materialized := requirements.get(identity):
            record["materialized"] = materialized
    return tomlkit.dumps(state)


def generate_tree(dir_path: Path) -> str:
    """Executes the tree CLI utility to generate a clean directory structure text representation."""
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    result = subprocess.run(
        [
            "tree",
            "-a",
            "-I",
            ".git",
            "--gitignore",
            "--noreport",
            "--charset=utf-8",
            ".",
        ],
        cwd=dir_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _execute_fixture_scenario(
    commands: list[list[str]], cwd: Path, env: dict[str, str]
) -> None:
    """Executes a defined sequence of Protostar commands within an isolated environment."""
    for flags in commands:
        try:
            subprocess.run(
                ["protostar", "init", *flags],
                cwd=cwd,
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Scenario command failed: {' '.join(e.cmd)}", file=sys.stderr)
            if e.stdout:
                print(f"STDOUT:\n{e.stdout}", file=sys.stderr)
            if e.stderr:
                print(f"STDERR:\n{e.stderr}", file=sys.stderr)
            raise


def _extract_and_write_targets(source_dir: Path, fixture_name: str) -> None:
    """Extracts target files from a completed execution scenario and writes them to disk."""
    tree_output = generate_tree(source_dir)
    tree_file = DOCS_GENERATED_DIR / f"tree_{fixture_name}.txt"
    tree_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(tree_file, tree_output.rstrip() + "\n")

    generated_pyproject = source_dir / "pyproject.toml"
    fixture_pyproject = SNAPSHOTS_DIR / fixture_name / "pyproject.toml"
    frozen_pyproject: str | None = None
    if generated_pyproject.exists():
        frozen_pyproject = generated_pyproject.read_text(encoding="utf-8")
        if fixture_pyproject.exists():
            frozen_pyproject = _freeze_pyproject_deps(
                fixture_pyproject.read_text(encoding="utf-8"), frozen_pyproject
            )

    written_targets: set[Path] = set()
    for file_path in sorted(source_dir.rglob("*")):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(source_dir)
        if any(
            part
            in (
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                ".ruff_cache",
                ".mypy_cache",
                ".rumdl_cache",
                "uv.lock",
            )
            for part in rel_path.parts
        ):
            continue

        target_rel_path = rel_path
        if rel_path.name == ".pre-commit-config.yaml":
            target_rel_path = rel_path.with_name("pre-commit-config.fixture.yaml")

        target_path = SNAPSHOTS_DIR / fixture_name / target_rel_path
        written_targets.add(target_path.resolve())
        content = file_path.read_text(encoding="utf-8")
        if rel_path.name == "pyproject.toml" and frozen_pyproject is not None:
            content = frozen_pyproject
        elif rel_path.name == ".protostar.lock.toml" and frozen_pyproject is not None:
            content = _align_state_dependencies(content, frozen_pyproject)

        if target_path.exists():
            old_content = target_path.read_text(encoding="utf-8")
            if target_rel_path.name == "pre-commit-config.fixture.yaml":
                content = _freeze_pre_commit_hooks(old_content, content)

        _write_snapshot_file(target_path, content)

    fixture_root = SNAPSHOTS_DIR / fixture_name
    if fixture_root.exists():
        for existing_file in list(fixture_root.rglob("*")):
            if (
                existing_file.is_file()
                and existing_file.resolve() not in written_targets
            ):
                existing_file.unlink()


def _get_host_uv_cache_dir() -> Path:
    """Resolves the user's host uv cache directory for sharing with isolated environments."""
    if env_dir := os.environ.get("UV_CACHE_DIR"):
        return Path(env_dir).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "uv"
    if sys.platform == "win32":
        local_app_data = os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )
        return Path(local_app_data) / "uv" / "cache"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "uv"
    return Path.home() / ".cache" / "uv"


def _build_fixture_scenario(
    scenario: RegressionScenario,
    clean_env: dict[str, str],
    host_cache_dir: str,
) -> None:
    """Builds a single fixture scenario in an isolated temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        isolated_env = clean_env.copy()
        isolated_env["HOME"] = tmpdir
        isolated_env["USERPROFILE"] = tmpdir
        isolated_env["XDG_CONFIG_HOME"] = tmpdir
        isolated_env["UV_CACHE_DIR"] = host_cache_dir
        isolated_env["UV_NO_PROGRESS"] = "1"

        static_cwd = Path(tmpdir) / "demo_project"
        static_cwd.mkdir()

        if scenario.seed_fn is not None:
            _execute_fixture_scenario(
                [list(c) for c in scenario.commands[:1]], static_cwd, isolated_env
            )
            scenario.seed_fn(static_cwd, isolated_env)
            _execute_fixture_scenario(
                [list(c) for c in scenario.commands[1:]], static_cwd, isolated_env
            )
        else:
            _execute_fixture_scenario(
                [list(c) for c in scenario.commands], static_cwd, isolated_env
            )
        _extract_and_write_targets(static_cwd, scenario.name)
        print(f"  ✔ Scenario [{scenario.name}] snapshots generated")


def build_snapshots(scenario_name: str | None = None) -> None:
    """Iterates through predefined scenarios concurrently and extracts snapshot artifacts."""
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    cache_path = _get_host_uv_cache_dir()
    cache_path.mkdir(parents=True, exist_ok=True)
    host_cache_dir = str(cache_path)

    if scenario_name is not None:
        if scenario_name not in SCENARIOS:
            valid = ", ".join(sorted(SCENARIOS.keys()))
            raise ValueError(
                f"Unknown scenario '{scenario_name}'. Valid options: {valid}"
            )
        target_scenarios = [SCENARIOS[scenario_name]]
    else:
        target_scenarios = list(SCENARIOS.values())

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                _build_fixture_scenario, scenario, clean_env, host_cache_dir
            )
            for scenario in target_scenarios
        ]
        for future in futures:
            future.result()


def check_snapshot_drift(directories: Sequence[Path]) -> bool:
    """Verifies that the target snapshot/doc directories match git HEAD."""
    rel_targets = [
        str(d.relative_to(Path.cwd())) if d.is_relative_to(Path.cwd()) else str(d)
        for d in directories
        if d.exists()
    ]

    status_result = subprocess.run(
        ["git", "status", "--porcelain", *rel_targets],
        capture_output=True,
        text=True,
        check=True,
    )
    status_output = status_result.stdout.strip()
    if not status_output:
        targets_str = ", ".join(rel_targets)
        print(f"✔ All snapshots and assets in [{targets_str}] match expected state.")
        return True

    diff_result = subprocess.run(
        ["git", "diff", "--color=never", *rel_targets],
        capture_output=True,
        text=True,
        check=True,
    )
    diff_output = diff_result.stdout.strip()

    targets_display = " ".join(rel_targets)
    print("\n" + "=" * 80, file=sys.stderr)
    print(
        f"❌ SNAPSHOT REGRESSION DETECTED (Drift found in {targets_display})",
        file=sys.stderr,
    )
    print("=" * 80, file=sys.stderr)
    print("\nModified or untracked snapshot files:", file=sys.stderr)
    for line in status_output.splitlines():
        print(f"  {line}", file=sys.stderr)

    if diff_output:
        print("\n--- Unified Diff ---", file=sys.stderr)
        print(diff_output, file=sys.stderr)

    print("\n" + "=" * 80, file=sys.stderr)
    print("AGENT INSTRUCTIONS:", file=sys.stderr)
    print(
        "- If this diff is INTENDED (you updated templates, flags, or opinions):",
        file=sys.stderr,
    )
    print("    Stage the updated snapshots and commit:", file=sys.stderr)
    print(f"    git add {targets_display}", file=sys.stderr)
    print(
        "- If this diff is an UNINTENDED REGRESSION:",
        file=sys.stderr,
    )
    print("    Discard modifications and fix your code:", file=sys.stderr)
    print(f"    git restore {targets_display}", file=sys.stderr)
    print(f"    git clean -fd {targets_display}", file=sys.stderr)
    print("=" * 80 + "\n", file=sys.stderr)

    return False


def main() -> None:
    """Primary execution pipeline for snapshot regression tests and doc generation."""
    parser = argparse.ArgumentParser(
        description="Run snapshot regression tests and documentation asset generation."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Target a specific scenario name (e.g., 'cli', 'ml').",
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip automatic git drift verification after generation.",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip static documentation asset generation.",
    )
    args = parser.parse_args()

    import protostar.config

    protostar.config.CONFIG_FILE = (
        Path(tempfile.gettempdir()) / "non_existent_protostar_config.toml"
    )
    protostar.config.clear_user_config_cache()

    try:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        DOCS_GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        if not args.scenario and not args.skip_docs:
            generate_docs_assets()

        scenario_msg = f" [{args.scenario}]" if args.scenario else "s"
        print(f"Generating regression snapshot{scenario_msg}...")
        build_snapshots(scenario_name=args.scenario)
        print("✔ Regression snapshots generated.")

        if not args.scenario and not args.skip_docs:
            generate_diff_fixtures()

        print("\nAll snapshots and documentation assets updated successfully!")

        if not args.no_check:
            print("\nVerifying snapshot drift against git HEAD...")
            dirs_to_check = [SNAPSHOTS_DIR]
            if not args.scenario and not args.skip_docs:
                dirs_to_check.extend([DOCS_GENERATED_DIR, DOCS_TERMINALS_DIR])
            if not check_snapshot_drift(dirs_to_check):
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting gracefully.")
        sys.exit(130)


if __name__ == "__main__":
    main()
