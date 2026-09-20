import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from protostar.fs import atomic_write_bytes, atomic_write_text
from scripts._common import (
    CONSTRAINTS_FILE as CONSTRAINTS_FILE,
)
from scripts._common import (
    DOCS_GENERATED_DIR as DOCS_GENERATED_DIR,
)
from scripts._common import (
    DOCS_TERMINALS_DIR as DOCS_TERMINALS_DIR,
)
from scripts._common import (
    REPO_ROOT as REPO_ROOT,
)
from scripts._common import (
    SNAPSHOTS_DIR as SNAPSHOTS_DIR,
)
from scripts.generate_docs_assets import (
    generate_diff_fixtures,
    generate_docs_assets,
)


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
    "lib": RegressionScenario(
        name="lib",
        commands=(("--template", "lib"),),
        description="Reusable Python library with PEP 561 typing and src-layout.",
    ),
}

FIXTURES: dict[str, list[list[str]]] = {
    name: [list(c) for c in s.commands] for name, s in SCENARIOS.items()
}


def _write_snapshot_file(filepath: Path, content: bytes) -> None:
    """Writes raw bytes to a snapshot file ensuring directory existence."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(filepath, content)


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
        _write_snapshot_file(target_path, file_path.read_bytes())

    fixture_root = SNAPSHOTS_DIR / fixture_name
    if fixture_root.exists():
        for existing_file in list(fixture_root.rglob("*")):
            if (
                existing_file.is_file()
                and existing_file.resolve() not in written_targets
            ):
                existing_file.unlink()

        for directory in sorted(
            [d for d in fixture_root.rglob("*") if d.is_dir()],
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()


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
        isolated_env["UV_CONSTRAINT"] = str(CONSTRAINTS_FILE.resolve())
        isolated_env["PROTOSTAR_OFFLINE_HOOK_REGISTRY"] = "1"

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


def check_snapshot_drift(targets: Sequence[Path]) -> bool:
    """Verifies that the target snapshot/doc paths match git HEAD without uncommitted drift.

    Inspects the disk inventory directly against Git's tracked index to prevent local or
    nested .gitignore rules from hiding untracked artifacts, captures staged and unstaged
    diffs against HEAD, and renders unified diffs for newly created files.

    Args:
        targets: Sequence of directory or file paths to verify.

    Returns:
        True if zero uncommitted changes exist; False otherwise.
    """
    base_dir = Path.cwd()
    if any(t.is_relative_to(REPO_ROOT) for t in targets if t.exists()) and not any(
        t.is_relative_to(base_dir) for t in targets if t.exists()
    ):
        base_dir = REPO_ROOT

    rel_targets = [
        t.relative_to(base_dir).as_posix()
        if t.is_relative_to(base_dir)
        else t.as_posix()
        for t in targets
    ]
    if not rel_targets:
        return True

    # 1. Collect disk file inventory directly (independent of Git's ignore rules)
    disk_files: set[Path] = set()
    for target in targets:
        if not target.exists():
            continue
        if target.is_file():
            disk_files.add(target.resolve())
        else:
            for file_path in target.rglob("*"):
                if not file_path.is_file():
                    continue
                # Exclude runtime caches that are not snapshot artifacts
                if any(
                    part
                    in (
                        "__pycache__",
                        ".DS_Store",
                        ".pytest_cache",
                        ".ruff_cache",
                        ".mypy_cache",
                    )
                    for part in file_path.parts
                ):
                    continue
                disk_files.add(file_path.resolve())

    # 2. Collect Git tracked files for the target paths
    ls_result = subprocess.run(
        ["git", "ls-files", "--", *rel_targets],
        cwd=base_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_files = {
        (base_dir / line).resolve()
        for line in ls_result.stdout.splitlines()
        if line.strip()
    }

    # Identify untracked and deleted files independently of .gitignore
    untracked_disk_files = disk_files - tracked_files
    deleted_tracked_files = tracked_files - disk_files

    # 3. Check for modified tracked files against HEAD (covers both staged and unstaged changes)
    diff_stat_result = subprocess.run(
        ["git", "diff", "HEAD", "--name-status", "--", *rel_targets],
        cwd=base_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    head_diff_lines = [
        line.strip() for line in diff_stat_result.stdout.splitlines() if line.strip()
    ]

    has_drift = bool(untracked_disk_files or deleted_tracked_files or head_diff_lines)
    if not has_drift:
        targets_str = ", ".join(rel_targets)
        print(f"✔ All snapshots and assets in [{targets_str}] match expected state.")
        return True

    # 4. Generate unified diff for tracked changes against HEAD
    diff_result = subprocess.run(
        ["git", "diff", "HEAD", "--color=never", "--", *rel_targets],
        cwd=base_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    diff_output = diff_result.stdout.strip()

    # 5. Generate unified diff for untracked files
    untracked_diff_blocks: list[str] = []
    for untracked_path in sorted(untracked_disk_files):
        rel_untracked = (
            untracked_path.relative_to(base_dir).as_posix()
            if untracked_path.is_relative_to(base_dir)
            else untracked_path.as_posix()
        )
        untracked_diff = subprocess.run(
            ["git", "diff", "--no-index", "--color=never", "/dev/null", rel_untracked],
            cwd=base_dir,
            capture_output=True,
            text=True,
        )
        if untracked_diff.stdout.strip():
            untracked_diff_blocks.append(untracked_diff.stdout.strip())

    targets_display = " ".join(rel_targets)
    print("\n" + "=" * 80, file=sys.stderr)
    print(
        f"❌ SNAPSHOT REGRESSION DETECTED (Drift found in {targets_display})",
        file=sys.stderr,
    )
    print("=" * 80, file=sys.stderr)
    print("\nModified or untracked snapshot files:", file=sys.stderr)

    reported_paths: set[str] = set()
    for line in head_diff_lines:
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            status_code, diff_path_str = parts
            print(f"  {status_code} {diff_path_str}", file=sys.stderr)
            reported_paths.add(diff_path_str)
        else:
            print(f"  {line}", file=sys.stderr)

    for untracked_path in sorted(untracked_disk_files):
        rel = (
            untracked_path.relative_to(base_dir).as_posix()
            if untracked_path.is_relative_to(base_dir)
            else untracked_path.as_posix()
        )
        if rel not in reported_paths:
            print(f"  ?? {rel}", file=sys.stderr)

    for deleted_path in sorted(deleted_tracked_files):
        rel = (
            deleted_path.relative_to(base_dir).as_posix()
            if deleted_path.is_relative_to(base_dir)
            else deleted_path.as_posix()
        )
        if rel not in reported_paths:
            print(f"  D  {rel}", file=sys.stderr)

    all_diffs: list[str] = []
    if diff_output:
        all_diffs.append(diff_output)
    if untracked_diff_blocks:
        all_diffs.extend(untracked_diff_blocks)

    if all_diffs:
        print("\n--- Unified Diff ---", file=sys.stderr)
        print("\n".join(all_diffs), file=sys.stderr)

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
            if args.scenario:
                targets_to_check = [
                    SNAPSHOTS_DIR / args.scenario,
                    DOCS_GENERATED_DIR / f"tree_{args.scenario}.txt",
                ]
            else:
                targets_to_check = [SNAPSHOTS_DIR, DOCS_GENERATED_DIR]
                if not args.skip_docs:
                    targets_to_check.append(DOCS_TERMINALS_DIR)

            if not check_snapshot_drift(targets_to_check):
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting gracefully.")
        sys.exit(130)


if __name__ == "__main__":
    main()
