from dataclasses import replace

import pytest

from protostar.dependencies import (
    DependencyGroup,
    _upgrades,
    install_dependencies,
    other_requirement_groups,
    preserved_requirement,
    requirement_entries,
    requirement_identity,
    resolver_commands,
    retract_requirements,
    select_dependencies,
)
from protostar.errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ConfigurationError,
)
from protostar.manifest import DependencyManifest
from protostar.merge import (
    MISSING,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
    Value,
)
from protostar.sync_state import DependencyState
from protostar.system import ProcessRunner


def test_install_dependencies_uv(mocker):
    """Dependency groups are installed with their explicit uv arguments."""
    runner = mocker.MagicMock(spec=ProcessRunner)

    install_dependencies(
        DependencyManifest(
            dependencies=["fastapi"],
            dev_dependencies=["pytest"],
            docs_dependencies=["mkdocs"],
        ),
        runner,
    )

    assert runner.run.call_args_list == [
        mocker.call(["uv", "add", "--no-sync", "fastapi"], timeout=600),
        mocker.call(["uv", "add", "--no-sync", "--dev", "pytest"], timeout=600),
        mocker.call(["uv", "add", "--group", "docs", "mkdocs"], timeout=600),
    ]


@pytest.mark.parametrize(
    ("manifest", "commands"),
    [
        (
            DependencyManifest(dev_dependencies=["pytest"]),
            [("uv", "add", "--dev", "pytest")],
        ),
        (
            DependencyManifest(dependencies=["fastapi"], docs_dependencies=["mkdocs"]),
            [
                ("uv", "add", "--no-sync", "fastapi"),
                ("uv", "add", "--group", "docs", "mkdocs"),
            ],
        ),
        (
            DependencyManifest(dependencies=["fastapi"], dev_dependencies=["pytest"]),
            [
                ("uv", "add", "--no-sync", "fastapi"),
                ("uv", "add", "--dev", "pytest"),
            ],
        ),
    ],
    ids=["one-group", "skips-empty-groups", "main-and-dev"],
)
def test_only_the_last_add_installs_into_the_environment(manifest, commands):
    """Each add locks, but the last one alone updates the environment.

    A lone add keeps its default sync, and a group with no requests is not
    counted when choosing which add is last.
    """
    assert resolver_commands(manifest) == tuple(commands)


def test_install_dependencies_brackets_each_group_in_a_step(mocker, progress):
    """Each uv add runs inside its own step, labelled with its group and count."""
    runner = mocker.MagicMock(spec=ProcessRunner)
    runner.run.side_effect = lambda command, **_: progress.events.append(
        ("run", command[-1])
    )

    install_dependencies(
        DependencyManifest(
            dependencies=["fastapi"],
            dev_dependencies=["pytest", "ruff"],
            docs_dependencies=["mkdocs"],
        ),
        runner,
        progress,
    )

    assert progress.events == [
        ("start", "Installing 1 standard dependency"),
        ("run", "fastapi"),
        ("done", "Installing 1 standard dependency"),
        ("start", "Installing 2 development dependencies"),
        ("run", "ruff"),
        ("done", "Installing 2 development dependencies"),
        ("start", "Installing 1 documentation dependency"),
        ("run", "mkdocs"),
        ("done", "Installing 1 documentation dependency"),
    ]


def test_install_dependencies_marks_the_failing_group(mocker, progress):
    """A failed group ends its step as failed and starts no later group."""
    runner = mocker.MagicMock(spec=ProcessRunner)
    runner.run.side_effect = CommandExecutionError(
        command=["uv", "add", "invalid"], returncode=1, stderr="not found"
    )

    with pytest.raises(CommandExecutionError):
        install_dependencies(
            DependencyManifest(dependencies=["invalid"], dev_dependencies=["pytest"]),
            runner,
            progress,
        )

    assert progress.events == [
        ("start", "Installing 1 standard dependency"),
        ("fail", "Installing 1 standard dependency"),
    ]


