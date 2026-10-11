"""Records the nightly benchmark comparisons, and finds slowdowns in them.

Each night on main, one Linux job compares the commit with a baseline
(``python -m scripts.benchmarks compare``), in alternating rounds on one
runner. This module chooses that baseline (``plan``), adds the results to
``metrics/benchmark-history.json`` on gh-pages (``record``), files a slowdown
found twice (``issue``), writes a pull request's comparison as a comment
(``comment``), and summarizes runs of a commit against itself (``calibrate``).

A slowdown is judged on the CPU time Protostar's own process used, the least
noisy measure: the commands a run waits on are uv's and git's, and the cost
budgets already check which ones run. A scenario is *suspect* when the whole
95% interval of its change lies at least ``THRESHOLD`` above no change, and a
*regression* when the next run, measured against the same baseline, finds it
again. A run with a suspect keeps its baseline, so the next one re-measures the
same change; any other run moves the baseline up to its own commit.

    python3 -m scripts.benchmarks.report plan --event EVENT --head SHA ...
    python3 -m scripts.benchmarks.report record --results DIR --history PATH ...

Runs on a bare runner, so it needs the standard library and
``scripts.benchmarks.stats`` alone.
"""

from __future__ import annotations

import argparse
import enum
import json
import re
import statistics
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from scripts.benchmarks.stats import Comparison, compare
from scripts.nightly_report import Tracker

REGRESSION_TRACKER = Tracker(
    label="performance-regression",
    title="Benchmarks found a slowdown on main",
    color="fbca04",
    description="The nightly benchmarks confirmed a slowdown",
)

# How much slower, at the least, Protostar's CPU time must be before a change
# counts. Runs of a commit against itself on GitHub's runners (``calibrate``)
# stay well inside it; see docs/developer/ci.md.
THRESHOLD = 0.10

# Routine comparisons use Linux to conserve macOS runners. Platform-specific
# performance investigations use the local harness.
OPERATING_SYSTEMS = ("ubuntu-latest",)

# Each operating system's artifact: ``benchmarks-<os>``, holding RESULT.
ARTIFACT_PREFIX = "benchmarks-"
RESULT = "benchmarks.json"

# Marks the pull request comment this module writes, so a new run replaces it.
COMMENT_MARKER = "<!-- protostar-benchmarks -->"

_SHA = re.compile(r"[0-9a-f]{40}")

# Ratios are stored to four places, far coarser than this.
_ROUNDING = 1e-9


class Status(enum.StrEnum):
    """What a scenario's change in one run means."""

    STEADY = "steady"
    FASTER = "faster"
    SUSPECT = "suspect"
    REGRESSION = "regression"


class BenchmarkReportError(Exception):
    """The results are incomplete or inconsistent, so nothing is recorded."""


class GitHub(Protocol):
    """The issue operations filing a regression needs."""

    def open_issue(self, tracker: Tracker) -> int | None: ...
    def has_report(self, number: int, body: str) -> bool: ...
    def create_issue(self, tracker: Tracker, body: str) -> None: ...
    def comment(self, number: int, body: str) -> None: ...


@dataclass(frozen=True)
class Regression:
    """A slowdown two runs found against the same baseline.

    Attributes:
        os: The operating system it was found on.
        scenario: The scenario that slowed down.
        baseline: The commit it was measured against.
        commit: The commit it was found in.
        change: Its CPU time change in the run that confirmed it.
    """

    os: str
    scenario: str
    baseline: str
    commit: str
    change: dict[str, float]


def read_history(path: Path) -> list[dict[str, Any]]:
    """Reads the recorded runs, treating a missing history as the first run."""
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise BenchmarkReportError(f"{path} is not a list of runs.")
    return entries


def _latest(history: Sequence[dict[str, Any]], os: str) -> dict[str, Any] | None:
    runs = [entry for entry in history if entry["os"] == os]
    return runs[-1] if runs else None


