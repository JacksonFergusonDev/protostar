"""Contracts of reconciling single documents and of reading the committed state."""

import logging
from pathlib import Path

import pytest

from protostar import __version__
from protostar.config import UserConfig
from protostar.documents import renovate
from protostar.errors import ConfigurationError, OutdatedProtostarError
from protostar.manifest import EnvironmentManifest
from protostar.merge import ConflictReason
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import ReviewWorkspace
from protostar.sync_state import (
    FilePolicy,
    FileState,
    SyncState,
    serialize_state,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


@pytest.fixture
def reconciliation(workspace):
    return Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )


def reconcile(reconciliation, path, policy, desired, local=None):
    if local is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(local, encoding="utf-8", newline="")
    located = reconciliation._locate(path, policy)
    return reconciliation._reconcile_document(located, desired, policy)


# ---- reconciling one document ---- #


def test_a_json_document_without_an_indent_to_follow_gets_two_spaces(
    reconciliation, workspace
):
    reconcile(
        reconciliation,
        renovate.TARGET,
        FilePolicy.JSONC,
        '{"a": {"b": 1}}',
        local="{}\n",
    )

    assert workspace.contents[renovate.TARGET] == (b'{\n  "a": {\n    "b": 1\n  }\n}\n')


@pytest.mark.parametrize(
    ("path", "policy", "desired", "local"),
    [
        (
            renovate.TARGET,
            FilePolicy.JSONC,
            '{"extends": ["config:base"]}',
            '{"x": 1}\n',
        ),
        (".readthedocs.yaml", FilePolicy.YAML, "version: 2\n", "foreign: 1\n"),
    ],
)
def test_a_change_into_a_file_never_owned_is_a_proposal(
    reconciliation, path, policy, desired, local
):
    reconcile(reconciliation, path, policy, desired, local)

    assert [c.reason for c in reconciliation.proposals] == [ConflictReason.PROPOSED]


@pytest.mark.parametrize(
    ("path", "policy", "desired", "baseline", "local"),
    [
        (
            renovate.TARGET,
            FilePolicy.JSONC,
            '{"extends": ["a"], "more": 1}',
            '{"extends": ["a"]}',
            '{"extends": ["a"]}\n',
        ),
        (
            ".readthedocs.yaml",
            FilePolicy.YAML,
            "version: 2\nformats: all\n",
            "version: 2\n",
            "version: 2\n",
        ),
    ],
)
def test_a_change_into_a_file_it_owns_is_no_proposal(
    reconciliation, path, policy, desired, baseline, local
):
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState(path, policy, baseline)
    )

    reconcile(reconciliation, path, policy, desired, local)

    assert reconciliation.proposals == []


# ---- the committed ownership state ---- #


def lock(workspace, state):
    Path("protostar.lock").write_text(
        serialize_state(state), encoding="utf-8", newline=""
    )


def test_a_lock_from_a_newer_protostar_is_refused(reconciliation, workspace):
    lock(workspace, SyncState("99.0.0"))

    with pytest.raises(OutdatedProtostarError):
        reconciliation._load_state()


def test_a_lock_from_an_older_protostar_is_continued_as_this_one(
    reconciliation, workspace
):
    lock(workspace, SyncState("0.0.1"))

    reconciliation._load_state()

    assert reconciliation.candidate_state.producer_version == __version__
    assert reconciliation._committed is not None
    assert reconciliation._committed.producer_version == "0.0.1"


def test_an_unreadable_lock_is_a_configuration_error(reconciliation, workspace):
    Path("protostar.lock").write_bytes(b"\xff\xfe")

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._load_state()

    assert str(caught.value) == "Cannot read Protostar state."
    assert caught.value.hint == "Correct the state file encoding and permissions."


# ---- small writers ---- #


def test_a_workflow_for_a_project_without_supported_systems_targets_linux(
    reconciliation, workspace
):
    reconciliation.manifest.tooling.wants_ci = True

    reconciliation._write_ci_workflow()

    workflow = workspace.contents[".github/workflows/ci.yml"].decode()
    assert "ubuntu-latest" in workflow
    assert "macos" not in workflow
    assert "windows" not in workflow


def test_appending_ignores_logs_how_many_were_missing(
    reconciliation, workspace, caplog
):
    Path(".gitignore").write_text("a/\n", encoding="utf-8", newline="")
    reconciliation.manifest.filesystem.vcs_ignores = {"a/", "b/", "c/"}
    caplog.set_level(logging.DEBUG, logger="protostar")

    reconciliation._write_ignores()

    assert "Appended 2 items to .gitignore" in caplog.messages
