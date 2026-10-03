"""Contracts of selecting the dependency requests a run hands to the resolver."""

from dataclasses import replace
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.intent import DependencyGroup, ResolverFootprint
from protostar.manifest import (
    CollisionStrategy,
    DependencyManifest,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from protostar.merge import (
    ConflictReason,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
)
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import LiveWorkspace, ReviewWorkspace
from protostar.sync_state import (
    DependencyState,
    FilePolicy,
    FileState,
    encode_toml_baseline,
)

MAIN, DEV, DOCS = DependencyGroup.MAIN, DependencyGroup.DEV, DependencyGroup.DOCS
TARGET = "pyproject.toml"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


@pytest.fixture
def reconciliation(workspace):
    return Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )


def owned_state(group, name, declared, materialized=None):
    return DependencyState(TARGET, group, name, "", declared, materialized or declared)


def own(reconciliation, *records, files=()):
    reconciliation.candidate_state = replace(
        reconciliation.candidate_state, dependencies=records, files=files
    )


def deleted_ancestor(group, identity):
    return DiagnosticEvent(
        DiagnosticPhase.EXECUTOR,
        f"Kept your version of pyproject.toml at dependencies.{group.value}: "
        "it conflicts with the update.",
        Severity.WARNING,
        conflict=MergeConflict(
            MergeLocation(TARGET, ("dependencies", group.value), identity),
            ConflictReason.DELETED_ANCESTOR,
        ),
    )


def test_a_missing_project_file_is_read_as_no_requirements(tmp_path, workspace):
    # Execution reads the live disk, where reading a missing file fails.
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), LiveWorkspace(), workspace, workspace
    )
    reconciliation.manifest.dependencies.add("requests>=2")

    accepted, blocked = reconciliation._select_dependencies()

    assert accepted.dependencies == ["requests>=2"]
    assert blocked == set()


def test_the_accepted_requests_carry_the_resolver_footprint(reconciliation):
    footprint = ResolverFootprint(("pyproject.toml",))
    reconciliation.manifest.dependencies.add("requests>=2")
    reconciliation.manifest.dependencies.resolver_footprint = footprint

    accepted, _ = reconciliation._select_dependencies()

    assert accepted.resolver_footprint is footprint


def test_a_project_that_declares_nothing_selects_nothing(reconciliation):
    accepted, blocked = reconciliation._select_dependencies()

    assert accepted.dependencies == []
    assert accepted.dev_dependencies == []
    assert blocked == set()


def test_owned_requirements_in_a_deleted_project_file_are_kept_out(
    reconciliation, workspace
):
    # The records alone say Protostar tracked the file, and it is gone.
    own(reconciliation, owned_state(MAIN, "requests", "requests>=2"))
    reconciliation.manifest.dependencies.add("requests>=3")

    accepted, blocked = reconciliation._select_dependencies()

    assert accepted.dependencies == []
    assert blocked == {MAIN, DEV, DOCS}
    assert reconciliation.diagnostics == [deleted_ancestor(MAIN, "requests:")]


def test_a_tracked_project_file_that_is_gone_blocks_every_group(
    reconciliation, workspace
):
    own(
        reconciliation,
        files=(FileState(TARGET, FilePolicy.TOML, encode_toml_baseline({})),),
    )
    reconciliation.manifest.dependencies.add("requests>=3")
    reconciliation.manifest.dependencies.add_dev("pytest>=8")

    accepted, blocked = reconciliation._select_dependencies()

    assert (accepted.dependencies, accepted.dev_dependencies) == ([], [])
    assert blocked == {MAIN, DEV, DOCS}
    assert reconciliation.diagnostics == [
        deleted_ancestor(MAIN, "requests:"),
        deleted_ancestor(DEV, "pytest:"),
    ]


def test_a_requirement_already_owned_as_declared_raises_no_warning_in_a_deleted_file(
    reconciliation,
):
    own(
        reconciliation,
        owned_state(DEV, "pytest", "pytest>=8"),
        owned_state(DEV, "ruff", "ruff>=0.5"),
    )
    reconciliation.manifest.dependencies.add_dev("pytest>=8")
    reconciliation.manifest.dependencies.add_dev("mypy>=1")
    reconciliation.manifest.dependencies.add_dev("ruff>=0.5")

    reconciliation._select_dependencies()

    # The first is owned unchanged, so it is no news; the rest are.
    assert [e.conflict.location.identity for e in reconciliation.diagnostics] == [
        "mypy:"
    ]


