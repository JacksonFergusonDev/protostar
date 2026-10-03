"""Contracts of dependency-group include reconciliation, from its mutation run.

Every case drives ``Reconciliation._apply_dependency_includes`` against a
pyproject.toml in the workspace and asserts the whole outcome: the bytes
accepted, the warnings, and the ownership recorded.
"""

import sys
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, FileSystemError
from protostar.intent import DependencyGroup, DependencyInclude
from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from protostar.merge import ConflictReason, MergeConflict, MergeLocation
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import LiveWorkspace, ReviewWorkspace
from protostar.sync_state import (
    DependencyState,
    FilePolicy,
    FileState,
    decode_toml_baseline,
    encode_toml_baseline,
)

DEV = DependencyGroup.DEV
DOCS = DependencyGroup.DOCS
TARGET = "pyproject.toml"
DEV_INCLUDES_DOCS = DependencyInclude(DEV, DOCS)
DOCS_INCLUDES_DEV = DependencyInclude(DOCS, DEV)
INCLUDE_DOCS = {"include-group": "docs"}
INCLUDE_DEV = {"include-group": "dev"}

BOTH_GROUPS = '[dependency-groups]\ndev = ["pytest"]\ndocs = ["zensical"]\n'
OWNED_BASELINE_ERROR = "Invalid owned dependency-group baseline."


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


@pytest.fixture
def reconciliation(workspace):
    return Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )


def apply(
    reconciliation,
    pyproject=None,
    *,
    edges=(DEV_INCLUDES_DOCS,),
    owned=None,
    strategy=CollisionStrategy.MERGE,
):
    """Declares ``edges``, writes ``pyproject``, records ``owned``, and applies."""
    if pyproject is not None:
        Path(TARGET).write_text(pyproject, encoding="utf-8", newline="")
    reconciliation.manifest.dependencies.includes.extend(edges)
    reconciliation.manifest.collision_strategy = strategy
    if owned is not None:
        reconciliation.candidate_state = reconciliation.candidate_state.with_file(
            FileState(
                TARGET,
                FilePolicy.TOML,
                encode_toml_baseline({"dependency-groups": owned}),
            )
        )
    reconciliation._apply_dependency_includes()


def accepted(workspace):
    """Returns the pyproject.toml text Protostar accepted, or None."""
    content = workspace.contents.get(TARGET)
    return None if content is None else content.decode("utf-8")


def owned_groups(reconciliation):
    """Returns the include ownership recorded for pyproject.toml, or None."""
    record = next(
        (r for r in reconciliation.candidate_state.files if r.path == TARGET), None
    )
    if record is None:
        return None
    return decode_toml_baseline(record.baseline)["dependency-groups"]


def warning(where, conflict):
    return DiagnosticEvent(
        DiagnosticPhase.EXECUTOR,
        f"Kept your version of pyproject.toml at {where}: "
        "it conflicts with the update.",
        Severity.WARNING,
        conflict=conflict,
    )


def kept(group, include, reason):
    """The warning for an include edge that was kept out, and why."""
    return warning(
        f"dependency-groups.{group}",
        MergeConflict(
            MergeLocation(TARGET, ("dependency-groups", group), include), reason
        ),
    )


def test_no_declared_include_touches_nothing(reconciliation, workspace):
    Path(TARGET).write_text(BOTH_GROUPS, encoding="utf-8", newline="")

    reconciliation._apply_dependency_includes()

    assert workspace.contents == {}
    assert reconciliation.diagnostics == []


def test_a_new_project_gets_both_groups_and_owns_the_edge(reconciliation, workspace):
    apply(reconciliation)

    assert accepted(workspace) == (
        '[dependency-groups]\ndev = [{ include-group = "docs" }]\ndocs = []\n'
    )
    assert owned_groups(reconciliation) == {"dev": [INCLUDE_DOCS], "docs": []}
    assert reconciliation._resolution_dirty
    assert reconciliation.diagnostics == []