def _suspects(entry: dict[str, Any]) -> list[str]:
    return [
        name
        for name, result in entry["scenarios"].items()
        if result["status"] == Status.SUSPECT
    ]


def baseline(
    history: Sequence[dict[str, Any]],
    os: str,
    head: str,
    is_ancestor: Callable[[str, str], bool],
) -> str | None:
    """Chooses the commit ``head`` is compared with on one operating system.

    Args:
        history: The recorded runs, oldest first.
        os: The operating system.
        head: The commit to measure.
        is_ancestor: Whether a commit is an ancestor of (or is) another.

    Returns:
        The latest recorded commit, or that run's own baseline when it left a
        suspect to re-measure. ``head`` itself, measured against itself, when
        nothing usable is recorded. None when ``head`` is recorded already and
        left nothing to re-measure.
    """
    latest = _latest(history, os)
    if latest is None:
        return head
    if _suspects(latest):
        chosen = str(latest["baseline"])
    elif latest["commit"] == head:
        return None
    else:
        chosen = str(latest["commit"])
    # History rewritten on main leaves a baseline that isn't behind head.
    return chosen if is_ancestor(chosen, head) else head


def plan(
    event: str,
    head: str,
    *,
    history: Sequence[dict[str, Any]] = (),
    base: str | None = None,
    repeats: int = 0,
    is_ancestor: Callable[[str, str], bool] = lambda _ancestor, _commit: True,
) -> list[dict[str, str]]:
    """Returns the measuring jobs a run starts, as a matrix's ``include``.

    Args:
        event: What started the run: ``schedule``, ``workflow_dispatch``, or
            ``pull_request``.
        head: The commit to measure.
        history: The recorded runs, for a run on main.
        base: A pull request's base commit.
        repeats: For a calibration, how many times to compare ``head`` with
            itself on each operating system; zero otherwise.
        is_ancestor: Whether a commit is an ancestor of (or is) another.

    Returns:
        One entry per job: its operating system, baseline, and artifact name.

    Raises:
        BenchmarkReportError: If a pull request run has no base commit.
    """
    if event == "pull_request":
        if base is None:
            raise BenchmarkReportError("A pull request comparison needs its base.")
        # One runner: a pull request's workflows share the account's limit.
        return [_job("ubuntu-latest", base)]
    if repeats:
        return [
            _job(os, head, f"{os}-{repeat}")
            for os in OPERATING_SYSTEMS
            for repeat in range(1, repeats + 1)
        ]
    jobs = []
    for os in OPERATING_SYSTEMS:
        chosen = baseline(history, os, head, is_ancestor)
        if chosen is not None:
            jobs.append(_job(os, chosen))
    return jobs


def _job(os: str, against: str, name: str | None = None) -> dict[str, str]:
    return {
        "os": os,
        "baseline": against,
        "artifact": f"{ARTIFACT_PREFIX}{name or os}",
    }


def _medians(samples: dict[str, list[float]]) -> dict[str, float]:
    return {
        metric: round(statistics.median(values) * 1000, 3)
        for metric, values in sorted(samples.items())
    }


def _change(comparison: Comparison) -> dict[str, float]:
    return {
        "ratio": round(comparison.ratio, 4),
        "low": round(comparison.low, 4),
        "high": round(comparison.high, 4),
    }


def classify(
    change: dict[str, float],
    scenario: str,
    against: str,
    previous: dict[str, Any] | None,
) -> Status:
    """Judges one scenario's CPU time change in one run.

    Args:
        change: The ratio of the change and its 95% interval.
        scenario: The scenario.
        against: The baseline this run measured against.
        previous: The run before on the same operating system, if any.

    Returns:
        Suspect the first time the change is slower by at least THRESHOLD,
        and regression when the next run against the same baseline finds it
        too.
    """
    # Exactly at the threshold counts, whichever way the arithmetic rounds.
    if change["low"] >= 1 + THRESHOLD - _ROUNDING:
        found_before = (
            previous is not None
            and previous["baseline"] == against
            and previous["scenarios"].get(scenario, {}).get("status") == Status.SUSPECT
        )
        return Status.REGRESSION if found_before else Status.SUSPECT
    if change["high"] <= 1 - THRESHOLD + _ROUNDING:
        return Status.FASTER
    return Status.STEADY


