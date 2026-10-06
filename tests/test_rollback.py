"""Rollback under a fault at every site of a real init.

Each case seeds a project, fails ``protostar init`` at one write, directory,
or command (before, mid-way, or after it, with an error or an interrupt), and
requires the project and home directory to be exactly as they were. See
``rollback_harness.py`` for how sites are named and faults raised.

The sites each scenario passes are committed in ``tests/rollback_sites/``,
and the cases are generated from them. A change that adds, removes, or
reorders a site fails ``test_the_sites_match_the_recorded_list`` until the
list is regenerated with ``--snapshot-update``, so new sites show in review.

Pull requests (``--rollback-scope pr``, the default) check every scenario's
site list, raise an error after each site of one representative scenario, and
run its real commands once (``--rollback-real once``), off Windows, so their
test jobs stay within a few minutes. The full scope raises every fault in
every scenario; nightly also raises each around real commands
(``--rollback-real all``), one template per job (``--rollback-templates``).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests.rollback_harness import (
    POSITIONS,
    SCENARIOS,
    SITES_DIR,
    Case,
    Command,
    Fault,
    Outcome,
    Position,
    RollbackFault,
    Runner,
    Scenario,
    SiteKind,
    Tree,
    Workspace,
    cases,
    run,
    site_kind,
    site_target,
    unaccounted,
)

# The scenarios pull requests run: the richest seed (merges, proposals, kept
# modes, an unrelated tree) under the template with the most sites, and a sync
# that removes, adds, resolves, and reinstalls hooks. Real commands run once,
# for the first; faults around them, and the sync's, run nightly.
REPRESENTATIVE = Scenario("cli", "adopted")
REPRESENTATIVE_SYNC = Scenario("cli", "retooled", Command.SYNC)

# Sync installs missing hooks as a convenience: a failed install only warns.
HOOK_INSTALLS = frozenset({"uv run prek install", "uv run pre-commit install"})


def _full(config: pytest.Config) -> bool:
    return config.getoption("--rollback-scope") == "full"


def _scenarios(config: pytest.Config) -> tuple[Scenario, ...]:
    if not _full(config):
        return (REPRESENTATIVE, REPRESENTATIVE_SYNC)
    templates = {t for t in config.getoption("--rollback-templates").split(",") if t}
    unknown = templates - {scenario.template for scenario in SCENARIOS}
    if unknown:
        raise pytest.UsageError(f"--rollback-templates: unknown {sorted(unknown)}")
    return tuple(s for s in SCENARIOS if not templates or s.template in templates)


def _every_real(config: pytest.Config) -> bool:
    return config.getoption("--rollback-real") == "all"


def _one_per_site(scenario: Scenario) -> list[Case]:
    """The pull-request faults: an error after each write, directory, and command.

    That is the fault that proves a path was journaled before it changed. The
    commit takes an interrupt on either side, where the run either rolls back
    or stands. The other positions and faults run in the full scope, so a
    pull request's test jobs stay within a few minutes on every platform.
    """
    selected = []
    for site in scenario.recorded_sites():
        if site_kind(site) is SiteKind.COMMIT:
            selected += [
                Case(scenario, site, position, Fault.INTERRUPT)
                for position in POSITIONS[SiteKind.COMMIT]
            ]
        else:
            selected.append(Case(scenario, site, Position.AFTER, Fault.ERROR))
    return selected


def _real_cases(scenario: Scenario) -> list[Case]:
    """Every fault around real commands in one scenario.

    All but a command stopped mid-way, which only the fake can do at a known
    point. What a real `git init`, `uv add`, or hook install leaves on disk
    must roll back too.
    """
    return [
        case
        for case in cases(scenario)
        if not (
            site_kind(case.site) is SiteKind.COMMAND and case.position is Position.MID
        )
    ]


def _last_write(scenario: Scenario) -> Case:
    """An error after the last write: everything the run does is journaled."""
    writes = [s for s in scenario.recorded_sites() if site_kind(s) is SiteKind.WRITE]
    return Case(scenario, writes[-1], Position.AFTER, Fault.ERROR)


def _failed_restores(scenario: Scenario) -> list[tuple[Case, str]]:
    """Each path the run writes or creates, failing its restore in turn."""
    paths = dict.fromkeys(
        site_target(site)
        for site in scenario.recorded_sites()
        if site_kind(site) in (SiteKind.WRITE, SiteKind.MKDIR, SiteKind.REMOVE)
    )
    return [(_last_write(scenario), path) for path in paths]


def _commits(case: Case) -> bool:
    """Whether the run commits before the fault, so nothing rolls back."""
    return site_kind(case.site) is SiteKind.COMMIT and case.position is Position.AFTER


def _survives(case: Case) -> bool:
    """Whether the run outlives the fault: sync's hook install only warns."""
    return (
        case.scenario.command is Command.SYNC
        and case.fault is Fault.ERROR
        and site_kind(case.site) is SiteKind.COMMAND
        and site_target(case.site) in HOOK_INSTALLS
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    scenarios = _scenarios(metafunc.config)
    if "scenario" in metafunc.fixturenames:
        metafunc.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
    if "scoped_scenario" in metafunc.fixturenames:
        metafunc.parametrize("scoped_scenario", scenarios, ids=lambda s: s.name)
    full = _full(metafunc.config)
    if "failed_restore" in metafunc.fixturenames:
        # A pull request fails one restore per scenario; the full scope, each.
        restores = [
            pair
            for scenario in scenarios
            for pair in _failed_restores(scenario)[: None if full else 1]
        ]
        metafunc.parametrize(
            "failed_restore", restores, ids=lambda p: f"{p[0].scenario.name}:{p[1]}"
        )
    if "retried_case" in metafunc.fixturenames:
        # Every fault case already proves a rolled-back project is byte for
        # byte the seed, so running again matters once per scenario: after an
        # interrupt at the last write, when the most is rolled back, for state
        # a run keeps outside the files.
        selected = [
            Case(scenario, _last_write(scenario).site, Position.AFTER, Fault.INTERRUPT)
            for scenario in scenarios
        ]
        metafunc.parametrize("retried_case", selected, ids=lambda c: c.id)
    if "case" in metafunc.fixturenames:
        select = cases if full else _one_per_site
        selected = [case for scenario in scenarios for case in select(scenario)]
        metafunc.parametrize("case", selected, ids=lambda c: c.id)
    if "real_scenario" in metafunc.fixturenames:
        real = scenarios if _every_real(metafunc.config) else (REPRESENTATIVE,)
        metafunc.parametrize("real_scenario", real, ids=lambda s: s.name)
    if "real_case" in metafunc.fixturenames:
        # A real command takes a minute on Windows, so faults around real
        # commands run nightly only.
        selected = (
            [case for scenario in scenarios for case in _real_cases(scenario)]
            if _every_real(metafunc.config)
            else []
        )
        metafunc.parametrize("real_case", selected, ids=lambda c: c.id)


def _assert_handled(
    case: Case,
    outcome: Outcome,
    workspace: Workspace,
    before: tuple[Tree, Tree],
    clean: Callable[[], Workspace],
) -> None:
    """Checks a fault rolled the run back, or left the run whole.

    Args:
        case: The fault raised.
        outcome: How the run ended.
        workspace: The project it ran in.
        before: The project and home directory before it ran.
        clean: Runs the scenario without a fault, for a run that survives.
    """
    if _commits(case):
        _assert_committed(outcome, workspace, before)
    elif _survives(case):
        _assert_survived(outcome, workspace, clean())
    else:
        _assert_rolled_back(case, outcome, workspace, before)


def _assert_survived(outcome: Outcome, workspace: Workspace, clean: Workspace) -> None:
    """Checks a non-fatal failure warned and left what a clean run leaves.

    Only the hooks the failed install would have written may differ.
    """
    assert outcome.fired, "the run never reached the hook install"
    assert outcome.code == 0, outcome.payload
    assert "Could not install git hooks" in json.dumps(outcome.payload)
    expected, project = clean.capture()[0], workspace.capture()[0]
    differences = [
        path for path in expected.changed(project) if not path.startswith(".git/hooks/")
    ]
    assert not differences, "differs from a clean run:\n" + "\n".join(differences)


def _assert_committed(
    outcome: Outcome, workspace: Workspace, before: tuple[Tree, Tree]
) -> None:
    """Checks an interrupt after the commit kept every change and claimed no rollback."""
    assert outcome.fired, "the run never committed"
    assert outcome.code == 130
    # A plain interrupt: no payload says the run was rolled back.
    assert outcome.payload == {}
    assert outcome.committed is not None
    project, home = workspace.capture()
    _assert_unchanged("the committed project", outcome.committed, project)
    _assert_unchanged("the home directory", before[1], home)


def _assert_rolled_back(
    case: Case, outcome: Outcome, workspace: Workspace, before: tuple[Tree, Tree]
) -> None:
    """Checks a failed run left nothing behind and touched nothing it didn't journal."""
    assert outcome.fired, f"the run never reached {case.site}"
    if case.fault is Fault.INTERRUPT:
        assert outcome.code == 130, outcome.payload
    else:
        assert outcome.code not in (0, 130), outcome.payload
        # A domain error, rolled back: never a crash or a failed rollback.
        assert outcome.payload["error"]["type"] not in (
            "InternalError",
            "RollbackFailedError",
        ), outcome.payload

    project, home = workspace.capture()
    _assert_unchanged("the project", before[0], project)
    _assert_unchanged("the home directory", before[1], home)

    # A file the run never journaled was never rewritten either.
    journaled = {
        path.relative_to(workspace.project.resolve()).as_posix()
        for path in outcome.journaled
    }
    rewritten = sorted(
        path
        for path, identity in before[0].identities.items()
        if path not in journaled and project.identities.get(path) != identity
    )
    assert not rewritten, "rewritten outside the journal:\n" + "\n".join(rewritten)


def _assert_unchanged(name: str, before: Tree, after: Tree) -> None:
    differences = before.differences(after)
    assert not differences, f"{name} changed:\n" + "\n".join(differences)


def _assert_clean_run(
    outcome: Outcome, workspace: Workspace, before: tuple[Tree, Tree]
) -> None:
    """Checks a run succeeded, journaled every change, and left home alone."""
    assert outcome.code == 0, outcome.payload
    project, home = workspace.capture()
    root = workspace.project.resolve()
    paths = unaccounted(root, before[0], project, outcome.journaled)
    assert not paths, "changed without a journal entry:\n" + "\n".join(paths)
    _assert_unchanged("the home directory", before[1], home)


@pytest.fixture(scope="session")
def seed_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Initialized projects the sync scenarios start from, built once per worker."""
    return tmp_path_factory.mktemp("initialized")


@pytest.fixture
def seed(tmp_path: Path, seed_cache: Path) -> Callable[..., Workspace]:
    """Seeds a scenario's project under ``tmp_path`` (or a folder in it)."""

    def _seed(
        scenario: Scenario, runner: Runner = Runner.FAKE, under: str = ""
    ) -> Workspace:
        return Workspace.seed(tmp_path / under, scenario, runner, seed_cache)

    return _seed


# ------------------------------------------------------------ site lists -- #


def test_a_clean_run_passes_the_recorded_sites_and_journals_every_change(
    scenario: Scenario, monkeypatch, seed, request
):
    """The fault cases cover every site, and every change goes through one.

    A new site fails here until the list is regenerated, so it gets its
    cases; a file written around ``TransactionAwareFS`` would survive a
    rollback, so it fails here too, named.
    """
    workspace = seed(scenario)
    before = workspace.capture()
    outcome = run(workspace, scenario, Runner.FAKE, monkeypatch)
    _assert_clean_run(outcome, workspace, before)
    if request.config.getoption("--snapshot-update"):
        SITES_DIR.mkdir(exist_ok=True)
        scenario.sites_file.write_text("\n".join(outcome.sites) + "\n", "utf-8")
    assert outcome.sites == scenario.recorded_sites()


# ----------------------------------------------------------------- faults -- #


def test_rollback_restores_the_seed(case: Case, monkeypatch, seed):
    workspace = seed(case.scenario)
    before = workspace.capture()
    outcome = run(workspace, case.scenario, Runner.FAKE, monkeypatch, case)

    def clean() -> Workspace:
        reference = seed(case.scenario, under="clean")
        assert run(reference, case.scenario, Runner.FAKE, monkeypatch).code == 0
        return reference

    _assert_handled(case, outcome, workspace, before, clean)


def test_a_failed_restore_is_reported_and_everything_else_restored(
    failed_restore: tuple[Case, str], monkeypatch, seed
):
    """A path rollback can't restore is named; every other path still comes back.

    A created directory above that path can't be removed while the path is
    there, so it is reported too. Nothing else may differ from the seed.
    """
    case, path = failed_restore
    workspace = seed(case.scenario)
    before = workspace.capture()
    outcome = run(
        workspace,
        case.scenario,
        Runner.FAKE,
        monkeypatch,
        case,
        RollbackFault(path=path),
    )
    assert outcome.code == 1, outcome.payload
    error = outcome.payload["error"]
    assert error["type"] == "RollbackFailedError"
    root = workspace.project.resolve()
    unrestored = {
        Path(entry["path"]).relative_to(root).as_posix()
        for entry in error["unrestored"]
    }
    parts = path.split("/")
    allowed = {"/".join(parts[:i]) for i in range(1, len(parts) + 1)}
    assert path in unrestored
    assert unrestored <= allowed, unrestored
    changed = set(before[0].changed(workspace.capture()[0]))
    assert changed <= allowed, sorted(changed)


@pytest.mark.skipif(sys.platform == "win32", reason="Ctrl+C is a POSIX signal here")
def test_rollback_finishes_through_a_second_interrupt(
    scoped_scenario: Scenario, monkeypatch, seed
):
    """A Ctrl+C while rollback runs is held off until every path is restored."""
    case = _last_write(scoped_scenario)
    workspace = seed(scoped_scenario)
    before = workspace.capture()
    outcome = run(
        workspace,
        scoped_scenario,
        Runner.FAKE,
        monkeypatch,
        case,
        RollbackFault(interrupt=True),
    )
    _assert_rolled_back(case, outcome, workspace, before)


def test_a_rolled_back_run_succeeds_when_retried(retried_case: Case, monkeypatch, seed):
    """Rollback leaves a project init can start over in, not just one that looks right."""
    scenario = retried_case.scenario
    clean = seed(scenario, under="clean")
    assert run(clean, scenario, Runner.FAKE, monkeypatch).code == 0
    workspace = seed(scenario, under="retried")
    run(workspace, scenario, Runner.FAKE, monkeypatch, retried_case)
    retried = run(workspace, scenario, Runner.FAKE, monkeypatch)
    assert retried.code == 0, retried.payload
    _assert_unchanged("the retried project", clean.capture()[0], workspace.capture()[0])


# ---------------------------------------------------------- real commands -- #


@pytest.fixture(autouse=True)
def _drop_environments(tmp_path: Path) -> Iterator[None]:
    """Removes each run's uv environment once its test is done.

    pytest keeps every test's directory until the session ends. Where uv
    can't link packages from its cache (Windows), it copies them, and a few
    hundred kept environments fill the runner's disk.
    """
    yield
    for environment in tmp_path.rglob(".venv"):
        shutil.rmtree(environment, ignore_errors=True)


@pytest.fixture
def real_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_tool_env: Callable[[], dict[str, str]],
) -> None:
    """Runs commands for real, with the shared uv cache and a stand-in direnv.

    direnv records its trust outside the project, and whether it is installed
    changes the sites; the stand-in keeps them the same on every host.
    """
    environment = real_tool_env()
    for name in ("VIRTUAL_ENV", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "PRE_COMMIT_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UV_CACHE_DIR", environment["UV_CACHE_DIR"])
    tools = tmp_path / "bin"
    tools.mkdir()
    if sys.platform == "win32":
        (tools / "direnv.cmd").write_text("@exit /b 0\r\n", encoding="utf-8")
    else:
        direnv = tools / "direnv"
        direnv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        direnv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")