def test_an_include_is_added_beside_the_local_requirements(reconciliation, workspace):
    apply(reconciliation, BOTH_GROUPS)

    assert tomllib.loads(accepted(workspace))["dependency-groups"] == {
        "dev": ["pytest", INCLUDE_DOCS],
        "docs": ["zensical"],
    }
    # `docs` exists in the project already, so Protostar owns none of it.
    assert owned_groups(reconciliation) == {"dev": [INCLUDE_DOCS]}


def test_an_include_already_in_place_is_owned_without_rewriting_the_file(
    reconciliation, workspace
):
    apply(
        reconciliation,
        '[dependency-groups]\ndev = [{include-group = "docs"}]\ndocs = []\n',
        owned={"dev": [INCLUDE_DOCS]},
    )

    assert accepted(workspace) is None
    assert not reconciliation._resolution_dirty
    assert owned_groups(reconciliation) == {"dev": [INCLUDE_DOCS]}


def test_a_missing_project_file_is_read_as_empty_when_nothing_deleted_it(
    tmp_path, workspace
):
    # Execution reads the live disk, where reading a missing file fails.
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), LiveWorkspace(), workspace, workspace
    )

    apply(reconciliation)

    assert accepted(workspace).startswith("[dependency-groups]\n")
    assert reconciliation._resolution_dirty


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
def test_the_project_file_is_checked_against_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / TARGET).write_text(BOTH_GROUPS, encoding="utf-8", newline="")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / TARGET).symlink_to(root / TARGET)
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )
    reconciliation.manifest.dependencies.includes.append(DEV_INCLUDES_DOCS)

    reconciliation._apply_dependency_includes()

    assert (
        INCLUDE_DOCS in tomllib.loads(accepted(workspace))["dependency-groups"]["dev"]
    )


@pytest.mark.parametrize("by", ["file", "dependency"])
def test_a_deleted_project_file_stays_deleted_with_a_warning(
    reconciliation, workspace, by
):
    if by == "file":
        record = FileState(TARGET, FilePolicy.TOML, encode_toml_baseline({}))
        reconciliation.candidate_state = reconciliation.candidate_state.with_file(
            record
        )
    else:
        reconciliation.candidate_state = replace(
            reconciliation.candidate_state,
            dependencies=(
                DependencyState(TARGET, DEV, "pytest", "", "pytest", "pytest"),
            ),
        )

    apply(reconciliation)

    assert workspace.contents == {}
    assert reconciliation.diagnostics == [
        warning(
            "dependency-groups",
            MergeConflict(
                MergeLocation(TARGET, ("dependency-groups",)),
                ConflictReason.DELETED_ANCESTOR,
            ),
        )
    ]


def test_overwrite_recreates_a_deleted_project_file(reconciliation, workspace):
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState(TARGET, FilePolicy.TOML, encode_toml_baseline({}))
    )

    apply(reconciliation, strategy=CollisionStrategy.OVERWRITE)

    assert accepted(workspace).startswith("[dependency-groups]\n")
    assert reconciliation.diagnostics == []


def test_a_corrupt_ownership_table_is_a_configuration_error(reconciliation, workspace):
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState(
            TARGET,
            FilePolicy.TOML,
            encode_toml_baseline({"dependency-groups": ["oops"]}),
        )
    )

    with pytest.raises(ConfigurationError) as caught:
        apply(reconciliation, BOTH_GROUPS)

    assert str(caught.value) == OWNED_BASELINE_ERROR
    assert caught.value.hint == "Keep dependency-group ownership as a TOML table."
    assert workspace.contents == {}


def test_a_corrupt_owned_group_is_a_configuration_error(reconciliation, workspace):
    with pytest.raises(ConfigurationError) as caught:
        apply(reconciliation, BOTH_GROUPS, owned={"dev": "oops"})

    assert str(caught.value) == OWNED_BASELINE_ERROR
    assert (
        caught.value.hint
        == "Keep owned dependency groups as arrays of include records."
    )
    assert workspace.contents == {}