def _result(directory: Path) -> dict[str, Any]:
    path = directory / RESULT
    if not path.is_file():
        raise BenchmarkReportError(f"Missing benchmark results: {path}.")
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("mode") != "compare" or not result.get("samples"):
        raise BenchmarkReportError(f"Not a comparison with samples: {path}.")
    return dict(result)


def record(
    results: Path,
    history: list[dict[str, Any]],
    *,
    commit: str,
    date: str,
    run_id: str,
) -> tuple[list[dict[str, Any]], list[Regression]]:
    """Adds one night's comparisons to the history.

    Args:
        results: A directory with one folder per operating system's artifact.
        history: The recorded runs, oldest first.
        commit: The commit the night measured.
        date: When it was measured, as a UTC timestamp.
        run_id: The workflow run, so recording it again changes nothing.

    Returns:
        The history with the night's runs added, and the regressions they
        confirmed.

    Raises:
        BenchmarkReportError: If a result is missing, measured another commit,
            or is older than the latest recorded run.
    """
    if not _SHA.fullmatch(commit):
        raise BenchmarkReportError("The commit must be a full Git commit hash.")
    when = datetime.fromisoformat(date)
    offset = when.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise BenchmarkReportError("The date must be a UTC timestamp.")
    if history and datetime.fromisoformat(history[-1]["date"]) > when:
        raise BenchmarkReportError("Refusing to record a run older than the latest.")
    folders = sorted(path for path in results.iterdir() if path.is_dir())
    if not folders:
        raise BenchmarkReportError(f"No benchmark results in {results}.")
    entries = list(history)
    regressions: list[Regression] = []
    for folder in folders:
        os = folder.name.removeprefix(ARTIFACT_PREFIX)
        if os not in OPERATING_SYSTEMS:
            raise BenchmarkReportError(f"Unexpected benchmark artifact {folder.name}.")
        if any(e["run_id"] == run_id and e["os"] == os for e in entries):
            continue
        result = _result(folder)
        if result["machine"]["commit"] != commit:
            raise BenchmarkReportError(f"{folder.name} measured another commit.")
        against = str(result["baseline"])
        previous = _latest(entries, os)
        scenarios: dict[str, Any] = {}
        for name, sides in sorted(result["samples"].items()):
            change = _change(
                compare(sides["baseline"]["cpu"], sides["candidate"]["cpu"])
            )
            status = classify(change, name, against, previous)
            scenarios[name] = {
                **_medians(sides["candidate"]),
                "change": change,
                "status": str(status),
            }
            if status is Status.REGRESSION:
                regressions.append(Regression(os, name, against, commit, change))
        entries.append(
            {
                "commit": commit,
                "baseline": against,
                "date": date,
                "run_id": run_id,
                "os": os,
                "python": result["machine"]["python"],
                "runs": result["runs"],
                "scenarios": scenarios,
            }
        )
    return entries, regressions


def _percent(change: dict[str, float]) -> str:
    return (
        f"{change['ratio'] - 1:+.1%} "
        f"(95% interval {change['low'] - 1:+.1%} to {change['high'] - 1:+.1%})"
    )


