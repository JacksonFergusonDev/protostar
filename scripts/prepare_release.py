"""Verify release readiness and review refreshed inputs before a version bump."""

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, NoReturn

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import (
    SCRIPTS_DIR,
    CodeLanguage,
    OutputStyle,
    report,
    report_code,
    run_repo_cmd,
)
from scripts.nightly_matrix import rollback_matrix
from scripts.release_commits import RELEASE_INPUTS, workflow_commits

RUN_DISCOVERY_ATTEMPTS = 24
RUN_DISCOVERY_INTERVAL = 5


def prepare_inputs() -> bool:
    """Regenerate both inputs before checking for changes awaiting review."""
    report()
    report("Preparing release", style=OutputStyle.TITLE)
    report()
    for script in ("sync_registry_fallbacks.py", "sync_secret_rules.py"):
        # Separate processes let the rules generator import the refreshed pins.
        result = run_repo_cmd([sys.executable, str(SCRIPTS_DIR / script)])
        report()
        if result.returncode:
            report(
                "Version bump stopped: preparation failed.",
                style=OutputStyle.ERROR,
                stderr=True,
            )
            sys.exit(result.returncode)

    status = run_repo_cmd(
        ["git", "status", "--porcelain", "--", *RELEASE_INPUTS],
        capture_output=True,
    )
    if status.returncode:
        report(status.stderr.rstrip(), style=OutputStyle.ERROR, stderr=True)
        sys.exit(status.returncode)
    if status.stdout.strip():
        report("Review release inputs", style=OutputStyle.WARNING)
        diff = run_repo_cmd(
            [
                "git",
                "diff",
                "--no-ext-diff",
                "--no-color",
                "HEAD",
                "--",
                *RELEASE_INPUTS,
            ],
            capture_output=True,
        )
        if diff.returncode:
            report(diff.stderr.rstrip(), style=OutputStyle.ERROR, stderr=True)
            sys.exit(diff.returncode)
        if not diff.stdout.strip():
            report(
                "Version bump stopped: Git reports changes but no reviewable diff.",
                style=OutputStyle.ERROR,
                stderr=True,
            )
            sys.exit(1)
        report_code(diff.stdout.rstrip(), CodeLanguage.DIFF)
        report()
        if not sys.stdin.isatty():
            report(
                "Version bump stopped: release inputs need an interactive review.",
                style=OutputStyle.ERROR,
                stderr=True,
            )
            sys.exit(1)
        try:
            accepted = confirm(
                "Accept these changes, commit and push them, then continue?"
            )
        except KeyboardInterrupt:
            report()
            stop("release input review was cancelled.")
        if not accepted:
            stop("release inputs were not accepted.")

        for command in (
            ["git", "add", "--", *RELEASE_INPUTS],
            [
                "git",
                "commit",
                "--only",
                "-m",
                "chore(release): refresh generated release inputs",
                "--",
                *RELEASE_INPUTS,
            ],
            ["git", "push"],
        ):
            result = run_repo_cmd(command)
            if result.returncode:
                report(
                    "Version bump stopped: release input commit or push failed.",
                    style=OutputStyle.ERROR,
                    stderr=True,
                )
                sys.exit(result.returncode)
        report(
            "Release inputs committed and pushed. Verify this new commit before releasing.",
            style=OutputStyle.SUCCESS,
        )
        report()
        return True
    report("Release inputs are current and committed.", style=OutputStyle.SUCCESS)
    report()
    return False


def stop(message: str) -> NoReturn:
    """Stop before the bump with an actionable explanation."""
    report(f"Version bump stopped: {message}", style=OutputStyle.ERROR, stderr=True)
    sys.exit(1)


def read_command(command: list[str]) -> str:
    """Read a prerequisite, preserving command failures as failed preflight."""
    try:
        result = run_repo_cmd(command, capture_output=True)
    except OSError as error:
        stop(f"could not run {command[0]}: {error}")
    if result.returncode:
        report(result.stderr.rstrip(), style=OutputStyle.ERROR, stderr=True)
        stop(f"{' '.join(command)} failed. Check tool installation and authentication.")
    return result.stdout.strip()