def test_install_dependencies_empty(mocker):
    """An empty dependency manifest does not start a process."""
    runner = mocker.MagicMock(spec=ProcessRunner)

    install_dependencies(DependencyManifest(), runner)

    runner.run.assert_not_called()


def test_install_dependencies_command_failure_is_fatal(mocker):
    """A failed dependency group aborts installation immediately."""
    runner = mocker.MagicMock(spec=ProcessRunner)
    error = CommandExecutionError(
        command=["uv", "add", "invalid"], returncode=1, stderr="not found"
    )
    runner.run.side_effect = error

    with pytest.raises(CommandExecutionError) as exc_info:
        install_dependencies(
            DependencyManifest(dependencies=["invalid"], dev_dependencies=["pytest"]),
            runner,
        )

    assert exc_info.value is error
    runner.run.assert_called_once_with(
        ["uv", "add", "--no-sync", "invalid"], timeout=600
    )


def test_install_dependencies_timeout_is_fatal(mocker):
    """A dependency timeout aborts installation immediately."""
    runner = mocker.MagicMock(spec=ProcessRunner)
    runner.run.side_effect = CommandTimeoutError(
        command=["uv", "add", "large"], timeout=600
    )

    with pytest.raises(CommandTimeoutError):
        install_dependencies(
            DependencyManifest(dependencies=["large"]),
            runner,
        )


def test_dependency_group_properties():
    assert DependencyGroup.MAIN.cli_args == []
    assert DependencyGroup.MAIN.label == "standard"
    assert DependencyGroup.DEV.cli_args == ["--dev"]
    assert DependencyGroup.DEV.label == "development"
    assert DependencyGroup.DOCS.cli_args == ["--group", "docs"]
    assert DependencyGroup.DOCS.label == "documentation"


def owned(
    name="pytest",
    declared="pytest",
    materialized="pytest>=9",
    *,
    group=DependencyGroup.DEV,
    marker="",
):
    return DependencyState(
        "pyproject.toml", group, name, marker, declared, materialized
    )


def where(name, group=DependencyGroup.DEV, marker=""):
    return MergeLocation(
        "pyproject.toml", ("dependencies", group.value), f"{name}:{marker}"
    )


def edited(record, local):
    found = preserved_requirement(record, local)
    assert found is not None
    return found


def choose(conflict, choice):
    return {conflict.id: choice}


def select(desired, local, records=(), group=DependencyGroup.DEV, **kwargs):
    return select_dependencies(desired, local, tuple(records), group, **kwargs)


def test_invalid_requirements_fail_with_a_hint():
    with pytest.raises(ConfigurationError) as caught:
        requirement_identity("not a requirement !!!")

    assert str(caught.value) == "Invalid dependency requirement."
    assert caught.value.hint == "Use a valid PEP 508 requirement."


def test_requirement_entries_read_the_group_they_are_asked_for():
    data = {
        "project": {"dependencies": ["httpx", {"x": 1}]},
        "dependency-groups": {"dev": ["pytest"], "docs": ["zensical"]},
    }

    assert requirement_entries(data, DependencyGroup.MAIN) == ["httpx"]
    assert requirement_entries(data, DependencyGroup.DEV) == ["pytest"]
    assert requirement_entries(data, DependencyGroup.DOCS) == ["zensical"]
    assert requirement_entries({}, DependencyGroup.DEV) == []


@pytest.mark.parametrize(
    ("data", "group", "message", "hint"),
    [
        (
            {"project": "text"},
            DependencyGroup.MAIN,
            "Invalid dependency table.",
            "Use TOML tables for project and dependency-groups.",
        ),
        (
            {"dependency-groups": ["dev"]},
            DependencyGroup.DEV,
            "Invalid dependency table.",
            "Use TOML tables for project and dependency-groups.",
        ),
        (
            {"project": {"dependencies": "httpx"}},
            DependencyGroup.MAIN,
            "Invalid dependency group.",
            "Use arrays of requirements and include-group records.",
        ),
        (
            {"dependency-groups": {"dev": "pytest"}},
            DependencyGroup.DEV,
            "Invalid dependency group.",
            "Use arrays of requirements and include-group records.",
        ),
    ],
)
def test_requirement_entries_reject_the_wrong_shape(data, group, message, hint):
    with pytest.raises(ConfigurationError) as caught:
        requirement_entries(data, group)

    assert str(caught.value) == message
    assert caught.value.hint == hint


