"""Times Protostar's commands, or compares the working tree with another version.

    uv run python -m scripts.benchmarks list
    uv run python -m scripts.benchmarks run SCENARIO... [--runs N]
    uv run python -m scripts.benchmarks compare REF SCENARIO... [--runs N]
    uv run python -m scripts.benchmarks profile SCENARIO [--text]

``just bench``, ``just bench-compare``, and ``just bench-profile`` run these.
A scenario is one of ``scenarios.SCENARIOS``, or a pattern such as ``init-*``.

Each sample is one run of the scenario's command in a fresh interpreter
(``sample.py``), in an isolated home directory and project, with configuration
off and the hook registry offline. A warm-up round runs first and fills uv's
cache; the measured rounds run uv offline from it, so the network never enters
a timing. A sample records the whole process's duration, the CPU time
Protostar's own process used, and the time it waited on commands; what remains
of the duration once commands are taken out is Protostar's.

``compare`` checks ``REF`` out into a temporary worktree with its own locked
environment, and alternates the two versions round by round, each going first
in turn, so a machine that slows down slows both.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts._common import REPO_ROOT, OutputStyle, fixture_environment, report
from scripts.benchmarks.scenarios import BY_NAME, SCENARIOS, Scenario, Start
from scripts.benchmarks.stats import Comparison, Summary, compare, summarize

SAMPLE = Path(__file__).with_name("sample.py")
RESULTS = REPO_ROOT / ".benchmarks"

# Variables that would point a sample's tools at the caller's own caches or
# configuration instead of the isolated home directory.
_HOST_LOCATIONS = (
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "PRE_COMMIT_HOME",
    "PREK_HOME",
    "UV_OFFLINE",
)


class BenchmarkError(Exception):
    """A benchmark that can't run, or whose command failed."""


@dataclass(frozen=True)
class Version:
    """A version of Protostar and the interpreter that has it installed.

    Attributes:
        label: How results name it: ``working tree``, or the ref compared.
        python: The interpreter whose environment holds this version.
    """

    label: str
    python: Path


@dataclass(frozen=True)
class Sample:
    """One timed run of a command.

    Attributes:
        wall: The whole process's duration, from start to exit, in seconds.
        cpu: The CPU time Protostar's own process used, in seconds.
        commands: The time the main thread waited on commands, in seconds.
    """

    wall: float
    cpu: float
    commands: float

    @property
    def protostar(self) -> float:
        """The run's duration with the commands it waited on taken out."""
        return max(self.wall - self.commands, 0.0)


METRICS = ("wall", "protostar", "cpu", "commands")


def _value(sample: Sample, metric: str) -> float:
    value: float = getattr(sample, metric)
    return value


@dataclass
class Bench:
    """Where one version's samples run: its home directory and projects.

    Attributes:
        version: The version that runs here.
        root: A scratch directory of its own.
        cache: uv's cache, shared with the host so packages download once.
        initialized: The ``lib`` project the ``initialized`` scenarios run in,
            once this version has created it.
    """

    version: Version
    root: Path
    cache: Path
    initialized: Path | None = None
    _projects: int = field(default=0)

    @property
    def home(self) -> Path:
        """The home directory every sample of this version shares."""
        home = self.root / "home"
        home.mkdir(parents=True, exist_ok=True)
        return home

    def environment(self, scenario: Scenario, *, offline: bool) -> dict[str, str]:
        """The variables a sample of ``scenario`` runs with."""
        environment = {
            name: value
            for name, value in fixture_environment().items()
            if name not in _HOST_LOCATIONS
        }
        environment.update(
            HOME=str(self.home),
            USERPROFILE=str(self.home),
            UV_CACHE_DIR=str(self.cache),
            # Fallback pins: no network, and the same files on every run.
            PROTOSTAR_OFFLINE_HOOK_REGISTRY="1",
        )
        if offline:
            environment["UV_OFFLINE"] = "1"
        environment.update(dict(scenario.environment))
        return environment

    def project(self, scenario: Scenario) -> Path:
        """The project a sample of ``scenario`` runs in.

        An empty project is new for every sample; the initialized one is
        created once and shared, since its scenarios change nothing.
        """
        if scenario.start is Start.INITIALIZED:
            if self.initialized is None:
                self.initialized = self._initialize()
            return self.initialized
        self._projects += 1
        project = self.root / "projects" / str(self._projects) / "project"
        project.mkdir(parents=True)
        return project

    def discard(self, scenario: Scenario, project: Path) -> None:
        """Removes a sample's project once timed, unless it is shared."""
        if scenario.start is Start.EMPTY:
            shutil.rmtree(project.parent, ignore_errors=True)

    def _initialize(self) -> Path:
        project = self.root / "initialized" / "project"
        project.mkdir(parents=True)
        initialize = BY_NAME["init-lib"]
        take(
            self.version,
            initialize,
            project,
            self.environment(initialize, offline=False),
        )
        # A project with something to update would change under its first
        # sample, and the rest would time something else.
        check = BY_NAME["sync-check"]
        try:
            take(self.version, check, project, self.environment(check, offline=True))
        except BenchmarkError as error:
            raise BenchmarkError(
                f"The project {self.version.label} initialized still has updates "
                f"pending, so the initialized scenarios can't be timed.\n{error}"
            ) from error
        return project


