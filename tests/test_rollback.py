"""Rollback under a fault at every site of a real init.

Each case seeds a project, fails ``protostar init`` at one write, directory,
or command (before, mid-way, or after it, with an error or an interrupt), and
requires the project and home directory to be exactly as they were. See
``rollback_harness.py`` for how sites are named and faults raised.

The sites each scenario passes are committed in ``tests/rollback_sites/``,
and the cases are generated from them. A change that adds, removes, or
reorders a site fails ``test_the_sites_match_the_recorded_list`` until the
list is regenerated with ``--snapshot-update``, so new sites show in review.

Pull requests run one representative scenario (``--rollback-scope pr``, the
default), with real commands only around an error after each one. Nightly runs
every template and seed (``--rollback-scope full``) and raises every fault
around real commands too (``--rollback-real all``), one template per job
(``--rollback-templates``).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.rollback_harness import (
    SCENARIOS,
    SITES_DIR,
    Case,
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
    init,
    site_kind,
    site_target,
    unaccounted,
)

# The scenario pull requests run: the richest seed (merges, proposals, kept
# modes, an unrelated tree) under the template with the most sites.
REPRESENTATIVE = Scenario("cli", "adopted")


def _scenarios(config: pytest.Config) -> tuple[Scenario, ...]:
    if config.getoption("--rollback-scope") == "pr":
        return (REPRESENTATIVE,)
    templates = {t for t in config.getoption("--rollback-templates").split(",") if t}
    unknown = templates - {scenario.template for scenario in SCENARIOS}
    if unknown:
        raise pytest.UsageError(f"--rollback-templates: unknown {sorted(unknown)}")
    return tuple(s for s in SCENARIOS if not templates or s.template in templates)


def _real_cases(scenario: Scenario, every: bool) -> list[Case]:
    """The faults raised around real commands in one scenario.

    Every case but a command stopped mid-way, which only the fake can do at a
    known point; or, by default, an error after each command and an
    interrupt after the last. Those are where real commands differ from the
    fake: what a real `git init`, `uv add`, or hook install leaves on disk
    must roll back too.
    """
    if every:
        return [
            case
            for case in cases(scenario)
            if not (
                site_kind(case.site) is SiteKind.COMMAND
                and case.position is Position.MID
            )
        ]
    commands = [
        site
        for site in scenario.recorded_sites()
        if site_kind(site) is SiteKind.COMMAND
    ]
    selected = [Case(scenario, site, Position.AFTER, Fault.ERROR) for site in commands]
    if commands:
        selected.append(Case(scenario, commands[-1], Position.AFTER, Fault.INTERRUPT))
    return selected


def _last_write(scenario: Scenario) -> Case:
    """An error after the last write: everything the run does is journaled."""
    writes = [s for s in scenario.recorded_sites() if site_kind(s) is SiteKind.WRITE]
    return Case(scenario, writes[-1], Position.AFTER, Fault.ERROR)


def _failed_restores(scenario: Scenario) -> list[tuple[Case, str]]:
    """Each path the run writes or creates, failing its restore in turn."""
    paths = dict.fromkeys(
        site_target(site)
        for site in scenario.recorded_sites()
        if site_kind(site) in (SiteKind.WRITE, SiteKind.MKDIR)
    )
    return [(_last_write(scenario), path) for path in paths]


def _commits(case: Case) -> bool:
    """Whether the run commits before the fault, so nothing rolls back."""
    return site_kind(case.site) is SiteKind.COMMIT and case.position is Position.AFTER


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    scenarios = _scenarios(metafunc.config)
    if "scenario" in metafunc.fixturenames:
        metafunc.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
    if "scoped_scenario" in metafunc.fixturenames:
        metafunc.parametrize("scoped_scenario", scenarios, ids=lambda s: s.name)
    if "failed_restore" in metafunc.fixturenames:
        restores = [
            pair for scenario in scenarios for pair in _failed_restores(scenario)
        ]
        metafunc.parametrize(
            "failed_restore", restores, ids=lambda p: f"{p[0].scenario.name}:{p[1]}"
        )
    if "retried_case" in metafunc.fixturenames:
        selected = [
            case
            for scenario in scenarios
            for case in cases(scenario)
            if case.position is Position.AFTER
            and case.fault is Fault.INTERRUPT
            and not _commits(case)
        ]
        metafunc.parametrize("retried_case", selected, ids=lambda c: c.id)
    if "case" in metafunc.fixturenames:
        selected = [case for scenario in scenarios for case in cases(scenario)]
        metafunc.parametrize("case", selected, ids=lambda c: c.id)
    if "real_scenario" in metafunc.fixturenames:
        metafunc.parametrize("real_scenario", scenarios, ids=lambda s: s.name)
    if "real_case" in metafunc.fixturenames:
        every = metafunc.config.getoption("--rollback-real") == "all"
        selected = [
            case for scenario in scenarios for case in _real_cases(scenario, every)
        ]
        metafunc.parametrize("real_case", selected, ids=lambda c: c.id)


def _assert_handled(
    case: Case, outcome: Outcome, workspace: Workspace, before: tuple[Tree, Tree]
) -> None:
    """Checks a fault rolled the run back, or left a committed run whole."""
    if _commits(case):
        _assert_committed(outcome, workspace, before)
    else:
        _assert_rolled_back(case, outcome, workspace, before)


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


# ------------------------------------------------------------ site lists -- #


def test_the_sites_match_the_recorded_list(
    scenario: Scenario, tmp_path, monkeypatch, capsys, request
):
    workspace = Workspace.seed(tmp_path, scenario)
    outcome = init(workspace, scenario, Runner.FAKE, monkeypatch, capsys)
    assert outcome.code == 0, outcome.payload
    if request.config.getoption("--snapshot-update"):
        SITES_DIR.mkdir(exist_ok=True)
        scenario.sites_file.write_text("\n".join(outcome.sites) + "\n", "utf-8")
    assert outcome.sites == scenario.recorded_sites()


def test_a_clean_run_journals_every_path_it_changes(
    scenario: Scenario, tmp_path, monkeypatch, capsys
):
    """Every write goes through the seams the fault cases cover.

    A file written around ``TransactionAwareFS`` would survive a rollback;
    this fails first, naming it.
    """
    workspace = Workspace.seed(tmp_path, scenario)
    before = workspace.capture()
    outcome = init(workspace, scenario, Runner.FAKE, monkeypatch, capsys)
    _assert_clean_run(outcome, workspace, before)


# ----------------------------------------------------------------- faults -- #


def test_rollback_restores_the_seed(case: Case, tmp_path, monkeypatch, capsys):
    workspace = Workspace.seed(tmp_path, case.scenario)
    before = workspace.capture()
    outcome = init(workspace, case.scenario, Runner.FAKE, monkeypatch, capsys, case)
    _assert_handled(case, outcome, workspace, before)


def test_a_failed_restore_is_reported_and_everything_else_restored(
    failed_restore: tuple[Case, str], tmp_path, monkeypatch, capsys
):
    """A path rollback can't restore is named; every other path still comes back.

    A created directory above that path can't be removed while the path is
    there, so it is reported too. Nothing else may differ from the seed.
    """
    case, path = failed_restore
    workspace = Workspace.seed(tmp_path, case.scenario)
    before = workspace.capture()
    outcome = init(
        workspace,
        case.scenario,
        Runner.FAKE,
        monkeypatch,
        capsys,
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
    scoped_scenario: Scenario, tmp_path, monkeypatch, capsys
):
    """A Ctrl+C while rollback runs is held off until every path is restored."""
    case = _last_write(scoped_scenario)
    workspace = Workspace.seed(tmp_path, scoped_scenario)
    before = workspace.capture()
    outcome = init(
        workspace,
        scoped_scenario,
        Runner.FAKE,
        monkeypatch,
        capsys,
        case,
        RollbackFault(interrupt=True),
    )
    _assert_rolled_back(case, outcome, workspace, before)


def test_a_rolled_back_run_succeeds_when_retried(
    retried_case: Case, tmp_path, monkeypatch, capsys
):
    """Rollback leaves a project init can start over in, not just one that looks right."""
    scenario = retried_case.scenario
    clean = Workspace.seed(tmp_path / "clean", scenario)
    assert init(clean, scenario, Runner.FAKE, monkeypatch, capsys).code == 0
    workspace = Workspace.seed(tmp_path / "retried", scenario)
    init(workspace, scenario, Runner.FAKE, monkeypatch, capsys, retried_case)
    retried = init(workspace, scenario, Runner.FAKE, monkeypatch, capsys)
    assert retried.code == 0, retried.payload
    _assert_unchanged("the retried project", clean.capture()[0], workspace.capture()[0])


# ---------------------------------------------------------- real commands -- #


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
    real_scenario: Scenario, tmp_path, monkeypatch, capsys
):
    """The fake runner stands in faithfully: real commands pass the same sites."""
    scenario = real_scenario
    workspace = Workspace.seed(tmp_path, scenario)
    before = workspace.capture()
    outcome = init(workspace, scenario, Runner.REAL, monkeypatch, capsys)
    _assert_clean_run(outcome, workspace, before)
    assert outcome.sites == scenario.recorded_sites()


@pytest.mark.integration
@pytest.mark.usefixtures("real_commands")
def test_real_commands_roll_back(real_case: Case, tmp_path, monkeypatch, capsys):
    workspace = Workspace.seed(tmp_path, real_case.scenario)
    before = workspace.capture()
    outcome = init(
        workspace, real_case.scenario, Runner.REAL, monkeypatch, capsys, real_case
    )
    _assert_handled(real_case, outcome, workspace, before)
