"""Files a finished Nightly run on main as GitHub issues.

A failed run opens one tracking issue, or comments on the open one, naming the
failing jobs and the commits since the last passing run. A passing run closes
it. Each flaky test gets its own issue. Once its fix is marked awaiting
verification, three clean nightly runs close it; a recurrence reopens it.

Run (from the Nightly Report workflow, with GH_TOKEN set):
    python3 -m scripts.nightly_report --repo OWNER/NAME --run-id ID --sha SHA
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# Runs on a bare runner before anything is installed, so it depends on the
# standard library alone.

GATE_JOB = "Check for new commits"
PREPARATION_JOBS = frozenset({GATE_JOB, "Select rollback jobs"})
FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "cancelled"})
FLAKY_ARTIFACT_PREFIX = "flaky-tests-"
FLAKY_LIST = "flaky-tests.txt"


@dataclass(frozen=True)
class Tracker:
    """An issue the report keeps open while its condition holds."""

    label: str
    title: str
    color: str
    description: str


FAILING = Tracker(
    label="nightly-failure",
    title="Nightly checks are failing on main",
    color="d73a4a",
    description="The scheduled Nightly run failed",
)


@dataclass(frozen=True)
class Job:
    """One job of a workflow run, as the Actions API reports it."""

    name: str
    conclusion: str | None


@dataclass(frozen=True)
class Run:
    """The finished run being reported."""

    repo: str
    run_id: str
    sha: str

    @property
    def url(self) -> str:
        """The run's page on GitHub."""
        return f"https://github.com/{self.repo}/actions/runs/{self.run_id}"


@dataclass(frozen=True)
class Outcome:
    """What a run found: whether its checks ran, what failed, and what flaked."""

    ran: bool
    failed: tuple[str, ...]
    flaky: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


class GitHub(Protocol):
    """The GitHub operations the report needs."""

    def jobs(self, run: Run) -> list[Job]: ...
    def flaky_lists(self, run: Run) -> dict[str, str]: ...
    def track_tests(self, run: Run) -> None: ...
    def last_passing_sha(self, run: Run) -> str | None: ...
    def open_issue(self, tracker: Tracker) -> int | None: ...
    def has_report(self, number: int, body: str) -> bool: ...
    def create_issue(self, tracker: Tracker, body: str) -> None: ...
    def comment(self, number: int, body: str) -> None: ...
    def close(self, number: int, body: str) -> None: ...


def summarize(jobs: Sequence[Job], flaky_lists: Mapping[str, str]) -> Outcome:
    """Reads a run's jobs and its flaky-test artifacts into an outcome.

    Args:
        jobs: Every job of the run.
        flaky_lists: Each flaky-test artifact's name and its list of test ids.

    Returns:
        The outcome. It did not run when the gate skipped every check; a
        failed gate still counts as a failure.
    """
    failed = tuple(
        sorted(job.name for job in jobs if job.conclusion in FAILED_CONCLUSIONS)
    )
    checks = [job for job in jobs if job.name not in PREPARATION_JOBS]
    ran = bool(failed) or any(job.conclusion == "success" for job in checks)
    flaky: dict[str, list[str]] = {}
    for artifact, text in sorted(flaky_lists.items()):
        platform = artifact.removeprefix(FLAKY_ARTIFACT_PREFIX)
        for test in text.splitlines():
            if test.strip():
                flaky.setdefault(test.strip(), []).append(platform)
    return Outcome(
        ran=ran,
        failed=failed,
        flaky={test: tuple(platforms) for test, platforms in sorted(flaky.items())},
    )


def failure_body(run: Run, outcome: Outcome, last_passing: str | None) -> str:
    """Describes a failed run: its failing jobs and the commits that could be the cause.

    Args:
        run: The failed run.
        outcome: What it found.
        last_passing: The commit the last passing run checked, if any run has passed.

    Returns:
        Markdown for the issue body or comment.
    """
    lines = [f"Nightly failed at `{run.sha[:7]}` ([run]({run.url})).", ""]
    lines += ["Failing jobs:", ""]
    lines += [f"- {name}" for name in outcome.failed] or ["- (none reported)"]
    lines.append("")
    if last_passing is None:
        lines.append("No earlier nightly run has passed.")
    else:
        compare = f"https://github.com/{run.repo}/compare/{last_passing}...{run.sha}"
        lines.append(
            f"Changes since the last passing run (`{last_passing[:7]}`): {compare}"
        )
    return "\n".join(lines) + "\n"


def report(github: GitHub, run: Run) -> Outcome:
    """Files a finished run as issues.

    Args:
        github: The GitHub operations to use.
        run: The finished run.

    Returns:
        What the run found.
    """
    outcome = summarize(github.jobs(run), github.flaky_lists(run))
    if not outcome.ran:
        return outcome

    failing = github.open_issue(FAILING)
    if outcome.failed:
        body = failure_body(run, outcome, github.last_passing_sha(run))
        if failing is None:
            github.create_issue(FAILING, body)
        elif not github.has_report(failing, body):
            github.comment(failing, body)
    elif failing is not None:
        github.close(failing, f"Nightly passed at `{run.sha[:7]}` ([run]({run.url})).")

    github.track_tests(run)
    return outcome