def regression_body(regressions: Sequence[Regression], repo: str, run_url: str) -> str:
    """Describes confirmed slowdowns and the commits that could be the cause.

    Args:
        regressions: What the run confirmed.
        repo: The repository, as OWNER/NAME.
        run_url: The workflow run that confirmed them.

    Returns:
        Markdown for the issue body or a comment.
    """
    lines = [
        f"The nightly benchmarks found Protostar's own CPU time at least "
        f"{THRESHOLD:.0%} slower in two runs in a row ([run]({run_url})).",
        "",
        "| Scenario | OS | Change | Commits |",
        "| --- | --- | --- | --- |",
    ]
    for item in regressions:
        commits = f"https://github.com/{repo}/compare/{item.baseline}...{item.commit}"
        lines.append(
            f"| `{item.scenario}` | {item.os} | {_percent(item.change)} | "
            f"[`{item.baseline[:7]}...{item.commit[:7]}`]({commits}) |"
        )
    lines += [
        "",
        "Reproduce it with `just bench-compare <baseline> <scenario>`. Close this "
        "issue once the slowdown is fixed, or accepted as the cost of a change.",
    ]
    return "\n".join(lines) + "\n"


def comment_body(result: dict[str, Any], base: str, head: str) -> str:
    """Writes a pull request's comparison as a comment.

    Args:
        result: The comparison the pull request's job wrote.
        base: The base commit it was measured against.
        head: The pull request's commit.

    Returns:
        Markdown, starting with the marker that lets a later run replace it.
    """
    lines = [
        COMMENT_MARKER,
        f"**Benchmarks:** `{head[:7]}` against its base `{base[:7]}` on "
        f"{result['machine']['platform']}, {result['runs']} alternating rounds.",
        "",
        "| Scenario | Wall | Protostar CPU | Verdict |",
        "| --- | --- | --- | --- |",
    ]
    for name, sides in sorted(result["samples"].items()):
        wall = compare(sides["baseline"]["wall"], sides["candidate"]["wall"])
        cpu = compare(sides["baseline"]["cpu"], sides["candidate"]["cpu"])
        verdict = classify(_change(cpu), name, base, None)
        shown = "slower" if verdict is Status.SUSPECT else str(verdict)
        lines.append(
            f"| `{name}` | {wall.ratio - 1:+.1%} | {_percent(_change(cpu))} | {shown} |"
        )
    lines += [
        "",
        f"A scenario reads slower or faster only when its whole interval is at "
        f"least {THRESHOLD:.0%} from no change. Re-run by removing and adding "
        "the `run-benchmark` label.",
    ]
    return "\n".join(lines) + "\n"


def calibration_body(results: Path) -> str:
    """Summarizes runs that compared a commit with itself.

    Args:
        results: A directory with one folder per calibration job's artifact.

    Returns:
        Markdown: each run's widest change by operating system, and how close
        the noise came to THRESHOLD.
    """
    rows: list[tuple[str, str, float, float]] = []
    for folder in sorted(path for path in results.iterdir() if path.is_dir()):
        result = _result(folder)
        for name, sides in sorted(result["samples"].items()):
            change = compare(sides["baseline"]["cpu"], sides["candidate"]["cpu"])
            rows.append(
                (
                    folder.name.removeprefix(ARTIFACT_PREFIX),
                    name,
                    change.low - 1,
                    change.high - 1,
                )
            )
    widest = max((max(abs(low), abs(high)) for _, _, low, high in rows), default=0.0)
    lines = [
        "**Benchmark calibration:** a commit compared with itself, so every "
        "difference below is noise.",
        "",
        f"The widest interval bound is {widest:.1%}; the threshold is {THRESHOLD:.0%}.",
        "",
        "| Job | Scenario | CPU 95% interval |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {job} | `{name}` | {low:+.1%} to {high:+.1%} |"
        for job, name, low, high in rows
    ]
    return "\n".join(lines) + "\n"