def take(
    version: Version, scenario: Scenario, project: Path, environment: dict[str, str]
) -> Sample:
    """Runs a scenario's command once and returns what it took.

    Args:
        version: The version to run.
        scenario: The command.
        project: The directory it runs in.
        environment: The variables it runs with.

    Returns:
        The sample.

    Raises:
        BenchmarkError: If the command crashed or exited with an error.
    """
    output = project.parent / "sample.json"
    command = [
        str(version.python),
        str(SAMPLE),
        json.dumps(list(scenario.argv)),
        str(output),
        str(REPO_ROOT),
    ]
    started = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=project,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    wall = time.perf_counter() - started
    if process.returncode != 0 or not output.exists():
        raise BenchmarkError(
            f"`protostar {' '.join(scenario.argv)}` crashed under "
            f"{version.label}:\n{process.stderr[-4000:]}"
        )
    result = json.loads(output.read_text(encoding="utf-8"))
    output.unlink()
    if result["exit"] != 0:
        raise BenchmarkError(
            f"`protostar {' '.join(scenario.argv)}` exited {result['exit']} under "
            f"{version.label}, so it can't be timed:\n{process.stderr[-4000:]}"
        )
    return Sample(wall, float(result["cpu"]), float(result["commands"]))


def measure(
    benches: Sequence[Bench], scenario: Scenario, *, runs: int, warmup: int
) -> list[list[Sample]]:
    """Times a scenario under each version, in alternating rounds.

    Args:
        benches: The versions, each in its own scratch directory.
        scenario: The command.
        runs: How many measured rounds.
        warmup: How many rounds to run first and discard; they fill uv's cache.

    Returns:
        Each version's samples, in round order.
    """
    samples: list[list[Sample]] = [[] for _ in benches]
    for round_ in range(warmup + runs):
        order = list(range(len(benches)))
        if round_ % 2:
            order.reverse()
        measured = round_ >= warmup
        for index in order:
            bench = benches[index]
            project = bench.project(scenario)
            sample = take(
                bench.version,
                scenario,
                project,
                bench.environment(scenario, offline=measured),
            )
            bench.discard(scenario, project)
            if measured:
                samples[index].append(sample)
        report(".", style=OutputStyle.DETAIL, stderr=True, end="")
    report(stderr=True)
    return samples


def select(patterns: Sequence[str], *, every: bool) -> list[Scenario]:
    """Returns the scenarios a command line names.

    Args:
        patterns: Scenario names, or shell-style patterns such as ``init-*``.
        every: Whether ``--all`` was given.

    Returns:
        The scenarios, in catalogue order.

    Raises:
        BenchmarkError: If nothing was named, or a pattern matches nothing.
    """
    names = ", ".join(scenario.name for scenario in SCENARIOS)
    if every:
        return list(SCENARIOS)
    if not patterns:
        raise BenchmarkError(
            "Name the scenarios to time, or pass --all to time every one "
            f"(several minutes). Scenarios: {names}"
        )
    chosen: set[str] = set()
    for pattern in patterns:
        matched = {s.name for s in SCENARIOS if fnmatch.fnmatchcase(s.name, pattern)}
        if not matched:
            raise BenchmarkError(f"No scenario matches {pattern!r}. Scenarios: {names}")
        chosen |= matched
    return [scenario for scenario in SCENARIOS if scenario.name in chosen]


def host_cache() -> Path:
    """Returns uv's cache directory as the caller's own environment sets it."""
    process = subprocess.run(
        ["uv", "cache", "dir"], capture_output=True, text=True, check=True
    )
    return Path(process.stdout.strip())


