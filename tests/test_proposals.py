"""Changes into existing content are proposals; kept edits can take the update later."""

import shutil
import tomllib
from pathlib import Path

import pytest

from protostar.appends import append_marker_blocks
from protostar.config import UserConfig
from protostar.dependencies import select_dependencies
from protostar.errors import StaleReviewError, UnmatchedResolutionError
from protostar.executor import SystemExecutor
from protostar.init_draft import InitDraft, resolve_init
from protostar.intent import AppendContribution, DependencyGroup
from protostar.lifecycle import prepare_project
from protostar.manifest import CollisionStrategy, EnvironmentManifest, SystemTask
from protostar.merge import (
    MISSING,
    ConflictReason,
    MergeLocation,
    MergePolicy,
    ResolutionChoice,
    Value,
    default_choice,
    reconcile,
)
from protostar.orchestrator import Orchestrator
from protostar.preparation import (
    ExecutionPolicy,
    PreparationPhase,
    ResolutionRequest,
    deleted,
    prepare_review,
    review_phase,
    select_resolutions,
)
from protostar.recipe import Tool
from protostar.registry import resolve_hook_revisions
from protostar.sync_state import DependencyState
from protostar.system import ProcessRunner
from protostar.text_merge import reconcile_text

LOCAL, DESIRED = ResolutionChoice.LOCAL, ResolutionChoice.DESIRED
FILE = MergeLocation("pyproject.toml")
PROPOSING = MergePolicy(proposing=True)
SET = MergePolicy(frozenset({("select",)}))


# The kernel: proposals


def test_changes_into_unowned_content_are_proposals_only_when_proposing():
    local: Value = {"tool": {"ruff": {"line-length": 100}}}
    desired: Value = {
        "tool": {"ruff": {"line-length": 100, "fix": True}, "mypy": {"a": 1}}
    }

    quiet = reconcile(MISSING, local, desired, FILE)
    proposed = reconcile(MISSING, local, desired, FILE, PROPOSING)

    assert quiet.proposals == ()
    assert (
        quiet.value
        == proposed.value
        == {"tool": {"ruff": {"line-length": 100, "fix": True}, "mypy": {"a": 1}}}
    )
    # A new subtree is one proposal, not one per leaf.
    assert [p.location.keys for p in proposed.proposals] == [
        ("tool", "ruff", "fix"),
        ("tool", "mypy"),
    ]
    assert {p.reason for p in proposed.proposals} == {ConflictReason.PROPOSED}
    assert all(p.resolution is None for p in proposed.proposals)


def test_keeping_a_proposal_out_owns_the_update_and_keeps_the_bytes():
    local: Value = {"tool": {"a": 1}}
    desired: Value = {"tool": {"a": 1, "b": 2}}
    (proposal,) = reconcile(MISSING, local, desired, FILE, PROPOSING).proposals

    kept = reconcile(MISSING, local, desired, FILE, PROPOSING, {proposal.id: LOCAL})

    assert kept.value == local
    assert kept.baseline == {"tool": {"b": 2}}
    assert [p.resolution for p in kept.proposals] == [LOCAL]
    # Next time, the kept-out value reads as a deletion that can be restored.
    later = reconcile(kept.baseline, local, desired, FILE)
    (gone,) = later.preserved
    assert gone.location.keys == ("tool", "b")
    assert deleted(gone)
    restored = reconcile(
        kept.baseline, local, desired, FILE, resolutions={gone.id: DESIRED}
    )
    assert restored.value == desired
    assert [r.resolution for r in restored.resolved] == [DESIRED]