DATA = {
    "project": {
        "dependencies": ["httpx", {"include-group": "x"}],
        "optional-dependencies": {"dev": ["extra-dev"], "cli": ["click"]},
    },
    "dependency-groups": {
        "dev": ["pytest", {"include-group": "docs"}],
        "docs": ["zensical"],
        "custom": ["rich"],
    },
}


def test_other_groups_leave_out_the_destination_and_name_the_rest():
    assert other_requirement_groups(DATA, DependencyGroup.DEV) == {
        "project.dependencies": ["httpx"],
        "dependency-groups.docs": ["zensical"],
        "dependency-groups.custom": ["rich"],
        "project.optional-dependencies.dev": ["extra-dev"],
        "project.optional-dependencies.cli": ["click"],
    }
    assert other_requirement_groups(DATA, DependencyGroup.DOCS) == {
        "project.dependencies": ["httpx"],
        "dependency-groups.dev": ["pytest"],
        "dependency-groups.custom": ["rich"],
        "project.optional-dependencies.dev": ["extra-dev"],
        "project.optional-dependencies.cli": ["click"],
    }


def test_other_groups_of_the_main_destination_list_every_group():
    assert other_requirement_groups(DATA, DependencyGroup.MAIN) == {
        "dependency-groups.dev": ["pytest"],
        "dependency-groups.docs": ["zensical"],
        "dependency-groups.custom": ["rich"],
        "project.optional-dependencies.dev": ["extra-dev"],
        "project.optional-dependencies.cli": ["click"],
    }
    assert other_requirement_groups({}, DependencyGroup.MAIN) == {}


def test_other_groups_tolerate_a_project_that_is_not_a_table():
    assert other_requirement_groups({"project": "text"}, DependencyGroup.MAIN) == {}


@pytest.mark.parametrize(
    ("data", "message", "hint"),
    [
        (
            {"dependency-groups": ["dev"]},
            "Invalid dependency table.",
            "Use TOML tables for dependency groups and optional dependencies.",
        ),
        (
            {"project": {"optional-dependencies": ["cli"]}},
            "Invalid dependency table.",
            "Use TOML tables for dependency groups and optional dependencies.",
        ),
        (
            {"dependency-groups": {"custom": "rich"}},
            "Invalid dependency group.",
            "Use arrays of requirements and include-group records.",
        ),
        (
            {"project": {"optional-dependencies": {"cli": "click"}}},
            "Invalid dependency group.",
            "Use arrays of requirements and include-group records.",
        ),
    ],
)
def test_other_groups_reject_the_wrong_shape(data, message, hint):
    with pytest.raises(ConfigurationError) as caught:
        other_requirement_groups(data, DependencyGroup.DEV)

    assert str(caught.value) == message
    assert caught.value.hint == hint


def test_several_requests_or_entries_for_one_identity_wait_for_a_hand():
    selection = select(
        ["a", "a>=2", "b", "c", "zzz"], ["b>=1", "b>=2", "c"], overwrite=False
    )

    assert selection.conflicts == (
        MergeConflict(where("a"), ConflictReason.DIVERGED),
        MergeConflict(where("b"), ConflictReason.DIVERGED),
    )
    assert selection.packages == ("zzz",)


def test_overwrite_takes_each_differing_request_and_goes_on():
    selection = select(
        ["same", "changed>=2", "new", "zzz"],
        ["same", "changed>=1"],
        overwrite=True,
    )

    assert selection.packages == ("changed>=2", "new", "zzz")
    assert selection.conflicts == ()


def test_an_untouched_owned_requirement_is_left_alone():
    selection = select(["pytest", "zzz"], ["pytest>=9"], [owned()], proposing=True)

    assert selection.packages == ("zzz",)
    assert [p.location.identity for p in selection.proposals] == ["zzz:"]
    assert selection.conflicts == selection.preserved == selection.records == ()


