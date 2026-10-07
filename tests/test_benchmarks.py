"""The benchmark harness: its statistics, its rounds, and its samples."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

from protostar.system import ProcessRunner
from scripts.benchmarks import __main__ as benchmarks
from scripts.benchmarks import probes
from scripts.benchmarks.scenarios import BY_NAME, SCENARIOS, Scenario
from scripts.benchmarks.stats import Verdict, compare, summarize


def test_a_summary_is_the_median_and_quartiles() -> None:
    summary = summarize([5.0, 1.0, 3.0, 2.0, 4.0])

    assert (summary.median, summary.low, summary.high, summary.count) == (3, 2, 4, 5)


def test_a_single_sample_summarizes_as_itself() -> None:
    summary = summarize([0.25])

    assert (summary.median, summary.low, summary.high) == (0.25, 0.25, 0.25)


@pytest.mark.parametrize(
    ("candidate", "verdict"),
    [
        ([0.90, 0.91, 0.89, 0.90, 0.92, 0.88, 0.90, 0.91], Verdict.FASTER),
        ([1.10, 1.11, 1.09, 1.10, 1.12, 1.08, 1.10, 1.11], Verdict.SLOWER),
        ([0.97, 1.04, 1.01, 0.96, 1.03, 0.99, 1.02, 0.98], Verdict.UNCHANGED),
    ],
)
def test_a_change_counts_only_when_its_interval_excludes_none(
    candidate: list[float], verdict: Verdict
) -> None:
    comparison = compare([1.0] * len(candidate), candidate)

    assert comparison.verdict is verdict
    assert comparison.low <= comparison.ratio <= comparison.high


def test_the_same_samples_give_the_same_interval() -> None:
    baseline = [1.0, 1.1, 0.9, 1.05, 0.95]
    candidate = [0.9, 1.0, 0.85, 0.95, 0.9]

    assert compare(baseline, candidate) == compare(baseline, candidate)


def test_a_comparison_needs_the_same_rounds_for_both() -> None:
    with pytest.raises(ValueError, match="same rounds"):
        compare([1.0, 1.0], [1.0])


def test_scenarios_are_named_or_matched_by_pattern_in_catalogue_order() -> None:
    chosen = benchmarks.select(["sync", "init-a*", "init-dry-run"], every=False)

    assert [scenario.name for scenario in chosen] == [
        "init-api",
        "init-astro",
        "init-dry-run",
        "sync",
    ]


def test_every_scenario_needs_asking_for() -> None:
    """Nothing runs by default: every scenario together takes several minutes."""
    with pytest.raises(benchmarks.BenchmarkError, match="--all"):
        benchmarks.select([], every=False)

    assert benchmarks.select([], every=True) == list(SCENARIOS)


def test_a_pattern_that_matches_nothing_is_an_error() -> None:
    with pytest.raises(benchmarks.BenchmarkError, match="No scenario matches 'snyc'"):
        benchmarks.select(["snyc"], every=False)


def test_versions_alternate_first_place_and_warm_up_online(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A machine that slows down mid-run slows both versions, not one."""
    calls: list[tuple[str, bool]] = []

    def take(
        version: benchmarks.Version,
        scenario: Scenario,
        project: Path,
        environment: dict[str, str],
    ) -> benchmarks.Sample:
        calls.append((version.label, environment.get("UV_OFFLINE") == "1"))
        return benchmarks.Sample(wall=float(len(calls)), cpu=0.0, commands=0.0)

    monkeypatch.setattr(benchmarks, "take", take)
    benches = [
        benchmarks.Bench(
            benchmarks.Version(label, Path(sys.executable)), tmp_path / label, tmp_path
        )
        for label in ("before", "after")
    ]

    before, after = benchmarks.measure(benches, BY_NAME["version"], runs=3, warmup=1)

    assert calls == [
        ("before", False),
        ("after", False),
        ("after", True),
        ("before", True),
        ("before", True),
        ("after", True),
        ("after", True),
        ("before", True),
    ]
    assert [sample.wall for sample in before] == [4, 5, 8]
    assert [sample.wall for sample in after] == [3, 6, 7]


def test_a_sample_runs_isolated_from_the_callers_caches_and_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/host/cache")
    monkeypatch.setenv("UV_OFFLINE", "1")
    bench = benchmarks.Bench(
        benchmarks.Version("v", Path(sys.executable)), tmp_path, tmp_path / "uv"
    )
    scenario = Scenario("editor", ("init",), environment=(("EXTRA", "1"),))

    online = bench.environment(scenario, offline=False)
    offline = bench.environment(scenario, offline=True)

    assert "XDG_CACHE_HOME" not in online
    assert "UV_OFFLINE" not in online
    assert offline["UV_OFFLINE"] == "1"
    assert online["HOME"] == str(tmp_path / "home")
    assert online["UV_CACHE_DIR"] == str(tmp_path / "uv")
    assert online["PROTOSTAR_OFFLINE_HOOK_REGISTRY"] == "1"
    assert online["PROTOSTAR_CONFIG"] == ""
    assert online["EXTRA"] == "1"


def test_only_commands_the_main_thread_waits_on_are_timed() -> None:
    """A command on another thread overlaps Protostar's own work, so it isn't taken out."""
    command = [sys.executable, "-c", "import time; time.sleep(0.2)"]

    with probes.time_commands() as clock:
        background = threading.Thread(target=ProcessRunner().run, args=(command,))
        background.start()
        background.join()
        assert clock.seconds == 0
        ProcessRunner().run(command)

    assert clock.seconds >= 0.2


def test_a_sample_times_the_command_in_a_fresh_interpreter(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    bench = benchmarks.Bench(
        benchmarks.Version("working tree", Path(sys.executable)),
        tmp_path,
        tmp_path / "uv",
    )
    scenario = BY_NAME["version"]

    sample = benchmarks.take(
        bench.version, scenario, project, bench.environment(scenario, offline=True)
    )

    assert sample.wall > 0
    assert sample.cpu > 0
    assert sample.commands == 0
    assert sample.protostar == sample.wall


def test_a_command_that_fails_is_not_timed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    bench = benchmarks.Bench(
        benchmarks.Version("working tree", Path(sys.executable)),
        tmp_path,
        tmp_path / "uv",
    )
    scenario = Scenario("broken", ("no-such-command",))

    with pytest.raises(benchmarks.BenchmarkError, match="can't be timed"):
        benchmarks.take(
            bench.version, scenario, project, bench.environment(scenario, offline=True)
        )


def test_naming_no_scenario_explains_and_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert benchmarks.main(["run"]) == 1

    assert "pass --all" in capsys.readouterr().err