@contextlib.contextmanager
def checked_out(ref: str, root: Path) -> Iterator[Version]:
    """Checks ``ref`` out into a temporary worktree with its own environment.

    Args:
        ref: A commit, branch, or tag.
        root: Where the worktree goes.

    Yields:
        The version, with the interpreter of its locked environment.

    Raises:
        BenchmarkError: If the ref can't be checked out or installed.
    """
    worktree = root / "checkout"
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), ref],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise BenchmarkError(f"Can't check out {ref!r}:\n{error.stderr}") from error
    try:
        try:
            # Its own locked dependencies, so each version runs as it shipped.
            subprocess.run(
                ["uv", "sync", "--locked", "--no-dev"],
                cwd=worktree,
                env=fixture_environment(),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            raise BenchmarkError(f"Can't install {ref!r}:\n{error.stderr}") from error
        scripts = "Scripts" if sys.platform == "win32" else "bin"
        executable = "python.exe" if sys.platform == "win32" else "python"
        yield Version(ref, worktree / ".venv" / scripts / executable)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )


def _seconds(value: float) -> str:
    return f"{value:.3f}s"


def _spread(summary: Summary) -> str:
    return f"{_seconds(summary.median)} ({summary.low:.3f}-{summary.high:.3f})"


def _change(comparison: Comparison) -> str:
    return (
        f"{comparison.ratio - 1:+.1%} "
        f"[{comparison.low - 1:+.1%}, {comparison.high - 1:+.1%}] "
        f"{comparison.verdict}"
    )


def _table(rows: list[list[str]]) -> None:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    for row in rows:
        report(
            "  ".join(
                cell.ljust(width) for cell, width in zip(row, widths, strict=True)
            ).rstrip()
        )


def _machine() -> dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    )
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
        "commit": commit,
        "uncommitted_changes": dirty,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _write(results: dict[str, object], path: Path | None) -> None:
    destination = path or RESULTS / "latest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report(f"Samples written to {destination}", style=OutputStyle.DETAIL)


def run(
    scenarios: list[Scenario], *, runs: int, warmup: int, output: Path | None
) -> None:
    """Times each scenario under the working tree and reports its spread."""
    version = Version("working tree", Path(sys.executable))
    report(
        f"Timing {len(scenarios)} scenario(s) with the working tree: "
        f"{runs} runs each after {warmup} warm-up.",
        style=OutputStyle.TITLE,
    )
    rows = [["scenario", "wall", "protostar", "cpu", "commands"]]
    recorded: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="protostar-bench-") as scratch:
        bench = Bench(version, Path(scratch), host_cache())
        for scenario in scenarios:
            report(scenario.name, style=OutputStyle.DETAIL, stderr=True, end=" ")
            (samples,) = measure([bench], scenario, runs=runs, warmup=warmup)
            rows.append(
                [scenario.name]
                + [_spread(summarize([_value(s, m) for s in samples])) for m in METRICS]
            )
            recorded[scenario.name] = {
                metric: [_value(s, metric) for s in samples] for metric in METRICS
            }
    _table(rows)
    _write(
        {"machine": _machine(), "mode": "run", "runs": runs, "samples": recorded},
        output,
    )


def compare_versions(
    ref: str, scenarios: list[Scenario], *, runs: int, warmup: int, output: Path | None
) -> None:
    """Compares the working tree with ``ref``, scenario by scenario."""
    report(
        f"Comparing the working tree with {ref}: {runs} alternating rounds per "
        f"scenario after {warmup} warm-up.",
        style=OutputStyle.TITLE,
    )
    rows = [
        [
            "scenario",
            f"{ref} wall",
            "working tree wall",
            "wall change",
            "protostar change",
        ]
    ]
    recorded: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="protostar-bench-") as scratch:
        root = Path(scratch)
        cache = host_cache()
        with checked_out(ref, root / "baseline") as baseline:
            benches = [
                Bench(baseline, root / "baseline", cache),
                Bench(
                    Version("working tree", Path(sys.executable)),
                    root / "candidate",
                    cache,
                ),
            ]
            for scenario in scenarios:
                report(scenario.name, style=OutputStyle.DETAIL, stderr=True, end=" ")
                before, after = measure(benches, scenario, runs=runs, warmup=warmup)
                rows.append(
                    [
                        scenario.name,
                        _seconds(summarize([s.wall for s in before]).median),
                        _seconds(summarize([s.wall for s in after]).median),
                        _change(
                            compare([s.wall for s in before], [s.wall for s in after])
                        ),
                        _change(
                            compare(
                                [s.protostar for s in before],
                                [s.protostar for s in after],
                            )
                        ),
                    ]
                )
                recorded[scenario.name] = {
                    side: {
                        metric: [_value(s, metric) for s in samples]
                        for metric in METRICS
                    }
                    for side, samples in (("baseline", before), ("candidate", after))
                }
    _table(rows)
    report(
        "A change reads faster or slower only when its 95% interval excludes "
        "zero; anything else is within the noise.",
        style=OutputStyle.DETAIL,
    )
    _write(
        {
            "machine": _machine(),
            "mode": "compare",
            "baseline": ref,
            "runs": runs,
            "samples": recorded,
        },
        output,
    )