def test_a_local_edit_under_an_unchanged_request_is_preserved_until_chosen():
    record = owned()
    preserved = edited(record, ["pytest>=10"])

    selection = select(["pytest", "zzz"], ["pytest>=10"], [record])

    assert selection.preserved == (preserved,)
    assert selection.resolved == ()
    assert selection.packages == ("zzz",)


def test_taking_the_update_restores_a_preserved_requirement():
    record = owned()
    preserved = edited(record, ["pytest>=10"])

    selection = select(
        ["pytest", "zzz"],
        ["pytest>=10"],
        [record],
        resolutions=choose(preserved, ResolutionChoice.DESIRED),
    )

    assert selection.resolved == (
        replace(preserved, resolution=ResolutionChoice.DESIRED),
    )
    assert selection.preserved == ()
    assert selection.packages == ("pytest", "zzz")


def test_keeping_a_preserved_requirement_settles_without_installing():
    record = owned()
    preserved = edited(record, ["pytest>=10"])

    selection = select(
        ["pytest", "zzz"],
        ["pytest>=10"],
        [record],
        resolutions=choose(preserved, ResolutionChoice.LOCAL),
    )

    assert selection.resolved == (
        replace(preserved, resolution=ResolutionChoice.LOCAL),
    )
    assert selection.packages == ("zzz",)


def test_a_requirement_the_file_already_lists_is_not_requested_again():
    selection = select(
        ["PyTest>=9", "zzz"], ["pytest>=9"], [owned(declared="pytest>=8")]
    )

    assert selection.packages == ("zzz",)
    assert selection.conflicts == ()


def test_an_existing_registry_requirement_satisfies_an_unconstrained_request():
    selection = select(["pytest", "zzz"], ["pytest>=7"])

    assert selection.packages == ("zzz",)
    assert selection.conflicts == ()
    assert selection.records == ()


def test_a_missing_extra_in_an_existing_requirement_needs_a_decision():
    selection = select(["httpx[socks]"], ["httpx"], group=DependencyGroup.MAIN)

    assert selection.conflicts == (
        MergeConflict(
            where("httpx", DependencyGroup.MAIN),
            ConflictReason.UNOWNED,
            ConflictSides(MISSING, "httpx", "httpx[socks]"),
        ),
    )


def test_a_new_request_is_accepted_without_a_proposal_by_default():
    selection = select(["pytest", "zzz"], [])

    assert selection.packages == ("pytest", "zzz")
    assert selection.proposals == ()
    assert selection.records == ()


def test_a_new_request_into_a_foreign_project_is_a_proposal():
    selection = select(["pytest", "zzz"], [], proposing=True)

    proposal = MergeConflict(
        where("pytest"),
        ConflictReason.PROPOSED,
        ConflictSides(MISSING, MISSING, "pytest"),
    )
    assert selection.proposals[0] == proposal
    assert selection.packages == ("pytest", "zzz")
    assert selection.records == ()


def test_declining_a_proposal_owns_the_request_without_installing_it():
    proposal = MergeConflict(
        where("pytest"),
        ConflictReason.PROPOSED,
        ConflictSides(MISSING, MISSING, "pytest"),
    )

    selection = select(
        ["pytest", "zzz"],
        [],
        proposing=True,
        resolutions=choose(proposal, ResolutionChoice.LOCAL),
    )

    assert selection.proposals[0] == replace(
        proposal, resolution=ResolutionChoice.LOCAL
    )
    assert selection.records == (owned(declared="pytest", materialized="pytest"),)
    assert selection.packages == ("zzz",)


def test_taking_a_proposal_installs_it():
    proposal = MergeConflict(
        where("pytest"),
        ConflictReason.PROPOSED,
        ConflictSides(MISSING, MISSING, "pytest"),
    )

    selection = select(
        ["pytest"],
        [],
        proposing=True,
        resolutions=choose(proposal, ResolutionChoice.DESIRED),
    )

    assert selection.proposals[0].resolution is ResolutionChoice.DESIRED
    assert selection.packages == ("pytest",)
    assert selection.records == ()