def test_a_set_union_into_an_unowned_list_is_one_proposal():
    local: Value = {"select": ["E", "F"]}
    desired: Value = {"select": ["E", "B", "UP"]}
    policy = MergePolicy(frozenset({("select",)}), proposing=True)

    (proposal,) = reconcile(MISSING, local, desired, FILE, policy).proposals
    assert proposal.sides is not None
    assert proposal.sides.desired == ["E", "F", "B", "UP"]

    kept = reconcile(MISSING, local, desired, FILE, policy, {proposal.id: LOCAL})
    assert kept.value == local
    assert kept.baseline == {"select": ["B", "UP"]}
    # The update's list still differs from what is owned, and the removed
    # members are still reported and restorable.
    later = reconcile(kept.baseline, local, desired, FILE, SET)
    (gone,) = later.preserved
    assert gone.location.keys == ("select",)
    restored = reconcile(kept.baseline, local, desired, FILE, SET, {gone.id: DESIRED})
    assert restored.value == {"select": ["E", "F", "B", "UP"]}


def test_proposal_and_preserved_defaults():
    (proposal,) = reconcile(MISSING, {}, {"a": 1}, FILE, PROPOSING).proposals
    (kept,) = reconcile({"a": 1}, {"a": 2}, {"a": 1}, FILE).preserved

    assert default_choice(proposal) is DESIRED
    assert default_choice(kept) is LOCAL
    assert proposal.choices == (LOCAL, DESIRED)
    assert kept.choices == (LOCAL, DESIRED)
    assert proposal.id != kept.id


# The kernel: preserved deviations


def test_a_kept_edit_is_reported_by_leaf_and_a_removed_value_once():
    owned: Value = {"tool": {"ruff": {"line-length": 88, "lint": {"select": ["E"]}}}}
    local: Value = {"tool": {"ruff": {"line-length": 100}}}

    result = reconcile(owned, local, owned, FILE)

    assert result.value == local
    assert [(p.location.keys, deleted(p)) for p in result.preserved] == [
        (("tool", "ruff", "line-length"), False),
        (("tool", "ruff", "lint"), True),
    ]


def test_extra_members_of_a_set_are_no_edit():
    owned: Value = {"select": ["E"]}

    assert reconcile(owned, {"select": ["E", "F"]}, owned, FILE, SET).preserved == ()


def test_keeping_a_kept_edit_changes_nothing():
    owned: Value = {"a": 1}
    local: Value = {"a": 2}
    (kept,) = reconcile(owned, local, owned, FILE).preserved

    result = reconcile(owned, local, owned, FILE, resolutions={kept.id: LOCAL})

    assert result.value == local
    assert result.preserved == ()
    assert [r.resolution for r in result.resolved] == [LOCAL]


# Text and regions


def test_a_kept_text_edit_or_deletion_can_take_the_update():
    location = MergeLocation("justfile")
    edited = reconcile_text(b"mine\n", "ours\n", "ours\n", location)
    gone = reconcile_text(None, "ours\n", "ours\n", location)

    assert edited.content is None
    (kept,) = edited.preserved
    assert kept.sides is not None
    assert kept.sides.local == "mine\n"
    assert deleted(gone.preserved[0])
    restored = reconcile_text(
        b"mine\n", "ours\n", "ours\n", location, resolutions={kept.id: DESIRED}
    )
    assert restored.content == "ours\n"
    # A checkout that only changed line endings is no edit.
    assert reconcile_text(b"ours\r\n", "ours\n", "ours\n", location).preserved == ()


def test_a_removed_region_can_take_the_update():
    payload = [AppendContribution("agents", "Use uv.\n")]
    first = append_marker_blocks("# Notes\n", payload, Path("AGENTS.md"))
    removed = "# Notes\n"

    kept = append_marker_blocks(
        removed, payload, Path("AGENTS.md"), baselines=first.baselines
    )
    (gone,) = kept.preserved
    assert kept.content == removed
    restored = append_marker_blocks(
        removed,
        payload,
        Path("AGENTS.md"),
        baselines=first.baselines,
        resolutions={gone.id: DESIRED},
    )
    assert "Use uv." in restored.content


# Dependencies


def record(requested: str, materialized: str) -> DependencyState:
    return DependencyState(
        "pyproject.toml", DependencyGroup.DEV, "ruff", "", requested, materialized
    )