def test_only_the_same_groups_record_makes_a_requirement_unchanged(reconciliation):
    own(reconciliation, owned_state(DOCS, "pytest", "pytest>=8"))
    reconciliation.manifest.dependencies.add_dev("pytest>=8")
    reconciliation.manifest.dependencies.add_docs("pytest>=8")

    reconciliation._select_dependencies()

    assert reconciliation.diagnostics == [deleted_ancestor(DEV, "pytest:")]


@pytest.mark.parametrize(
    ("group", "pyproject", "files"),
    [
        # Owned requirements, and the group is gone from the project.
        (DEV, '[project]\nname = "app"\n', ()),
        (DEV, '[project]\nname = "app"\n[dependency-groups]\ndocs = []\n', ()),
    ],
)
def test_an_owned_group_the_project_removed_is_kept_out(
    reconciliation, workspace, group, pyproject, files
):
    Path(TARGET).write_text(pyproject, encoding="utf-8", newline="")
    own(reconciliation, owned_state(DEV, "pytest", "pytest>=8"))
    reconciliation.manifest.dependencies.add_dev("pytest>=9")

    accepted, blocked = reconciliation._select_dependencies()

    assert accepted.dev_dependencies == []
    assert blocked == {DEV}


@pytest.mark.parametrize(
    ("baseline", "pyproject", "blocked"),
    [
        # The project table was owned and is gone.
        ({"project": {"name": "app"}}, "[tool.x]\ny = 1\n", {MAIN}),
        # The groups table was owned and is gone: only groups are blocked.
        (
            {"dependency-groups": {"dev": []}},
            "[project]\nname = 'app'\n",
            {DEV, DOCS},
        ),
    ],
)
def test_an_owned_table_the_project_removed_blocks_its_groups(
    reconciliation, workspace, baseline, pyproject, blocked
):
    Path(TARGET).write_text(pyproject, encoding="utf-8", newline="")
    own(
        reconciliation,
        files=(FileState(TARGET, FilePolicy.TOML, encode_toml_baseline(baseline)),),
    )
    reconciliation.manifest.dependencies.add("requests>=2")
    reconciliation.manifest.dependencies.add_dev("pytest>=8")

    _, kept_out = reconciliation._select_dependencies()

    assert kept_out == blocked


def test_an_owned_group_in_the_ownership_baseline_is_blocked_when_gone(
    reconciliation, workspace
):
    Path(TARGET).write_text(
        '[project]\nname = "app"\n[dependency-groups]\ndocs = []\n',
        encoding="utf-8",
        newline="",
    )
    own(
        reconciliation,
        files=(
            FileState(
                TARGET,
                FilePolicy.TOML,
                encode_toml_baseline({"dependency-groups": {"dev": [], "docs": []}}),
            ),
        ),
    )
    reconciliation.manifest.dependencies.add_dev("pytest>=8")
    reconciliation.manifest.dependencies.add_docs("zensical>=1")

    _, blocked = reconciliation._select_dependencies()

    assert blocked == {DEV}


def test_overwrite_selects_requirements_the_project_replaced(reconciliation, workspace):
    Path(TARGET).write_text(
        '[project]\nname = "app"\ndependencies = ["requests>=1"]\n',
        encoding="utf-8",
        newline="",
    )
    own(reconciliation, owned_state(MAIN, "requests", "requests>=2"))
    reconciliation.manifest.dependencies.add("requests>=3")
    reconciliation.manifest.collision_strategy = CollisionStrategy.OVERWRITE

    accepted, blocked = reconciliation._select_dependencies()

    assert accepted.dependencies == ["requests>=3"]
    assert blocked == set()


def test_a_merge_keeps_requirements_the_project_replaced_and_reports_them(
    reconciliation, workspace
):
    Path(TARGET).write_text(
        '[project]\nname = "app"\ndependencies = ["requests>=1"]\n',
        encoding="utf-8",
        newline="",
    )
    own(reconciliation, owned_state(MAIN, "requests", "requests>=2"))
    reconciliation.manifest.dependencies.add("requests>=3")

    accepted, _ = reconciliation._select_dependencies()

    assert accepted.dependencies == []
    assert [e.conflict.reason for e in reconciliation.diagnostics] == [
        ConflictReason.DIVERGED
    ]