def read_json(command: list[str]) -> Any:
    """Reject unreadable GitHub responses rather than continuing a release."""
    output = read_command(command)
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        stop(f"{command[0]} returned invalid JSON.")


def confirm(question: str) -> bool:
    """Ask before starting or waiting for remote work; redirected input declines."""
    if not sys.stdin.isatty():
        return False
    try:
        while True:
            report(f"{question} [y/N] ", end="")
            answer = input().strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"", "n", "no"}:
                return False
            report("Please answer y or n.")
    except EOFError:
        return False


def latest_run(repo: str, workflow: str, sha: str) -> dict[str, Any] | None:
    """Find the newest run for the pinned commit, including pending or failed runs."""
    runs = read_json(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--commit",
            sha,
            "--limit",
            "1",
            "--json",
            "databaseId,headSha,status,conclusion,url",
        ]
    )
    if not runs:
        return None
    run = runs[0]
    if run["headSha"] != sha:
        stop(f"{workflow} returned a run for a different commit.")
    return run


def require_source(repo: str, sha: str) -> None:
    """Do not continue or dispatch on a branch that moved while the user waited."""
    if check_checkout() != (repo, sha):
        stop(
            "the release source changed during preflight. Rerun your just bump command."
        )


def wait_for_workflow(
    repo: str,
    workflow: str,
    sha: str,
    run: dict[str, Any] | None,
    *,
    source_sha: str,
) -> dict[str, Any]:
    """With permission, discover a new run and watch its specific ID to completion."""
    label = "CI" if workflow == "ci.yml" else "Nightly"
    if not confirm(f"Wait for {label} to pass and automatically continue?"):
        stop(
            f"{label} must pass on {sha[:8]}. "
            "Wait for it, then rerun your just bump command."
        )
    require_source(repo, source_sha)
    if run is None:
        report(f"Waiting for GitHub to register {label} on {sha[:8]}...")
        for attempt in range(RUN_DISCOVERY_ATTEMPTS):
            run = latest_run(repo, workflow, sha)
            if run is not None:
                break
            if attempt + 1 < RUN_DISCOVERY_ATTEMPTS:
                time.sleep(RUN_DISCOVERY_INTERVAL)
        if run is None:
            stop(
                f"no {label} run appeared for {sha[:8]}. "
                f"Inspect gh run list --repo {repo} --workflow {workflow} --commit {sha}, "
                "then rerun your just bump command."
            )
    report(f"{label}: {run['url']}")
    if run["status"] != "completed":
        command = [
            "gh",
            "run",
            "watch",
            str(run["databaseId"]),
            "--repo",
            repo,
            "--exit-status",
            "--interval",
            "10",
        ]
        try:
            result = run_repo_cmd(command)
        except OSError as error:
            stop(f"could not watch {label}: {error}")
        if result.returncode:
            stop(
                f"{label} did not finish successfully, or watching failed. {run['url']}"
            )
        # Do not trust only the watch command's exit code, especially for skipped runs.
        run = read_json(
            [
                "gh",
                "run",
                "view",
                str(run["databaseId"]),
                "--repo",
                repo,
                "--json",
                "databaseId,headSha,status,conclusion,url",
            ]
        )
    require_source(repo, source_sha)
    return run