@pytest.mark.parametrize(
    ("group", "destination"),
    [
        (DependencyGroup.MAIN, "project.dependencies"),
        (DependencyGroup.DEV, "dependency-groups.dev"),
    ],
)
def test_a_request_listed_in_another_group_is_a_decision(group, destination):
    elsewhere = {"dependency-groups.custom": ["pytest>=8"]}
    shown: dict[str, Value] = {"dependency-groups.custom": ["pytest>=8"]}

    selection = select(["pytest>=9", "zzz"], [], group=group, other_groups=elsewhere)

    assert selection.conflicts == (
        MergeConflict(
            where("pytest", group),
            ConflictReason.DIFFERENT_GROUP,
            ConflictSides(MISSING, shown, {**shown, destination: ["pytest>=9"]}),
        ),
    )
    assert selection.packages == ("zzz",)
    assert selection.proposals == ()


def test_only_requirements_with_the_same_identity_count_as_another_group():
    selection = select(
        ["pytest"],
        [],
        other_groups={
            "dependency-groups.custom": ["rich"],
            "project.dependencies": ["pytest; python_version < '3'"],
        },
    )

    assert selection.conflicts == ()
    assert selection.packages == ("pytest",)


def test_taking_the_update_over_another_group_installs_the_request():
    elsewhere = {"dependency-groups.custom": ["pytest>=8"]}
    found = select(["pytest>=9"], [], other_groups=elsewhere).conflicts[0]

    selection = select(
        ["pytest>=9", "zzz"],
        [],
        other_groups=elsewhere,
        resolutions=choose(found, ResolutionChoice.DESIRED),
    )

    assert selection.resolved == (replace(found, resolution=ResolutionChoice.DESIRED),)
    assert selection.packages == ("pytest>=9", "zzz")
    assert selection.records == ()


def test_keeping_the_other_group_owns_the_request_without_installing():
    elsewhere = {"dependency-groups.custom": ["pytest>=8"]}
    found = select(["pytest>=9"], [], other_groups=elsewhere).conflicts[0]

    selection = select(
        ["pytest>=9", "zzz"],
        [],
        other_groups=elsewhere,
        resolutions=choose(found, ResolutionChoice.LOCAL),
    )

    assert selection.resolved == (replace(found, resolution=ResolutionChoice.LOCAL),)
    assert selection.records == (owned(declared="pytest>=9", materialized="pytest>=9"),)
    assert selection.packages == ("zzz",)


def test_another_group_is_not_asked_about_when_the_file_lists_the_requirement():
    selection = select(
        ["pytest>=9"],
        ["pytest>=8"],
        other_groups={"dependency-groups.custom": ["pytest>=8"]},
    )

    assert selection.conflicts[0].reason is ConflictReason.UNOWNED


def test_a_raised_lower_bound_upgrades_what_the_resolver_wrote():
    selection = select(
        ["pytest>=10", "zzz"],
        ["pytest>=9"],
        [owned(declared="pytest>=8", materialized="pytest>=9")],
    )

    assert selection.packages == ("pytest>=10", "zzz")
    assert selection.conflicts == ()


def test_a_lowered_bound_is_not_an_upgrade():
    record = owned(declared="pytest>=8", materialized="pytest>=9")

    selection = select(["pytest>=8.5"], ["pytest>=9"], [record])

    assert selection.packages == ()
    assert selection.conflicts[0].reason is ConflictReason.DIVERGED


@pytest.mark.parametrize(
    ("record", "local", "reason", "sides"),
    [
        (
            None,
            ["pytest>=8"],
            ConflictReason.UNOWNED,
            ConflictSides(MISSING, "pytest>=8", "pytest>=9"),
        ),
        (
            owned(declared="pytest>=7", materialized="pytest>=7"),
            [],
            ConflictReason.DELETED_ANCESTOR,
            ConflictSides("pytest>=7", MISSING, "pytest>=9"),
        ),
        (
            owned(declared="pytest>=7", materialized="pytest>=7"),
            ["pytest>=6"],
            ConflictReason.DIVERGED,
            ConflictSides("pytest>=7", "pytest>=6", "pytest>=9"),
        ),
    ],
)
def test_a_changed_request_over_other_content_is_a_decision_with_its_sides(
    record, local, reason, sides
):
    selection = select(["pytest>=9", "zzz"], local, [record] if record else [])

    assert selection.conflicts == (MergeConflict(where("pytest"), reason, sides),)
    assert selection.packages == ("zzz",)
    assert selection.proposals == ()
    assert selection.resolved == ()


