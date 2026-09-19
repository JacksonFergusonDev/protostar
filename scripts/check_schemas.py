"""Validates repository and snapshot configurations against official schemas.

Checks:
1. Pre-commit & prek configurations against prek's parser (root and snapshots).
2. GitHub Workflows with actionlint and workflow schema (root and snapshots).
3. Custom GitHub Actions metadata against vendor.github-actions schema (root and snapshots).
4. Renovate configuration against vendor.renovate schema (root and snapshots).
5. Protostar emitted JSON schemas against JSON Schema Draft 2020-12 metaschema.
6. Internal template definitions against Protostar's exported schema.
7. Root and snapshot pyproject.toml files against PEP 621 schema.

Run:
    uv run python scripts/check_schemas.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import (
    DOCS_GENERATED_DIR,
    REPO_ROOT,
    SNAPSHOTS_DIR,
    SRC_DIR,
    VENV_BIN,
    run_repo_cmd,
)


def ensure_environment_synced() -> None:
    """Ensures the virtual environment is synced via uv before validation checks."""
    try:
        run_repo_cmd(["uv", "sync", "--quiet"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(
            f"\033[1;31m✖ Failed to sync environment with uv: {e}\033[0m",
            file=sys.stderr,
        )
        sys.exit(1)

    if VENV_BIN.is_dir() and str(VENV_BIN) not in os.environ.get("PATH", "").split(
        os.pathsep
    ):
        os.environ["PATH"] = f"{VENV_BIN}{os.pathsep}{os.environ.get('PATH', '')}"


def _run_validator(name: str, cmd: list[str]) -> bool:
    """Runs a validator subprocess and prints colored status.

    Args:
        name: Display name of the validation check.
        cmd: Command and arguments to execute.

    Returns:
        True if the validation command exited with 0, False otherwise.
    """
    print(f"\033[1;34m=== Validating {name} ===\033[0m")
    result = run_repo_cmd(cmd)
    if result.returncode == 0:
        print(f"\033[1;32m✔ {name} valid\033[0m\n")
        return True
    print(f"\033[1;31m✖ {name} failed validation\033[0m\n", file=sys.stderr)
    return False


def validate_prek_configs() -> bool:
    """Validates root and snapshot pre-commit / prek configuration files."""
    prek_files: list[Path] = []
    root_config = REPO_ROOT / ".pre-commit-config.yaml"
    if root_config.is_file():
        prek_files.append(root_config)

    snapshots_dir = SNAPSHOTS_DIR
    if snapshots_dir.is_dir():
        prek_files.extend(sorted(snapshots_dir.rglob("pre-commit-config.fixture.yaml")))
        prek_files.extend(sorted(snapshots_dir.rglob(".pre-commit-config.yaml")))

    if not prek_files:
        print("No pre-commit/prek configuration files found.")
        return True

    cmd = [
        "prek",
        "validate-config",
        *[str(p.relative_to(REPO_ROOT)) for p in prek_files],
    ]
    return _run_validator("Pre-Commit / Prek Configurations", cmd)


def validate_github_workflows() -> bool:
    """Validates root and snapshot GitHub Workflows with actionlint and workflow schema."""
    workflow_files: list[Path] = []
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if workflows_dir.is_dir():
        workflow_files.extend(sorted(workflows_dir.glob("*.yml")))
        workflow_files.extend(sorted(workflows_dir.glob("*.yaml")))

    snapshots_dir = SNAPSHOTS_DIR
    if snapshots_dir.is_dir():
        for path in sorted(snapshots_dir.rglob("*.yml")) + sorted(
            snapshots_dir.rglob("*.yaml")
        ):
            if "workflows" in path.parts:
                workflow_files.append(path)

    if not workflow_files:
        return True

    rel_paths = [str(p.relative_to(REPO_ROOT)) for p in workflow_files]
    schema_ok = _run_validator(
        "GitHub Workflows Schema",
        ["check-jsonschema", "--builtin-schema", "vendor.github-workflows", *rel_paths],
    )
    actionlint_ok = _run_validator(
        "GitHub Workflows (actionlint)", ["actionlint", *rel_paths]
    )
    return schema_ok and actionlint_ok


def validate_github_actions() -> bool:
    """Validates root and snapshot custom composite action definitions against GitHub Actions schema."""
    action_files: list[Path] = []
    actions_dir = REPO_ROOT / ".github" / "actions"
    if actions_dir.is_dir():
        action_files.extend(sorted(actions_dir.rglob("action.yml")))
        action_files.extend(sorted(actions_dir.rglob("action.yaml")))

    snapshots_dir = SNAPSHOTS_DIR
    if snapshots_dir.is_dir():
        for path in sorted(snapshots_dir.rglob("action.yml")) + sorted(
            snapshots_dir.rglob("action.yaml")
        ):
            action_files.append(path)

    if not action_files:
        return True

    cmd = [
        "check-jsonschema",
        "--builtin-schema",
        "vendor.github-actions",
        *[str(p.relative_to(REPO_ROOT)) for p in action_files],
    ]
    return _run_validator("GitHub Actions Metadata", cmd)


def validate_renovate() -> bool:
    """Validates root and snapshot Renovate configuration against Renovate schema."""
    renovate_files: list[Path] = []
    root_renovate = REPO_ROOT / ".github" / "renovate.json"
    if root_renovate.is_file():
        renovate_files.append(root_renovate)

    snapshots_dir = SNAPSHOTS_DIR
    if snapshots_dir.is_dir():
        renovate_files.extend(sorted(snapshots_dir.rglob("renovate.json")))

    if not renovate_files:
        return True

    cmd = [
        "check-jsonschema",
        "--builtin-schema",
        "vendor.renovate",
        *[str(p.relative_to(REPO_ROOT)) for p in renovate_files],
    ]
    return _run_validator("Renovate Configuration", cmd)


def validate_metaschemas() -> bool:
    """Validates Protostar emitted JSON schemas against Draft 2020-12 metaschema."""
    docs_generated_dir = DOCS_GENERATED_DIR
    schema_files: list[Path] = []
    if docs_generated_dir.is_dir():
        schema_files.extend(sorted(docs_generated_dir.glob("*_schema.json")))

    if not schema_files:
        return True

    cmd = [
        "check-jsonschema",
        "--check-metaschema",
        *[str(p.relative_to(REPO_ROOT)) for p in schema_files],
    ]
    return _run_validator("Emitted JSON Metaschemas", cmd)


def validate_template_blueprints() -> bool:
    """Validates internal template definitions against Protostar's exported schema."""
    templates_dir = SRC_DIR / "protostar" / "templates"
    template_files = sorted(templates_dir.glob("*.toml"))
    if not template_files:
        return True

    schema_cmd = ["protostar", "export-schema", "--json"]
    schema_json = run_repo_cmd(schema_cmd, check=True, capture_output=True).stdout
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write(schema_json)
        tmp_path = tmp.name

    try:
        cmd = [
            "check-jsonschema",
            "--schemafile",
            tmp_path,
            "--force-filetype",
            "toml",
            *[str(p.relative_to(REPO_ROOT)) for p in template_files],
        ]
        return _run_validator("Internal Template Blueprints", cmd)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def validate_pyproject_files() -> bool:
    """Validates root and snapshot pyproject.toml files against PEP 621 schema."""
    pyproject_files: list[Path] = []
    root_pyproject = REPO_ROOT / "pyproject.toml"
    if root_pyproject.is_file():
        pyproject_files.append(root_pyproject)

    snapshots_dir = SNAPSHOTS_DIR
    if snapshots_dir.is_dir():
        pyproject_files.extend(sorted(snapshots_dir.rglob("pyproject.toml")))

    if not pyproject_files:
        return True

    cmd = [
        "check-jsonschema",
        "--schemafile",
        "https://json.schemastore.org/pyproject.json",
        *[str(p.relative_to(REPO_ROOT)) for p in pyproject_files],
    ]
    return _run_validator("PEP 621 pyproject.toml Specifications", cmd)


def main() -> None:
    """Runs all schema validation checks and exits with non-zero on failure."""
    ensure_environment_synced()

    checks = [
        validate_prek_configs,
        validate_github_workflows,
        validate_github_actions,
        validate_renovate,
        validate_metaschemas,
        validate_template_blueprints,
        validate_pyproject_files,
    ]

    all_passed = True
    for check in checks:
        if not check():
            all_passed = False

    if not all_passed:
        print("\033[1;31m✖ Schema validation failed.\033[0m", file=sys.stderr)
        sys.exit(1)

    print("\033[1;32m✔ All schema checks passed.\033[0m")


if __name__ == "__main__":
    main()
