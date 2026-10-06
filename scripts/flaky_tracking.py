"""Track one issue per flaky test and verify fixes from explicit nightly evidence.

Issue bodies hold a small managed block; the awaiting-verification label's
latest event anchors a fix. No clean result is inferred from silence, a retry,
or the outcome of an entire job. Issue history survives migration and closure.
"""

from __future__ import annotations

import base64
import json
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

LABEL = "flaky-test"
AWAITING = "awaiting-verification"
PASSES_REQUIRED = 3
START = "<!-- protostar-flake:start -->"
END = "<!-- protostar-flake:end -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
STATE = re.compile(r"<!-- state:([A-Za-z0-9+/=]+) -->")
LEGACY_TITLE = "Flaky tests in the nightly run"


class Result(StrEnum):
    """A test's evidence, in order from least to most concerning."""

    SKIPPED = "skipped"
    PASSED = "passed"
    FLAKY = "flaky"
    FAILED = "failed"


Evidence = dict[str, dict[str, Result]]


def evidence_from(artifacts: Mapping[str, Mapping[str, str]]) -> Evidence:
    """Combine separate first/retry attempts and shards without losing failures."""
    evidence: Evidence = {}
    rank = list(Result)
    for files in artifacts.values():
        if "first.json" not in files:
            continue
        first = json.loads(files["first.json"])
        retry = json.loads(files["retry.json"]) if "retry.json" in files else None
        if retry is not None and retry["platform"] != first["platform"]:
            raise SystemExit("Retry evidence names a different platform.")
        platform = first["platform"]
        for test, value in first["tests"].items():
            result = Result(value)
            if result is Result.FAILED and retry is not None:
                if retry["tests"].get(test) == Result.PASSED:
                    result = Result.FLAKY
            previous = evidence.setdefault(test, {}).get(platform, Result.SKIPPED)
            evidence[test][platform] = max((previous, result), key=rank.index)
    return evidence


@dataclass(frozen=True)
class Flake:
    """Durable verification state stored in an issue's managed body block."""

    test: str
    platforms: tuple[str, ...]
    clean_runs: tuple[int, ...] = ()
    verification_since: str | None = None
    last_run: int = 0


def decode(body: str) -> Flake | None:
    """Read state from a tracker issue; leave unrelated issues alone."""
    block = BLOCK.search(body)
    match = STATE.search(block.group()) if block else None
    if match is None:
        return None
    data = json.loads(base64.b64decode(match[1], validate=True))
    return Flake(
        test=data["test"],
        platforms=tuple(data["platforms"]),
        clean_runs=tuple(data["clean_runs"]),
        verification_since=data["verification_since"],
        last_run=data["last_run"],
    )


def body_for(flake: Flake, body: str = "") -> str:
    """Replace only the managed block, preserving the user's notes."""
    state = base64.b64encode(
        json.dumps(asdict(flake), sort_keys=True).encode()
    ).decode()
    block = "\n".join(
        [
            START,
            f"<!-- state:{state} -->",
            f"Test: `{flake.test}`",
            "",
            f"Affected platforms: {', '.join(flake.platforms)}.",
            "",
            f"Verified clean nightly runs: **{len(flake.clean_runs)}/{PASSES_REQUIRED}**.",
            "",
            "After the fix lands on main, add `awaiting-verification` and link the fix.",
            "Three distinct later runs must pass this test on every affected platform without retrying.",
            "Skipped or missing results do not count. A recurrence resets verification and reopens the issue.",
            END,
        ]
    )
    return (
        BLOCK.sub(lambda _: block, body)
        if BLOCK.search(body)
        else body.rstrip() + "\n\n" + block + "\n"
    )


@dataclass(frozen=True)
class Issue:
    """One issue and its verification label's most recent addition."""

    number: int
    title: str
    body: str
    closed: bool = False
    awaiting_since: str | None = None


@dataclass(frozen=True)
class Nightly:
    """The originating run, with the time it was created (not retried)."""

    number: int
    sha: str
    created_at: str
    url: str


class Store(Protocol):
    """The small issue interface the tracker needs."""

    def issues(self) -> list[Issue]: ...
    def comments(self, number: int) -> list[str]: ...
    def create(self, flake: Flake, body: str) -> Issue: ...
    def update(self, number: int, body: str) -> None: ...
    def comment_once(self, number: int, body: str) -> None: ...
    def reopen(self, number: int) -> None: ...
    def close(self, number: int) -> None: ...
    def remove_awaiting(self, number: int) -> None: ...