class GhCli:
    """GitHub operations through the `gh` command line."""

    def __init__(self, repo: str) -> None:
        """Targets one repository.

        Args:
            repo: The repository, as OWNER/NAME.
        """
        self.repo = repo

    def _gh(self, *args: str) -> str:
        return subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True
        ).stdout

    def jobs(self, run: Run) -> list[Job]:
        """Every job of the run's latest attempt, across every page."""
        pages = json.loads(
            self._gh(
                "api",
                f"repos/{self.repo}/actions/runs/{run.run_id}/jobs?per_page=100",
                "--paginate",
                "--slurp",
            )
        )
        return [
            Job(job["name"], job["conclusion"])
            for page in pages
            for job in page["jobs"]
        ]

    def flaky_lists(self, run: Run) -> dict[str, str]:
        """Each flaky-test artifact the run uploaded, by name."""
        names = [
            artifact["name"]
            for artifact in self.artifacts(run)
            if artifact["name"].startswith(FLAKY_ARTIFACT_PREFIX)
        ]
        if not names:
            return {}
        with tempfile.TemporaryDirectory() as directory:
            for name in names:
                self._gh(
                    "run",
                    "download",
                    run.run_id,
                    "--repo",
                    self.repo,
                    "--name",
                    name,
                    "--dir",
                    str(Path(directory) / name),
                )
            return {
                name: (Path(directory) / name / FLAKY_LIST).read_text(encoding="utf-8")
                for name in names
            }

    def artifacts(self, run: Run) -> list[dict[str, Any]]:
        """Read all artifact pages, since sliced runs can upload more than 100."""
        pages = json.loads(
            self._gh(
                "api",
                f"repos/{self.repo}/actions/runs/{run.run_id}/artifacts?per_page=100",
                "--paginate",
                "--slurp",
            )
        )
        return [artifact for page in pages for artifact in page["artifacts"]]

    def track_tests(self, run: Run) -> None:
        """Verify fixes using only this attempt's explicit test results."""
        from scripts.flaky_tracking import IssueStore, Nightly, evidence_from, track

        details = json.loads(
            self._gh("api", f"repos/{self.repo}/actions/runs/{run.run_id}")
        )
        names = [
            a["name"]
            for a in self.artifacts(run)
            if a["name"].startswith("test-results-")
            and not a["expired"]
            and a["created_at"] >= details["run_started_at"]
        ]
        artifacts: dict[str, dict[str, str]] = {}
        if names:
            with tempfile.TemporaryDirectory() as directory:
                # gh extracts a single named artifact directly into --dir;
                # multiple named artifacts get their own subdirectories.
                destination = (
                    Path(directory) / names[0] if len(names) == 1 else Path(directory)
                )
                self._gh(
                    "run",
                    "download",
                    run.run_id,
                    "--repo",
                    self.repo,
                    "--dir",
                    str(destination),
                    *(arg for name in names for arg in ("--name", name)),
                )
                artifacts = {
                    name: {
                        path.name: path.read_text(encoding="utf-8")
                        for path in (Path(directory) / name).glob("*.json")
                    }
                    for name in names
                }
        store = IssueStore(self.repo, self._gh)
        store.ensure_labels()
        track(
            store,
            Nightly(int(run.run_id), run.sha, details["created_at"], run.url),
            evidence_from(artifacts),
        )

    def last_passing_sha(self, run: Run) -> str | None:
        """The commit of the latest passing Nightly run on main before this one."""
        runs = json.loads(
            self._gh(
                "run",
                "list",
                "--repo",
                self.repo,
                "--workflow",
                "nightly.yml",
                "--branch",
                "main",
                "--status",
                "success",
                "--limit",
                "5",
                "--json",
                "databaseId,headSha",
            )
        )
        return next(
            (r["headSha"] for r in runs if str(r["databaseId"]) != run.run_id), None
        )

    def open_issue(self, tracker: Tracker) -> int | None:
        """The open issue carrying the tracker's label, if there is one."""
        issues = json.loads(
            self._gh(
                "issue",
                "list",
                "--repo",
                self.repo,
                "--label",
                tracker.label,
                "--state",
                "open",
                "--limit",
                "1",
                "--json",
                "number",
            )
        )
        return issues[0]["number"] if issues else None

    def create_issue(self, tracker: Tracker, body: str) -> None:
        """Opens the tracker's issue, creating its label first if needed."""
        self._gh(
            "label",
            "create",
            tracker.label,
            "--repo",
            self.repo,
            "--force",
            "--color",
            tracker.color,
            "--description",
            tracker.description,
        )
        self._gh(
            "issue",
            "create",
            "--repo",
            self.repo,
            "--label",
            tracker.label,
            "--title",
            tracker.title,
            "--body",
            body,
        )

    def has_report(self, number: int, body: str) -> bool:
        """Whether this exact report is already in the issue or its comments.

        Re-running Nightly Report must not repeat a report. Distinct Nightly
        runs have different URLs, and still record each recurrence.
        """
        endpoint = f"repos/{self.repo}/issues/{number}"
        issue = json.loads(self._gh("api", endpoint))
        pages = json.loads(
            self._gh(
                "api", f"{endpoint}/comments?per_page=100", "--paginate", "--slurp"
            )
        )
        bodies = [issue["body"] or "", *(c["body"] for page in pages for c in page)]
        return any(previous.strip() == body.strip() for previous in bodies)

    def comment(self, number: int, body: str) -> None:
        """Comments on an issue."""
        self._gh("issue", "comment", str(number), "--repo", self.repo, "--body", body)

    def close(self, number: int, body: str) -> None:
        """Closes an issue with a comment."""
        self._gh("issue", "close", str(number), "--repo", self.repo, "--comment", body)


def main(argv: Sequence[str] | None = None) -> None:
    """Reports the run named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)
    run = Run(repo=args.repo, run_id=args.run_id, sha=args.sha)
    outcome = report(GhCli(args.repo), run)
    if not outcome.ran:
        print(f"The run skipped its checks: {run.sha[:7]} already passed.")
    else:
        print(f"Failed jobs: {len(outcome.failed)}; flaky tests: {len(outcome.flaky)}")


if __name__ == "__main__":
    main()