def test_an_edit_kept_under_an_unchanged_update_is_reported_without_warning(
    reconciliation, workspace
):
    Path(TARGET).write_text(
        '[project]\nname = "app"\ndependencies = ["requests>=3"]\n',
        encoding="utf-8",
        newline="",
    )
    own(reconciliation, owned_state(MAIN, "requests", "requests>=2"))
    reconciliation.manifest.dependencies.add("requests>=2")

    reconciliation._select_dependencies()

    assert reconciliation.diagnostics == []
    assert [c.reason for c in reconciliation.preserved] == [ConflictReason.PRESERVED]


def test_a_kept_requirement_replaces_its_record_and_leaves_the_others(workspace):
    def fresh(resolutions=None):
        reconciliation = Reconciliation(
            EnvironmentManifest(),
            UserConfig(),
            workspace,
            workspace,
            workspace,
            resolutions=resolutions or {},
        )
        own(
            reconciliation,
            owned_state(MAIN, "requests", "requests>=2"),
            owned_state(MAIN, "click", "click>=8"),
        )
        reconciliation.manifest.dependencies.add("requests>=3")
        reconciliation.manifest.dependencies.add("click>=8")
        return reconciliation

    Path(TARGET).write_text(
        '[project]\nname = "app"\ndependencies = ["requests>=1", "click>=8"]\n',
        encoding="utf-8",
        newline="",
    )
    first = fresh()
    first._select_dependencies()
    [event] = first.diagnostics
    assert event.conflict.reason is ConflictReason.DIVERGED

    second = fresh({event.conflict.id: ResolutionChoice.LOCAL})
    second._select_dependencies()

    assert sorted(
        (r.name, r.declared, r.materialized)
        for r in second.candidate_state.dependencies
    ) == [
        ("click", "click>=8", "click>=8"),
        ("requests", "requests>=3", "requests>=1"),
    ]


def materialized_pyproject():
    Path(TARGET).write_text(
        '[project]\nname = "app"\ndependencies = ["requests>=3"]\n'
        '[dependency-groups]\ndev = ["pytest>=8", "ruff>=0.5"]\n',
        encoding="utf-8",
        newline="",
    )


def test_a_blocked_group_does_not_stop_the_groups_after_it(reconciliation, workspace):
    materialized_pyproject()
    own(reconciliation, owned_state(DEV, "pytest", "pytest>=7"))
    reconciliation.manifest.dependencies.add("requests>=3")
    reconciliation.manifest.dependencies.add_dev("pytest>=8")
    accepted, blocked = DependencyManifest(), {MAIN}

    reconciliation._materialize_dependencies(accepted, blocked)

    assert reconciliation.candidate_state.dependencies == (
        owned_state(DEV, "pytest", "pytest>=8"),
    )


def test_a_requirement_the_resolver_moved_updates_only_its_own_record(
    reconciliation, workspace
):
    materialized_pyproject()
    ruff = owned_state(DEV, "ruff", "ruff>=0.4", "ruff>=0.4")
    own(reconciliation, owned_state(DEV, "pytest", "pytest>=7"), ruff)
    reconciliation.manifest.dependencies.add_dev("pytest>=8")

    reconciliation._materialize_dependencies(DependencyManifest(), set())

    assert reconciliation.candidate_state.dependencies == (
        owned_state(DEV, "pytest", "pytest>=8"),
        ruff,
    )


def test_a_moved_requirement_records_what_the_file_now_holds(reconciliation, workspace):
    Path(TARGET).write_text(
        '[project]\nname = "app"\n[dependency-groups]\ndev = ["pytest >= 8"]\n',
        encoding="utf-8",
        newline="",
    )
    own(reconciliation, owned_state(DEV, "pytest", "pytest>=7"))
    reconciliation.manifest.dependencies.add_dev("pytest>=8")

    reconciliation._materialize_dependencies(DependencyManifest(), set())

    [record] = reconciliation.candidate_state.dependencies
    assert (record.declared, record.materialized) == ("pytest>=8", "pytest >= 8")


def test_releasing_undeclared_requirements_reads_a_missing_file_as_empty(workspace):
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), LiveWorkspace(), workspace, workspace
    )
    own(reconciliation, owned_state(MAIN, "requests", "requests>=2"))

    reconciliation._release_undeclared_dependencies()

    assert reconciliation.candidate_state.dependencies == ()
    assert workspace.contents == {}