def _is_ancestor(ancestor: str, commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, commit],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _post_comment(repo: str, number: str, body: str) -> None:
    """Replaces this module's earlier comment on the pull request, or adds one."""

    def gh(*args: str) -> str:
        return subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True
        ).stdout

    pages = json.loads(
        gh(
            "api",
            f"repos/{repo}/issues/{number}/comments?per_page=100",
            "--paginate",
            "--slurp",
        )
    )
    earlier = next(
        (
            c["id"]
            for page in pages
            for c in page
            if COMMENT_MARKER in (c["body"] or "")
        ),
        None,
    )
    if earlier is None:
        gh("api", f"repos/{repo}/issues/{number}/comments", "--field", f"body={body}")
    else:
        gh(
            "api",
            f"repos/{repo}/issues/comments/{earlier}",
            "--method",
            "PATCH",
            "--field",
            f"body={body}",
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    planned = commands.add_parser("plan", help="Print the measuring jobs as JSON.")
    planned.add_argument("--event", required=True)
    planned.add_argument("--head", required=True)
    planned.add_argument("--base")
    planned.add_argument("--history", type=Path)
    planned.add_argument("--repeats", type=int, default=0)

    recorded = commands.add_parser("record", help="Add a night's results.")
    recorded.add_argument("--results", type=Path, required=True)
    recorded.add_argument("--history", type=Path, required=True)
    recorded.add_argument("--commit", required=True)
    recorded.add_argument("--date", required=True)
    recorded.add_argument("--run-id", required=True)
    recorded.add_argument("--regressions", type=Path, required=True)

    filed = commands.add_parser("issue", help="File confirmed regressions.")
    filed.add_argument("--regressions", type=Path, required=True)
    filed.add_argument("--repo", required=True)
    filed.add_argument("--run-url", required=True)

    commented = commands.add_parser(
        "comment", help="Comment a pull request's comparison."
    )
    commented.add_argument("--result", type=Path, required=True)
    commented.add_argument("--base", required=True)
    commented.add_argument("--head", required=True)
    commented.add_argument("--repo", required=True)
    commented.add_argument("--number", required=True)

    calibrated = commands.add_parser(
        "calibrate", help="Summarize runs of a commit against itself."
    )
    calibrated.add_argument("--results", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Runs the command named on the command line."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            history = read_history(args.history) if args.history else []
            jobs = plan(
                args.event,
                args.head,
                history=history,
                base=args.base,
                repeats=args.repeats,
                is_ancestor=_is_ancestor,
            )
            print(json.dumps({"include": jobs}))
        elif args.command == "record":
            history = read_history(args.history)
            entries, regressions = record(
                args.results,
                history,
                commit=args.commit,
                date=args.date,
                run_id=args.run_id,
            )
            args.history.parent.mkdir(parents=True, exist_ok=True)
            args.history.write_text(
                json.dumps(entries, indent=2) + "\n", encoding="utf-8"
            )
            args.regressions.write_text(
                json.dumps([vars(item) for item in regressions], indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"Recorded {len(entries) - len(history)} run(s); "
                f"{len(regressions)} regression(s) confirmed."
            )
        elif args.command == "issue":
            file_regressions(args.regressions, args.repo, args.run_url)
        elif args.command == "comment":
            result = json.loads(args.result.read_text(encoding="utf-8"))
            _post_comment(
                args.repo, args.number, comment_body(result, args.base, args.head)
            )
        else:
            print(calibration_body(args.results))
    except BenchmarkReportError as error:
        raise SystemExit(str(error)) from error


def file_regressions(
    path: Path, repo: str, run_url: str, github: GitHub | None = None
) -> None:
    """Opens the regression issue, or comments on the open one.

    A run that confirmed nothing files nothing, and the issue stays open until
    someone closes it: whether to fix a slowdown or accept it is a decision.

    Args:
        path: The regressions ``record`` wrote.
        repo: The repository, as OWNER/NAME.
        run_url: The workflow run that confirmed them.
        github: The issue operations; the ``gh`` command line when None.
    """
    from scripts.nightly_report import GhCli

    found = [
        Regression(**item) for item in json.loads(path.read_text(encoding="utf-8"))
    ]
    if not found:
        return
    github = github or GhCli(repo)
    body = regression_body(found, repo, run_url)
    tracker = REGRESSION_TRACKER
    number = github.open_issue(tracker)
    if number is None:
        github.create_issue(tracker, body)
    elif not github.has_report(number, body):
        github.comment(number, body)


if __name__ == "__main__":
    main()