def test_new_requirements_of_an_unowned_project_are_proposals():
    selected = select_dependencies(
        ["ruff"], [], (), DependencyGroup.DEV, proposing=True
    )
    (proposal,) = selected.proposals

    assert selected.packages == ("ruff",)
    declined = select_dependencies(
        ["ruff"],
        [],
        (),
        DependencyGroup.DEV,
        proposing=True,
        resolutions={proposal.id: LOCAL},
    )
    assert declined.packages == ()
    assert declined.records == (record("ruff", "ruff"),)


def test_a_differing_unowned_requirement_can_be_kept_or_taken():
    (conflict,) = select_dependencies(
        ["ruff"], ["ruff>=0.5"], (), DependencyGroup.DEV
    ).conflicts
    assert conflict.reason is ConflictReason.UNOWNED
    assert conflict.choices == (LOCAL, DESIRED)

    kept = select_dependencies(
        ["ruff"],
        ["ruff>=0.5"],
        (),
        DependencyGroup.DEV,
        resolutions={conflict.id: LOCAL},
    )
    assert kept.packages == ()
    assert kept.records == (record("ruff", "ruff>=0.5"),)
    # Kept, the requirement stands for the request: nothing is pending after.
    again = select_dependencies(
        ["ruff"], ["ruff>=0.5"], kept.records, DependencyGroup.DEV
    )
    assert (again.packages, again.conflicts, again.preserved) == ((), (), ())

    taken = select_dependencies(
        ["ruff"],
        ["ruff>=0.5"],
        (),
        DependencyGroup.DEV,
        resolutions={conflict.id: DESIRED},
    )
    assert taken.packages == ("ruff",)


def test_a_removed_owned_requirement_can_take_the_update():
    owned = (record("ruff", "ruff>=0.14"),)
    kept = select_dependencies(["ruff"], [], owned, DependencyGroup.DEV)
    (gone,) = kept.preserved

    assert kept.packages == ()
    assert deleted(gone)
    restored = select_dependencies(
        ["ruff"], [], owned, DependencyGroup.DEV, resolutions={gone.id: DESIRED}
    )
    assert restored.packages == ("ruff",)


# Selectors and review phases


def test_a_file_selector_never_restores_a_kept_edit():
    local: Value = {"a": 2, "b": 1}
    owned: Value = {"a": 1}
    review_decisions = (
        *reconcile(owned, local, owned, FILE).preserved,
        *reconcile(MISSING, local, {"c": 3}, FILE, PROPOSING).proposals,
    )
    kept, proposal = review_decisions

    chosen = select_resolutions(
        review_decisions, [ResolutionRequest("pyproject.toml", DESIRED)]
    )
    assert chosen == {proposal.id: DESIRED}
    assert select_resolutions(
        review_decisions, [ResolutionRequest(kept.id, DESIRED)]
    ) == {kept.id: DESIRED}


def test_the_review_shows_both_batches_unless_a_command_creates_their_input():
    manifest = EnvironmentManifest()
    assert review_phase(manifest) is PreparationPhase.BEFORE_COMMANDS
    manifest.tasks.system_tasks.append(
        SystemTask(["uv", "init"], owned_files=["pyproject.toml"])
    )
    assert review_phase(manifest) is PreparationPhase.BEFORE_INITIALIZERS


def test_execution_rejects_a_reviewed_choice_that_settles_nothing(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "old"\n')
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]\nline-length = 88\n", producer="module:test"
    )
    executor = SystemExecutor(manifest, UserConfig(), resolutions={"0" * 12: LOCAL})
    mocker.patch.object(executor, "_check_ide_extensions")

    with pytest.raises(StaleReviewError):
        executor.execute()
    assert Path("pyproject.toml").read_text() == '[project]\nname = "old"\n'


def test_a_lifecycle_review_rejects_an_unknown_choice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(UnmatchedResolutionError):
        prepare_review(EnvironmentManifest(), UserConfig(), resolutions={"x": LOCAL})


# The whole path: an existing project adopted without a change


