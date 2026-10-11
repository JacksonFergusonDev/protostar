"""Records how many faults the nightly rollback jobs injected and restored.

Each rollback job writes the faults it raised and how many the project
survived (``tests/rollback_report.py``). Once every job has reported, this
adds them up. Zero unrestored faults add a point to the history; any failure
only changes the badge, so the history stays a record of green runs.

Run:
    python3 -m scripts.rollback_report record --results DIR --matrix JSON \\
        --history PATH --latest PATH --state PATH --commit SHA \\
        --date UTC --run-id ID --run-attempt ATTEMPT
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

# Runs without the project installed (the workflow's publish job), so it
# depends on the standard library alone.
from scripts import _publish

LABEL = "rollback faults restored"


class HistoryEntry(TypedDict):
    """One fully green run, keeping the counts per operating system and template."""

    commit: str
    date: str
    cells: list[dict[str, object]]


class Publication(TypedDict):
    """The latest published attempt, including runs that only changed the badge."""

    commit: str
    date: str
    run_id: int
    run_attempt: int


def publication_key(publication: Publication) -> tuple[datetime, int, int]:
    """Order runs by creation time, breaking ties by run id and then attempt."""
    return (
        datetime.fromisoformat(publication["date"]),
        publication["run_id"],
        publication["run_attempt"],
    )


class RollbackReportError(Exception):
    """The results are incomplete or inconsistent, so nothing is published."""


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
    return _publish.badge(LABEL, f"{failed:,} failing" if failed else f"{passed:,}")


def record(args: argparse.Namespace) -> None:
    """Writes the badge for a complete run, and its history point if none failed."""
    try:
        _record(args)
    except (_publish.PublicationError, RollbackReportError) as error:
        raise SystemExit(str(error)) from error


def _record(args: argparse.Namespace) -> None:
    _publish.check_commit(args.commit)
    date = _publish.utc_date(args.date)
    if args.run_id < 1 or args.run_attempt < 1:
        raise SystemExit("--run-id and --run-attempt must be positive integers.")
    publication: Publication = {
        "commit": args.commit,
        "date": args.date,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
    }
    if args.state.exists():
        previous: Publication = json.loads(args.state.read_text(encoding="utf-8"))
        if publication_key(publication) < publication_key(previous):
            raise SystemExit(
                "Refusing to publish a run older than the latest publication."
            )
        if publication_key(publication) == publication_key(previous):
            return
    entries: list[HistoryEntry] = _publish.read_history(args.history)
    _publish.check_newest(entries, date)
    rows, failed = combine(args.results, json.loads(args.matrix)["include"])
    passed = sum(row["passed"] for row in rows)  # type: ignore[misc]
    # Several attempts or runs of one commit add only one green history point.
    if not failed and not any(item["commit"] == args.commit for item in entries):
        entries.append({"commit": args.commit, "date": args.date, "cells": rows})
    _publish.write_json(args.history, entries)
    _publish.write_json(args.latest, badge(passed, failed))
    _publish.write_json(args.state, publication)
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
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("--commit", required=True)
    command.add_argument(
        "--date", required=True, help="The originating run's creation time in UTC."
    )
    command.add_argument("--run-id", type=int, required=True)
    command.add_argument("--run-attempt", type=int, required=True)
    command.set_defaults(func=record)
    return parser.parse_args()


def main() -> None:
    """Runs the selected command."""
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