@pytest.mark.parametrize(
    "pyproject",
    [
        # The groups are not a table at all.
        'dependency-groups = "oops"\n',
        # The included group is not a list.
        '[dependency-groups]\ndev = []\ndocs = "oops"\n',
        # Two records could each be the one Protostar owns.
        "[dependency-groups]\n"
        'dev = [{include-group = "docs"}, {include-group = "docs"}]\n'
        "docs = []\n",
    ],
)
def test_an_unreadable_shape_is_kept_with_a_diverged_warning(
    reconciliation, workspace, pyproject
):
    apply(reconciliation, pyproject)

    assert workspace.contents == {}
    assert reconciliation.diagnostics == [kept("dev", "docs", ConflictReason.DIVERGED)]
    assert reconciliation.candidate_state.files == ()
    assert not reconciliation._resolution_dirty


def test_the_same_record_once_is_not_ambiguous(reconciliation, workspace):
    apply(
        reconciliation,
        '[dependency-groups]\ndev = [{include-group = "docs"}]\ndocs = []\n',
        owned={"dev": [INCLUDE_DOCS]},
    )

    assert reconciliation.diagnostics == []


def test_other_include_records_do_not_make_an_include_ambiguous(
    reconciliation, workspace
):
    apply(
        reconciliation,
        "[dependency-groups]\n"
        'dev = [{include-group = "docs"}, {include-group = "other"}, "pytest"]\n'
        "docs = []\n",
        owned={"dev": [INCLUDE_DOCS]},
    )

    assert reconciliation.diagnostics == []


@pytest.mark.parametrize(
    ("pyproject", "owned"),
    [
        # The group is no list: the project replaced it.
        ('[dependency-groups]\ndev = "oops"\ndocs = []\n', {}),
        # Protostar owned the group, and it is gone.
        ("[dependency-groups]\ndocs = []\n", {"dev": []}),
        # Protostar owned the included group, and it is gone.
        ("[dependency-groups]\ndev = []\n", {"docs": []}),
    ],
)
def test_a_group_the_project_removed_is_kept_out_with_a_deleted_warning(
    reconciliation, workspace, pyproject, owned
):
    apply(reconciliation, pyproject, owned=owned)

    assert workspace.contents == {}
    assert reconciliation.diagnostics == [
        kept("dev", "docs", ConflictReason.DELETED_ANCESTOR)
    ]
    assert not reconciliation._resolution_dirty


@pytest.mark.parametrize(
    ("pyproject", "owned"),
    [
        # Protostar owned the group, and it is gone.
        ("[dependency-groups]\ndocs = []\n", {"dev": [INCLUDE_DOCS]}),
        # The include was owned and the project removed it from its group.
        ("[dependency-groups]\ndev = []\ndocs = []\n", {"dev": [INCLUDE_DOCS]}),
    ],
)
def test_an_include_the_project_removed_stays_removed_without_a_warning(
    reconciliation, workspace, pyproject, owned
):
    apply(reconciliation, pyproject, owned=owned)

    assert workspace.contents == {}
    assert reconciliation.diagnostics == []
    # The edge was settled by leaving it out, so ownership does not change.
    assert owned_groups(reconciliation) == owned


@pytest.mark.parametrize(
    ("pyproject", "owned"),
    [
        ("[dependency-groups]\ndocs = []\n", {"dev": []}),
        ("[dependency-groups]\ndev = []\n", {"docs": []}),
    ],
)
def test_overwrite_restores_what_the_project_removed(
    reconciliation, workspace, pyproject, owned
):
    apply(reconciliation, pyproject, owned=owned, strategy=CollisionStrategy.OVERWRITE)

    assert reconciliation.diagnostics == []
    assert (
        INCLUDE_DOCS in tomllib.loads(accepted(workspace))["dependency-groups"]["dev"]
    )