LEGACY = {
    "pyproject.toml": """\
[project]
name = "legacy"
version = "0.3.1"
requires-python = ">=3.12"
dependencies = ["httpx"]

[dependency-groups]
dev = ["ruff>=0.5", "pytest"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
    "justfile": "test:\n    uv run pytest\n",
    ".pre-commit-config.yaml": (
        "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v0.6.0\n    hooks:\n      - id: ruff\n"
    ),
    ".github/workflows/ci.yml": (
        "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v4\n      - run: uv run pytest\n"
    ),
}


@pytest.fixture
def legacy(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROTOSTAR_OFFLINE_HOOK_REGISTRY", "1")
    monkeypatch.setattr("protostar.metadata.get_git_config", lambda key: None)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    mocker.patch.object(ProcessRunner, "run")
    mocker.patch.object(SystemExecutor, "_check_ide_extensions")
    for name, content in LEGACY.items():
        Path(name).parent.mkdir(parents=True, exist_ok=True)
        Path(name).write_text(content, newline="\n")
    return tmp_path


def adopt(choice: ResolutionChoice | None) -> None:
    config = UserConfig()
    tools = {
        Tool.RUFF: True,
        Tool.PYTEST: True,
        Tool.JUST: True,
        Tool.PREK: True,
        Tool.CI: True,
        Tool.DIRENV: False,
        Tool.MYPY: False,
        Tool.RUMDL: False,
    }
    draft = InitDraft(
        tool_overrides=tuple(tools.items()),
        collision_strategy=CollisionStrategy.MERGE,
    )
    modules, request = resolve_init(draft, config)
    engine = Orchestrator(modules, config, request=request)
    manifest = engine.plan()
    revisions = resolve_hook_revisions()
    phase = review_phase(manifest)
    assert phase is PreparationPhase.BEFORE_COMMANDS
    review = prepare_review(
        manifest,
        config,
        hook_revisions=revisions,
        policy=ExecutionPolicy.INITIALIZATION,
        phase=phase,
    )
    # Each change the review offers is a choice, including what used to be
    # settled only by hand.
    assert all(conflict.choices for conflict in review.conflicts)
    assert {p.location.file for p in review.proposals} >= {
        "pyproject.toml",
        ".pre-commit-config.yaml",
        ".github/workflows/ci.yml",
    }
    choices = (
        {d.id: choice for d in review.decisions if choice in d.choices}
        if choice
        else {}
    )
    engine.execute(engine.plan(), hook_revisions=revisions, resolutions=choices)


def test_keeping_everything_changes_no_existing_file_and_checks_clean(legacy):
    adopt(LOCAL)

    for name, content in LEGACY.items():
        text = Path(name).read_text()
        if name == "pyproject.toml":
            # Only the recipe is added, after everything that was there.
            assert text.startswith(content)
            added = tomllib.loads(text)
            assert set(added["tool"]) == {"ruff", "pytest", "protostar"}
            assert added["tool"]["ruff"]["lint"]["select"] == ["E", "F", "I"]
        else:
            assert text == content, name
    project = prepare_project()
    assert not project.review.pending
    kept = {(p.location.file, p.location.keys) for p in project.review.preserved}
    assert (".github/workflows/ci.yml", ("jobs", "lint")) in kept
    assert ("pyproject.toml", ("tool", "ruff", "lint", "select")) in kept

    # A kept change takes the update later, through sync.
    select = next(
        p
        for p in project.review.preserved
        if p.location.keys == ("tool", "ruff", "lint", "select")
    )
    project.resolve({select.id: DESIRED}).apply()
    lint = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["ruff"]["lint"]
    assert lint["select"][:3] == ["E", "F", "I"]
    assert {"A", "B", "C4", "RUF", "UP"} <= set(lint["select"])
    assert not prepare_project().review.pending


def test_without_choices_init_merges_as_before(legacy):
    adopt(None)

    lint = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["ruff"]["lint"]
    assert {"A", "B", "E", "F", "I"} <= set(lint["select"])
    assert "default_install_hook_types" in Path(".pre-commit-config.yaml").read_text()