def settled_by(choice, record, local):
    found = select(["pytest>=9"], local, [record] if record else []).conflicts[0]
    return select(
        ["pytest>=9", "zzz"],
        local,
        [record] if record else [],
        resolutions=choose(found, choice),
    ), found


def test_taking_the_update_over_a_decision_installs_the_request():
    record = owned(declared="pytest>=7", materialized="pytest>=7")

    selection, found = settled_by(ResolutionChoice.DESIRED, record, ["pytest>=6"])

    assert selection.resolved == (replace(found, resolution=ResolutionChoice.DESIRED),)
    assert selection.conflicts == ()
    assert selection.packages == ("pytest>=9", "zzz")
    assert selection.records == ()


def test_keeping_a_local_requirement_owns_it_as_the_materialization():
    record = owned(declared="pytest>=7", materialized="pytest>=7")

    selection, found = settled_by(ResolutionChoice.LOCAL, record, ["pytest>=6"])

    assert selection.resolved == (replace(found, resolution=ResolutionChoice.LOCAL),)
    assert selection.packages == ("zzz",)
    assert selection.records == (owned(declared="pytest>=9", materialized="pytest>=6"),)


def test_keeping_a_deletion_keeps_the_resolvers_materialization():
    record = owned(declared="pytest>=7", materialized="pytest>=7.1")

    selection, _ = settled_by(ResolutionChoice.LOCAL, record, [])

    assert selection.records == (
        owned(declared="pytest>=9", materialized="pytest>=7.1"),
    )


def test_keeping_an_unowned_requirement_owns_the_local_one():
    selection, _ = settled_by(ResolutionChoice.LOCAL, None, ["pytest>=8"])

    assert selection.records == (owned(declared="pytest>=9", materialized="pytest>=8"),)


def test_only_records_of_this_group_and_file_count_as_owned():
    others = [
        owned(
            declared="pytest>=7", materialized="pytest>=7", group=DependencyGroup.DOCS
        ),
        DependencyState(
            "docs/pyproject.toml",
            DependencyGroup.DEV,
            "pytest",
            "",
            "pytest>=7",
            "pytest>=7",
        ),
    ]

    selection = select(["pytest>=9"], ["pytest>=7"], others)

    assert selection.conflicts[0].reason is ConflictReason.UNOWNED


def test_markers_make_separate_identities():
    selection = select(
        ["pytest; python_version < '3.13'", "pytest; python_version >= '3.13'"],
        [],
    )

    assert len(selection.packages) == 2
    assert selection.conflicts == ()


@pytest.mark.parametrize(
    ("local", "expected"),
    [
        (["pytest>=9"], None),
        (
            ["pytest>=10"],
            ConflictSides("pytest>=9", "pytest>=10", "pytest"),
        ),
        ([], ConflictSides("pytest>=9", MISSING, "pytest")),
        (
            ["pytest>=10", "pytest>=11"],
            ConflictSides("pytest>=9", ["pytest>=10", "pytest>=11"], "pytest"),
        ),
    ],
)
def test_a_preserved_requirement_names_what_the_file_holds(local, expected):
    found = preserved_requirement(owned(), local)

    if expected is None:
        assert found is None
        return
    assert found == MergeConflict(where("pytest"), ConflictReason.PRESERVED, expected)


def test_an_equal_requirement_in_other_notation_is_not_preserved():
    record = owned("py-test", "Py_Test", "Py_Test>=9")

    assert preserved_requirement(record, ["py-test>=9"]) is None


def retraction(requested, local, records, **kwargs):
    return retract_requirements(requested, local, tuple(records), **kwargs)