def check_workflows(repo: str, sha: str) -> None:
    """Check CI on HEAD and allow Nightly immediately before an input refresh."""
    for workflow, candidates in workflow_commits(sha).items():
        run = None
        run_sha = sha
        for candidate in candidates:
            if run := latest_run(repo, workflow, candidate):
                run_sha = candidate
                break
        if run_sha != sha:
            report(
                f"Using Nightly on {run_sha[:8]}, before the generated-input refresh."
            )
        if run is None:
            report(f"No {workflow} run exists for {sha[:8]}.", stderr=True)
            if workflow == "nightly.yml":
                if not confirm(f"Trigger full Nightly on main at {sha[:8]}?"):
                    stop(
                        f"run gh workflow run nightly.yml --repo {repo} --ref main, "
                        "then rerun your just bump command."
                    )
                require_source(repo, sha)
                output = read_command(
                    [
                        "gh",
                        "workflow",
                        "run",
                        "nightly.yml",
                        "--repo",
                        repo,
                        "--ref",
                        "main",
                        "-f",
                        "rollback-only=false",
                        "-f",
                        "os=all",
                        "-f",
                        "template=all",
                    ]
                )
                report(output or "Full Nightly requested on main.")
            else:
                report("CI starts automatically after a push to main.")
            run = wait_for_workflow(repo, workflow, sha, None, source_sha=sha)
        elif run["status"] != "completed":
            report(f"{workflow}: {run['status']}. {run['url']}")
            run = wait_for_workflow(repo, workflow, run_sha, run, source_sha=sha)
        if (
            run["headSha"] != run_sha
            or run["status"] != "completed"
            or run["conclusion"] != "success"
        ):
            stop(
                f"{workflow}: {run['status']} / {run['conclusion'] or 'pending'}. {run['url']}",
            )
        if workflow == "nightly.yml":
            jobs = read_json(
                [
                    "gh",
                    "run",
                    "view",
                    str(run["databaseId"]),
                    "--repo",
                    repo,
                    "--json",
                    "jobs",
                ]
            )["jobs"]
            passed = {job["name"] for job in jobs if job["conclusion"] == "success"}
            expected = {
                f"Rollback ({entry['os']} / {entry['template']}"
                + (f" {entry['slice']}" if entry["slice"] != "1/1" else "")
                + ")"
                for entry in rollback_matrix()["include"]
            }
            if not expected <= passed or not any(
                name.startswith("Platforms / Test on ") for name in passed
            ):
                report(
                    f"Nightly did not run the full platform and rollback suite. {run['url']}",
                    stderr=True,
                )
                report(
                    f"Run: gh workflow run nightly.yml --repo {repo} --ref main",
                    stderr=True,
                )
                stop("a full Nightly must pass before releasing.")
        report(
            f"{workflow} passed on {run_sha[:8]}: {run['url']}",
            style=OutputStyle.SUCCESS,
        )


def check_checkout() -> tuple[str, str]:
    """Validate the release branch and published source before refreshing inputs."""
    if read_command(["git", "branch", "--show-current"]) != "main":
        stop("releases must start from main.")
    if read_command(["git", "status", "--porcelain"]):
        stop("commit or stash all working tree changes before releasing.")
    sha = read_command(["git", "rev-parse", "HEAD"])
    remote = read_command(["git", "ls-remote", "origin", "refs/heads/main"])
    if not remote or remote.split()[0] != sha:
        stop("local HEAD differs from origin/main. Pull or push before releasing.")
    repo = read_command(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]
    )
    return repo, sha


def check_local_builds() -> None:
    """Validate temporary distribution artifacts and build docs in site/."""

    def check(command: list[str]) -> None:
        try:
            result = run_repo_cmd(command)
        except OSError as error:
            stop(f"could not run {command[0]}: {error}")
        if result.returncode:
            stop(f"{' '.join(command)} failed.")

    with tempfile.TemporaryDirectory(prefix="protostar-release-") as directory:
        dist = Path(directory) / "dist"
        check(["uv", "lock", "--check"])
        check(["uv", "build", "--out-dir", str(dist)])
        wheels = list(dist.glob("*.whl"))
        sources = list(dist.glob("*.tar.gz"))
        if not wheels or not sources:
            stop("the distribution build must produce both a wheel and source archive.")
        artifacts = sorted(str(path) for path in (*wheels, *sources))
        check(
            ["uv", "run", "--with", "twine", "twine", "check", "--strict", *artifacts]
        )
        check(
            [
                "uv",
                "run",
                "--locked",
                "--group",
                "docs",
                "zensical",
                "build",
                "--strict",
            ]
        )


def main() -> None:
    """Gate the bump on verified source and locally buildable release outputs."""
    try:
        repo, sha = check_checkout()
        if prepare_inputs():
            # CI covers the refresh; commit selection may reuse its parent's Nightly.
            repo, sha = check_checkout()
        check_workflows(repo, sha)
        require_source(repo, sha)
        check_local_builds()
        require_source(repo, sha)
    except KeyboardInterrupt:
        stop("preparation cancelled. Any workflows already started continue on GitHub.")
    report("Release preflight passed.", style=OutputStyle.SUCCESS)


if __name__ == "__main__":
    main()