def _legacy_tests(text: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for test, platforms in re.findall(
        r"^- `([^`]+)` \(([^\n]+)\)$", text, re.MULTILINE
    ):
        for name in platforms.split(", "):
            match = re.fullmatch(
                r"(?:rollback-)?(ubuntu-latest|macos-latest|windows-latest)(?:-py(3\.\d+)|-[a-z]+-\d+)",
                name,
            )
            if match:
                system = {
                    "ubuntu-latest": "linux",
                    "macos-latest": "macos",
                    "windows-latest": "windows",
                }[match[1]]
                found.setdefault(test, set()).add(f"{system}-py{match[2] or '3.14'}")
    return found


def recurrence_body(run: Nightly, failures: set[str]) -> str:
    """Describe an occurrence once, whether it opens an issue or comments."""
    return f"Failed or needed a retry at `{run.sha[:7]}` ([run]({run.url})) on {', '.join(sorted(failures))}. Verification reset; this test needs a fix."


def track(store: Store, run: Nightly, evidence: Evidence) -> None:
    """Migrate aggregate issues, report recurrences, and verify each fixed test."""
    issues = store.issues()
    created: set[str] = set()
    tracked = {
        flake.test: (issue, flake)
        for issue in issues
        if (flake := decode(issue.body)) is not None
    }
    for aggregate in issues:
        if (
            aggregate.closed
            or aggregate.title != LEGACY_TITLE
            or decode(aggregate.body)
        ):
            continue
        imported = _legacy_tests(
            "\n".join([aggregate.body, *store.comments(aggregate.number)])
        )
        if not imported:
            continue
        numbers = []
        for test, platforms in sorted(imported.items()):
            if test not in tracked:
                flake = Flake(test, tuple(sorted(platforms)))
                issue = store.create(
                    flake,
                    body_for(
                        flake,
                        f"Imported from #{aggregate.number}; its reports remain there as history.",
                    ),
                )
                tracked[test] = issue, flake
            else:
                issue, flake = tracked[test]
                flake = replace(
                    flake, platforms=tuple(sorted(set(flake.platforms) | platforms))
                )
                store.update(issue.number, body_for(flake, issue.body))
                tracked[test] = replace(issue, body=body_for(flake, issue.body)), flake
            numbers.append(f"#{tracked[test][0].number}")
        store.comment_once(
            aggregate.number,
            "Tracking has moved to individual test issues: "
            + ", ".join(numbers)
            + ". This aggregate is closed because tracking moved; the tests are not yet verified fixed.",
        )
        store.close(aggregate.number)

    for test, observed in sorted(evidence.items()):
        flaky = tuple(
            sorted(p for p, result in observed.items() if result is Result.FLAKY)
        )
        if flaky and test not in tracked:
            flake = Flake(test, flaky, last_run=run.number)
            issue = store.create(
                flake, body_for(flake, recurrence_body(run, set(flaky)))
            )
            tracked[test] = issue, flake
            created.add(test)

    for test, (issue, flake) in sorted(tracked.items()):
        if test in created or run.number < flake.last_run:
            continue
        if issue.awaiting_since is not None:
            if run.created_at <= issue.awaiting_since:
                continue
            if flake.verification_since != issue.awaiting_since:
                flake = replace(
                    flake, clean_runs=(), verification_since=issue.awaiting_since
                )
        results = evidence.get(test, {})
        failures = {
            p
            for p, result in results.items()
            if result in (Result.FLAKY, Result.FAILED)
        }
        if failures:
            updated = replace(
                flake,
                platforms=tuple(sorted(set(flake.platforms) | failures)),
                clean_runs=(),
                verification_since=None,
                last_run=run.number,
            )
            store.update(issue.number, body_for(updated, issue.body))
            if issue.closed:
                store.reopen(issue.number)
            if issue.awaiting_since:
                store.remove_awaiting(issue.number)
            store.comment_once(issue.number, recurrence_body(run, failures))
            continue
        # Finish a close even if a previous reporter failed after persisting
        # its third pass but before changing the issue's state or labels.
        if len(flake.clean_runs) >= PASSES_REQUIRED:
            if issue.awaiting_since:
                store.remove_awaiting(issue.number)
            if not issue.closed:
                store.close(issue.number)
            continue
        if run.number == flake.last_run:
            continue
        if issue.closed or issue.awaiting_since is None:
            continue
        if not flake.platforms or not all(
            results.get(p) is Result.PASSED for p in flake.platforms
        ):
            continue
        updated = replace(
            flake, clean_runs=(*flake.clean_runs, run.number), last_run=run.number
        )
        store.comment_once(
            issue.number,
            f"Clean verification **{len(updated.clean_runs)}/{PASSES_REQUIRED}** at `{run.sha[:7]}` ([run]({run.url})): `{test}` passed on every affected platform without a retry.",
        )
        store.update(issue.number, body_for(updated, issue.body))
        if len(updated.clean_runs) >= PASSES_REQUIRED:
            store.remove_awaiting(issue.number)
            store.close(issue.number)


class IssueStore:
    """GitHub issue operations through the report's authenticated gh client."""

    def __init__(self, repo: str, gh: Callable[..., str]) -> None:
        self.repo, self.gh = repo, gh

    def _pages(self, endpoint: str) -> list[dict[str, Any]]:
        pages = json.loads(self.gh("api", endpoint, "--paginate", "--slurp"))
        return [item for page in pages for item in page]

    def _write(
        self, endpoint: str, data: dict[str, Any], method: str = "PATCH"
    ) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return json.loads(
                self.gh("api", endpoint, "--method", method, "--input", str(path))
            )

    def ensure_labels(self) -> None:
        """Make the tracker and agent verification labels available."""
        for name, color, description in (
            (LABEL, "fbca04", "Tests that passed only when retried"),
            (AWAITING, "1d76db", "Fix landed; waiting for three clean nightly runs"),
        ):
            self.gh(
                "label",
                "create",
                name,
                "--repo",
                self.repo,
                "--force",
                "--color",
                color,
                "--description",
                description,
            )

    def issues(self) -> list[Issue]:
        """All open and closed flaky-test issues, including verification events."""
        result = []
        for item in self._pages(
            f"repos/{self.repo}/issues?state=all&labels={LABEL}&per_page=100"
        ):
            if "pull_request" in item:
                continue
            since = None
            if AWAITING in {label["name"] for label in item["labels"]}:
                for event in self._pages(
                    f"repos/{self.repo}/issues/{item['number']}/events?per_page=100"
                ):
                    if (
                        event["event"] == "labeled"
                        and event["label"]["name"] == AWAITING
                    ):
                        since = event["created_at"]
            result.append(
                Issue(
                    item["number"],
                    item["title"],
                    item["body"] or "",
                    item["state"] == "closed",
                    since,
                )
            )
        return result

    def comments(self, number: int) -> list[str]:
        """Read every comment, including historical aggregate reports."""
        return [
            item["body"]
            for item in self._pages(
                f"repos/{self.repo}/issues/{number}/comments?per_page=100"
            )
        ]

    def create(self, flake: Flake, body: str) -> Issue:
        """Create a separately identifiable issue for one test."""
        item = self._write(
            f"repos/{self.repo}/issues",
            {
                "title": f"Flaky test: {flake.test}"[:256],
                "body": body,
                "labels": [LABEL],
            },
            "POST",
        )
        return Issue(item["number"], item["title"], body)

    def update(self, number: int, body: str) -> None:
        """Update the managed body block."""
        self._write(f"repos/{self.repo}/issues/{number}", {"body": body})

    def comment_once(self, number: int, body: str) -> None:
        """Keep reruns from duplicating lifecycle comments."""
        issue = json.loads(self.gh("api", f"repos/{self.repo}/issues/{number}"))
        if body not in (issue["body"] or "") and body not in self.comments(number):
            self._write(
                f"repos/{self.repo}/issues/{number}/comments", {"body": body}, "POST"
            )

    def reopen(self, number: int) -> None:
        """Reopen a resolved test when it recurs."""
        self._write(f"repos/{self.repo}/issues/{number}", {"state": "open"})

    def close(self, number: int) -> None:
        """Close the issue while preserving all its history."""
        self._write(f"repos/{self.repo}/issues/{number}", {"state": "closed"})

    def remove_awaiting(self, number: int) -> None:
        """Return a recurrence to work needing a fix, or finish verification."""
        self.gh(
            "api",
            f"repos/{self.repo}/issues/{number}/labels/{AWAITING}",
            "--method",
            "DELETE",
        )
