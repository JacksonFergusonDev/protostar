"""Validates repository and snapshot configurations against official schemas.

Checks (``CHECKS``, then the schemas Protostar emits):
1. Pre-commit & prek configurations against prek's parser (root and snapshots).
2. GitHub Workflows with actionlint and workflow schema (root and snapshots).
3. Custom GitHub Actions metadata against vendor.github-actions schema (root and snapshots).
4. Renovate configuration against vendor.renovate schema (root and snapshots).
5. Root and snapshot pyproject.toml files against PEP 621 schema.
6. Protostar's emitted JSON schemas against the Draft 2020-12 metaschema.
7. Internal template definitions against Protostar's exported schema.

Run:
    uv run python -m scripts.check_schemas
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts._common import (
    REPO_ROOT,
    SNAPSHOTS_DIR,
    SRC_DIR,
    OutputStyle,
    report,
    run_repo_cmd,
)


def _run_validator(name: str, cmd: list[str]) -> bool:
    """Runs a validator subprocess and prints colored status.

    Args:
        name: Display name of the validation check.
        cmd: Command and arguments to execute.

    Returns:
        True if the validation command exited with 0, False otherwise.
    """
    report(f"=== Validating {name} ===", style=OutputStyle.TITLE)
    result = run_repo_cmd(cmd)
    if result.returncode == 0:
        report(f"OK {name} valid\n", style=OutputStyle.SUCCESS)
        return True
    report(f"FAIL {name} failed validation\n", stderr=True, style=OutputStyle.ERROR)
    return False


def _find(root: Sequence[str], snapshots: Sequence[str] = ()) -> list[Path]:
    """Returns the repository files matching ``root`` and the snapshot files matching ``snapshots``.

    Args:
        root: Glob patterns relative to the repository root.
        snapshots: File-name patterns searched for anywhere in the snapshots.
    """
    found = [path for pattern in root for path in sorted(REPO_ROOT.glob(pattern))]
    if SNAPSHOTS_DIR.is_dir():
        found += [
            path
            for pattern in snapshots
            for path in sorted(SNAPSHOTS_DIR.rglob(pattern))
        ]
    return [path for path in found if path.is_file()]


@dataclass(frozen=True)
class SchemaCheck:
    """Files of one kind, and the validators that check them.

    Attributes:
        files: Finds the files, when the check runs.
        validators: Each validator's name and command; the files follow it.
    """

    files: Callable[[], list[Path]]
    validators: tuple[tuple[str, tuple[str, ...]], ...]


def _snapshot_workflows() -> list[Path]:
    return [
        path
        for path in _find([".github/workflows/*.yml", ".github/workflows/*.yaml"])
        + _find([], ["*.yml", "*.yaml"])
        if path.is_relative_to(REPO_ROOT / ".github") or "workflows" in path.parts
    ]


CHECKS: tuple[SchemaCheck, ...] = (
    SchemaCheck(
        lambda: _find([".pre-commit-config.yaml"], ["pre-commit-config.fixture.yaml"]),
        (("Pre-Commit / Prek Configurations", ("prek", "validate-config")),),
    ),
    SchemaCheck(
        _snapshot_workflows,
        (
            (
                "GitHub Workflows Schema",
                ("check-jsonschema", "--builtin-schema", "vendor.github-workflows"),
            ),
            ("GitHub Workflows (actionlint)", ("actionlint",)),
        ),
    ),
    SchemaCheck(
        lambda: _find(
            [".github/actions/**/action.yml", ".github/actions/**/action.yaml"],
            ["action.yml", "action.yaml"],
        ),
        (
            (
                "GitHub Actions Metadata",
                ("check-jsonschema", "--builtin-schema", "vendor.github-actions"),
            ),
        ),
    ),
    SchemaCheck(
        lambda: _find([".github/renovate.json"], ["renovate.json"]),
        (
            (
                "Renovate Configuration",
                ("check-jsonschema", "--builtin-schema", "vendor.renovate"),
            ),
        ),
    ),
    SchemaCheck(
        lambda: _find(["pyproject.toml"], ["pyproject.toml"]),
        (
            (
                "PEP 621 pyproject.toml Specifications",
                (
                    "check-jsonschema",
                    "--schemafile",
                    "https://json.schemastore.org/pyproject.json",
                ),
            ),
        ),
    ),
)


def run_check(check: SchemaCheck) -> bool:
    """Runs every validator of a check over its files; a check with none passes."""
    files = [str(path.relative_to(REPO_ROOT)) for path in check.files()]
    if not files:
        return True
    results = [
        _run_validator(name, [*command, *files]) for name, command in check.validators
    ]
    return all(results)


def validate_emitted_schemas() -> bool:
    """Checks the schemas Protostar publishes, then the built-in templates against one.

    The template schema comes from ``protostar export-schema``; the review and
    application envelopes come from ``protostar.cli.schema``. Each must be a
    valid Draft 2020-12 schema, and every built-in template must satisfy the
    template schema.
    """
    from protostar.cli.schema import application_schema, review_schema

    template_json = run_repo_cmd(
        ["protostar", "export-schema", "--json"], check=True, capture_output=True
    ).stdout
    with tempfile.TemporaryDirectory() as directory:
        schemas = {
            "template_schema.json": template_json,
            "review_schema.json": json.dumps(review_schema()),
            "application_schema.json": json.dumps(application_schema()),
        }
        for name, text in schemas.items():
            Path(directory, name).write_text(text, encoding="utf-8")
        metaschemas_ok = _run_validator(
            "Emitted JSON Metaschemas",
            [
                "check-jsonschema",
                "--check-metaschema",
                *(str(Path(directory, name)) for name in schemas),
            ],
        )
        templates = sorted((SRC_DIR / "protostar" / "templates").glob("*.toml"))
        templates_ok = not templates or _run_validator(
            "Internal Template Blueprints",
            [
                "check-jsonschema",
                "--schemafile",
                str(Path(directory, "template_schema.json")),
                "--force-filetype",
                "toml",
                *(str(path.relative_to(REPO_ROOT)) for path in templates),
            ],
        )
    return metaschemas_ok and templates_ok


def main() -> None:
    """Runs all schema validation checks and exits with non-zero on failure."""
    results = [run_check(check) for check in CHECKS]
    results.append(validate_emitted_schemas())
    if not all(results):
        report("FAIL Schema validation failed.", stderr=True, style=OutputStyle.ERROR)
        sys.exit(1)

    report("OK All schema checks passed.", style=OutputStyle.SUCCESS)


if __name__ == "__main__":
    main()