def profile(scenario: Scenario, *, text: bool, output: Path | None) -> None:
    """Profiles one run of a scenario under the working tree with pyinstrument."""
    version = Version("working tree", Path(sys.executable))
    destination = (
        output or RESULTS / f"profile-{scenario.name}.{'txt' if text else 'html'}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="protostar-bench-") as scratch:
        bench = Bench(version, Path(scratch), host_cache())
        # A warm-up fills uv's cache, so the profile shows no download.
        warm = bench.project(scenario)
        take(version, scenario, warm, bench.environment(scenario, offline=False))
        bench.discard(scenario, warm)
        project = bench.project(scenario)
        process = subprocess.run(
            [
                str(version.python),
                "-m",
                "pyinstrument",
                "--renderer",
                "text" if text else "html",
                "--outfile",
                str(destination),
                str(SAMPLE),
                json.dumps(list(scenario.argv)),
                str(project.parent / "sample.json"),
                str(REPO_ROOT),
            ],
            cwd=project,
            env=bench.environment(scenario, offline=True),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
    if process.returncode != 0:
        raise BenchmarkError(
            f"Profiling {scenario.name} failed:\n{process.stderr[-4000:]}"
        )
    if text:
        report(destination.read_text(encoding="utf-8"))
    report(f"Profile written to {destination}", style=OutputStyle.DETAIL)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.benchmarks",
        description="Time Protostar's commands, or compare the working tree with another version.",
    )
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("list", help="List the scenarios.")
    for name, summary in (
        ("run", "Time scenarios under the working tree."),
        ("compare", "Compare the working tree with another version."),
    ):
        action = actions.add_parser(name, help=summary)
        if name == "compare":
            action.add_argument(
                "ref", help="The version to compare with: a commit, branch, or tag."
            )
        action.add_argument(
            "scenarios", nargs="*", help="Scenario names or patterns, such as init-*."
        )
        action.add_argument("--all", action="store_true", help="Time every scenario.")
        action.add_argument(
            "--runs", type=_positive, default=10, help="Measured rounds (default 10)."
        )
        action.add_argument(
            "--warmup",
            type=_positive,
            default=1,
            help="Discarded rounds first (default 1).",
        )
        action.add_argument("--json", type=Path, help="Where to write the samples.")
    profiled = actions.add_parser(
        "profile", help="Profile one scenario with pyinstrument."
    )
    profiled.add_argument("scenario", choices=sorted(BY_NAME))
    profiled.add_argument("--text", action="store_true", help="Print a text profile.")
    profiled.add_argument("--output", type=Path, help="Where to write the profile.")
    return parser


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the benchmark command a command line names.

    Args:
        argv: The arguments; the process's own when None.

    Returns:
        The exit code.
    """
    arguments = _parser().parse_args(argv)
    try:
        if arguments.action == "list":
            for scenario in SCENARIOS:
                report(f"{scenario.name:<14} protostar {' '.join(scenario.argv)}")
        elif arguments.action == "profile":
            profile(
                BY_NAME[arguments.scenario],
                text=arguments.text,
                output=arguments.output,
            )
        else:
            scenarios = select(arguments.scenarios, every=arguments.all)
            if arguments.action == "run":
                run(
                    scenarios,
                    runs=arguments.runs,
                    warmup=arguments.warmup,
                    output=arguments.json,
                )
            else:
                compare_versions(
                    arguments.ref,
                    scenarios,
                    runs=arguments.runs,
                    warmup=arguments.warmup,
                    output=arguments.json,
                )
    except BenchmarkError as error:
        report(str(error), style=OutputStyle.ERROR, stderr=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