def test_groups_the_project_still_has_are_not_taken_as_deleted(
    reconciliation, workspace
):
    apply(
        reconciliation,
        BOTH_GROUPS,
        owned={"dev": [], "docs": []},
    )

    assert reconciliation.diagnostics == []
    assert tomllib.loads(accepted(workspace))["dependency-groups"]["dev"] == [
        "pytest",
        INCLUDE_DOCS,
    ]
    assert owned_groups(reconciliation) == {"dev": [INCLUDE_DOCS], "docs": []}


def test_an_included_group_the_project_lacks_becomes_owned_empty(
    reconciliation, workspace
):
    apply(reconciliation, '[dependency-groups]\ndev = ["pytest"]\n')

    assert tomllib.loads(accepted(workspace))["dependency-groups"] == {
        "dev": ["pytest", INCLUDE_DOCS],
        "docs": [],
    }
    assert owned_groups(reconciliation) == {"dev": [INCLUDE_DOCS], "docs": []}


def test_a_matching_include_the_project_wrote_itself_is_not_adopted(
    reconciliation, workspace
):
    apply(
        reconciliation,
        '[dependency-groups]\ndev = [{include-group = "docs"}]\ndocs = []\n',
    )

    assert workspace.contents == {}
    assert reconciliation.diagnostics == []
    assert reconciliation.candidate_state.files == ()


def test_overwrite_adopts_a_matching_include_the_project_wrote(
    reconciliation, workspace
):
    apply(
        reconciliation,
        '[dependency-groups]\ndev = [{include-group = "docs"}]\ndocs = []\n',
        strategy=CollisionStrategy.OVERWRITE,
    )

    assert owned_groups(reconciliation) == {"dev": [INCLUDE_DOCS]}


@pytest.mark.parametrize(
    ("pyproject", "owned", "warnings"),
    [
        # The first edge cannot be read.
        (
            "[dependency-groups]\n"
            'dev = [{include-group = "docs"}, {include-group = "docs"}]\n'
            "docs = []\n",
            None,
            [kept("dev", "docs", ConflictReason.DIVERGED)],
        ),
        # The first edge was removed by the project.
        (
            "[dependency-groups]\ndev = []\ndocs = []\n",
            {"dev": [INCLUDE_DOCS]},
            [],
        ),
        # The first edge is the project's own.
        (
            '[dependency-groups]\ndev = [{include-group = "docs"}]\ndocs = []\n',
            None,
            [],
        ),
    ],
)
def test_a_kept_out_edge_does_not_stop_the_next_one(
    reconciliation, workspace, pyproject, owned, warnings
):
    apply(
        reconciliation,
        pyproject,
        edges=(DEV_INCLUDES_DOCS, DOCS_INCLUDES_DEV),
        owned=owned,
    )

    groups = tomllib.loads(accepted(workspace))["dependency-groups"]
    assert groups["docs"] == [INCLUDE_DEV]
    assert reconciliation.diagnostics == warnings


def test_a_failed_write_names_the_operation_path_and_cause(reconciliation, monkeypatch):
    error = OSError("disk full")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(reconciliation.fs, "write_text", fail)

    with pytest.raises(FileSystemError) as caught:
        apply(reconciliation, BOTH_GROUPS)

    assert caught.value.operation == "apply dependency includes"
    assert caught.value.path == TARGET
    assert caught.value.original is error
    assert caught.value.__cause__ is error


def test_an_undecodable_project_file_names_the_operation_path_and_cause(
    reconciliation,
):
    Path(TARGET).write_bytes(b"\xff\xfe")
    reconciliation.manifest.dependencies.includes.append(DEV_INCLUDES_DOCS)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._apply_dependency_includes()

    assert caught.value.operation == "apply dependency includes"
    assert caught.value.path == TARGET
    assert isinstance(caught.value.original, UnicodeDecodeError)