def test_an_unedited_requirement_nobody_requests_is_removed_and_released():
    kept = owned("black", "black", "black>=1")
    gone = owned()

    result = retraction(
        {DependencyGroup.DEV: ["black"]},
        {DependencyGroup.DEV: ["black>=1", "pytest>=9"]},
        [kept, gone],
    )

    assert result.removed == ((DependencyGroup.DEV, ("pytest>=9",)),)
    assert result.released == frozenset({gone.identity})
    assert result.conflicts == ()


def test_retraction_goes_on_after_a_requested_or_foreign_record():
    foreign = DependencyState(
        "docs/pyproject.toml", DependencyGroup.DEV, "a", "", "a", "a"
    )
    gone = owned()

    result = retraction(
        {}, {DependencyGroup.DEV: ["pytest>=9"]}, [foreign, owned("b", "b", "b"), gone]
    )

    assert foreign.identity not in result.released
    assert gone.identity in result.released


def test_a_group_the_file_does_not_list_only_releases_ownership():
    gone = owned()

    result = retraction({}, {}, [gone])

    assert result.removed == ()
    assert result.released == frozenset({gone.identity})


def test_an_edited_requirement_stays_until_settled():
    record = owned()
    result = retraction({}, {DependencyGroup.DEV: ["pytest>=10"]}, [record])

    assert result.conflicts == (
        MergeConflict(
            where("pytest"),
            ConflictReason.RETRACTED,
            ConflictSides("pytest>=9", "pytest>=10", MISSING),
        ),
    )
    assert result.removed == ()
    assert result.released == frozenset()


def test_several_edited_entries_are_listed_together():
    record = owned()
    result = retraction(
        {}, {DependencyGroup.DEV: ["pytest>=10", "pytest>=11"]}, [record]
    )

    assert result.conflicts[0].sides == ConflictSides(
        "pytest>=9", ["pytest>=10", "pytest>=11"], MISSING
    )


def test_retraction_goes_on_after_an_open_conflict():
    edited = owned("a", "a", "a>=1")
    gone = owned("b", "b", "b>=1")

    result = retraction(
        {},
        {DependencyGroup.DEV: ["a>=2", "b>=1"]},
        [edited, gone],
    )

    assert len(result.conflicts) == 1
    assert result.released == frozenset({gone.identity})


@pytest.mark.parametrize(
    ("choice", "removed"),
    [
        (ResolutionChoice.DESIRED, ((DependencyGroup.DEV, ("pytest>=10",)),)),
        (ResolutionChoice.LOCAL, ()),
    ],
)
def test_settling_a_retraction_releases_it(choice, removed):
    record = owned()
    local = {DependencyGroup.DEV: ["pytest>=10"]}
    found = retraction({}, local, [record]).conflicts[0]

    result = retraction({}, local, [record], resolutions=choose(found, choice))

    assert result.resolved == (replace(found, resolution=choice),)
    assert result.conflicts == ()
    assert result.removed == removed
    assert result.released == frozenset({record.identity})


@pytest.mark.parametrize(
    ("materialized", "request_", "expected"),
    [
        ("pytest>=9", "pytest>=10", True),
        ("pytest>=9", "pytest>=9", True),
        ("pytest>=9", "pytest>=8", False),
        ("pytest", "pytest>=3", True),
        ("pytest==1.0", "pytest>=2", True),
        ("pytest==2.0", "pytest==1.0", False),
        ("pytest>=1", "pytest==2", True),
        ("pytest>=1", "pytest>=2,>=3", False),
        ("pytest<2", "pytest>=1", False),
        ("pytest", "pytest<3", False),
        ("pytest==1.*", "pytest>=2", False),
        ("pytest", "pytest==2.*", False),
        ("pytest>=1", "pytest==2.*", False),
        ("pkg @ https://x/a.whl", "pkg @ https://x/a.whl", False),
        ("pkg>=1", "pkg @ https://x/a.whl", False),
    ],
)
def test_only_a_raised_simple_lower_bound_is_an_upgrade(
    materialized, request_, expected
):
    assert _upgrades(materialized, request_) is expected