@pytest.mark.integration
@pytest.mark.usefixtures("real_commands")
def test_real_commands_pass_the_recorded_sites(
    real_scenario: Scenario, monkeypatch, seed, request
):
    """The fake runner stands in faithfully: real commands pass the same sites."""
    if sys.platform == "win32" and not _every_real(request.config):
        pytest.skip("A real init takes a minute on Windows; nightly runs it there.")
    scenario = real_scenario
    workspace = seed(scenario, Runner.REAL)
    before = workspace.capture()
    outcome = run(workspace, scenario, Runner.REAL, monkeypatch)
    _assert_clean_run(outcome, workspace, before)
    assert outcome.sites == scenario.recorded_sites()


@pytest.mark.integration
@pytest.mark.usefixtures("real_commands")
def test_real_commands_roll_back(real_case: Case, monkeypatch, seed):
    workspace = seed(real_case.scenario, Runner.REAL)
    before = workspace.capture()
    outcome = run(workspace, real_case.scenario, Runner.REAL, monkeypatch, real_case)

    def clean() -> Workspace:
        reference = seed(real_case.scenario, Runner.REAL, under="clean")
        assert run(reference, real_case.scenario, Runner.REAL, monkeypatch).code == 0
        return reference

    _assert_handled(real_case, outcome, workspace, before, clean)
