"""Records how many faults the nightly rollback jobs injected and restored.

Each rollback job writes the faults it raised and how many the project
survived (``tests/rollback_report.py``). Once every job has reported, this
adds them up. Zero unrestored faults add a point to the history; any failure
only changes the badge, so the history stays a record of green runs.

Run:
    python3 scripts/rollback_report.py record --results DIR --matrix JSON \\
        --history PATH --latest PATH --commit SHA
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

# Runs without the project installed (the workflow's publish job), so it
# depends on the standard library alone.
LABEL = "rollback faults restored"


class HistoryEntry(TypedDict):
    """One fully green run, keeping the counts per operating system and template."""

    commit: str
    date: str
    cells: list[dict[str, object]]


class RollbackReportError(Exception):
    """The results are incomplete or inconsistent, so nothing is published."""


def read_history(path: Path) -> list[HistoryEntry]:
    """Read recorded runs, treating a missing history as the first run."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def combine(
    results: Path, matrix: list[dict[str, str]]
) -> tuple[list[dict[str, object]], int]:
    """Adds every job's counts into one row per operating system and template.

    Args:
        results: A directory holding one folder per job, named by its artifact,
            each with the ``report.json`` the job wrote.
        matrix: The ``include`` entries of the rollback matrix.

    Returns:
        The rows (``os``, ``template``, ``passed``), and how many faults failed.

    Raises:
        RollbackReportError: A planned job has no report, an unplanned one has,
            or a report holds no faults or another template's.
    """
    expected = {entry["artifact"] for entry in matrix}
    actual = {path.name for path in results.iterdir() if path.is_dir()}
    if not expected or actual != expected:
        raise RollbackReportError(
            f"Expected artifacts {sorted(expected)}, got {sorted(actual)}."
        )
    totals: dict[tuple[str, str], int] = {}
    failed = 0
    for entry in matrix:
        path = results / entry["artifact"] / "report.json"
        if not path.is_file():
            raise RollbackReportError(f"Missing rollback report: {path}.")
        scenarios = json.loads(path.read_text(encoding="utf-8"))["scenarios"]
        if not scenarios:
            raise RollbackReportError(f"No faults reported: {path}.")
        if {row["template"] for row in scenarios.values()} != {entry["template"]}:
            raise RollbackReportError(f"Faults of another template in {path}.")
        key = (entry["os"].removesuffix("-latest"), entry["template"])
        totals[key] = totals.get(key, 0) + sum(
            row["passed"] for row in scenarios.values()
        )
        failed += sum(len(row["failed"]) for row in scenarios.values())
    rows = [
        {"os": system, "template": template, "passed": passed}
        for (system, template), passed in sorted(totals.items())
    ]
    return rows, failed


def badge(passed: int, failed: int) -> dict[str, object]:
    """Returns the shields.io endpoint payload: the count, or how many failed."""
    return {
        "schemaVersion": 1,
        "label": LABEL,
        "message": f"{failed:,} failing" if failed else f"{passed:,}",
        "color": "22d3ee",
        "labelColor": "0A0A0A",
    }


def record(args: argparse.Namespace) -> None:
    """Writes the badge for a complete run, and its history point if none failed."""
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise SystemExit("--commit must be a full Git commit hash.")
    date = datetime.fromisoformat(args.date)
    offset = date.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise SystemExit("--date must be a UTC timestamp.")
    try:
        rows, failed = combine(args.results, json.loads(args.matrix)["include"])
    except RollbackReportError as error:
        raise SystemExit(str(error)) from error
    passed = sum(row["passed"] for row in rows)  # type: ignore[misc]
    entries = read_history(args.history)
    # A retry of a recorded commit neither appends twice nor replaces a newer run.
    if not failed and not any(item["commit"] == args.commit for item in entries):
        if entries and datetime.fromisoformat(entries[-1]["date"]) > date:
            raise SystemExit(
                "Refusing to publish a run older than the latest recorded run."
            )
        entries.append({"commit": args.commit, "date": args.date, "cells": rows})
    for path, payload in (
        (args.history, entries),
        (args.latest, badge(passed, failed)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"{passed:,} faults restored, {failed:,} failing.")


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("record", help="Add up a complete run.")
    command.add_argument("--results", type=Path, required=True)
    command.add_argument("--matrix", required=True)
    command.add_argument("--history", type=Path, required=True)
    command.add_argument("--latest", type=Path, required=True)
    command.add_argument("--commit", required=True)
    command.add_argument("--date", default=datetime.now(UTC).isoformat())
    command.set_defaults(func=record)
    return parser.parse_args()


def main() -> None:
    """Runs the selected command."""
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
