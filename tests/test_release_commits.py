"""Release eligibility follows the Git diff across at most a bump and refresh."""

import json
import subprocess
import sys

import pytest

from scripts import release_commits
from scripts._common import fixture_environment
from scripts.release_commits import RELEASE_INPUTS, workflow_commits


@pytest.fixture
def history(tmp_path, mocker):
    env = {
        **fixture_environment(),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "GIT_AUTHOR_NAME": "Release test",
        "GIT_AUTHOR_EMAIL": "release@example.invalid",
        "GIT_COMMITTER_NAME": "Release test",
        "GIT_COMMITTER_EMAIL": "release@example.invalid",
    }

    def run(command, *, capture_output=True):
        return subprocess.run(
            command, cwd=tmp_path, env=env, text=True, capture_output=capture_output
        )

    def git(*args):
        result = run(["git", *args])
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def commit(changes, message="change"):
        for name, content in changes.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                path.unlink()
            else:
                path.write_text(content, encoding="utf-8")
        git("add", ".")
        git("commit", "--allow-empty", "-m", message)
        return git("rev-parse", "HEAD")

    git("init", "-b", "main")
    git("config", "core.hooksPath", str(tmp_path / "no-hooks"))
    commit(
        dict.fromkeys(
            (*RELEASE_INPUTS, "pyproject.toml", "uv.lock", "src/code.py"), "initial\n"
        )
    )
    mocker.patch.object(release_commits, "run_repo_cmd", side_effect=run)
    return git, commit


def test_nightly_can_precede_refresh_and_bump_but_ci_must_cover_refresh(history):
    git, commit = history
    base = git("rev-parse", "HEAD")
    refresh = commit({RELEASE_INPUTS[0]: "refreshed\n"})
    assert workflow_commits(refresh) == {
        "ci.yml": [refresh],
        "nightly.yml": [refresh, base],
    }
    bump = commit({"pyproject.toml": "new version\n", "uv.lock": "new version\n"})
    assert workflow_commits(bump, tagged=True) == {
        "ci.yml": [bump, refresh],
        "nightly.yml": [bump, refresh, base],
    }


def test_release_gate_shallow_checkout_contains_enough_history(
    history, tmp_path, mocker
):
    git, commit = history
    base = commit({"src/code.py": "last code change\n"})
    refresh = commit({RELEASE_INPUTS[0]: "refreshed\n"})
    bump = commit({"pyproject.toml": "new version\n"})
    checkout = tmp_path / "shallow"
    git("clone", "--depth", "3", tmp_path.as_uri(), str(checkout))
    mocker.patch.object(
        release_commits,
        "run_repo_cmd",
        side_effect=lambda command, **kwargs: subprocess.run(
            command, cwd=checkout, env=fixture_environment(), text=True, **kwargs
        ),
    )
    assert workflow_commits(bump, tagged=True) == {
        "ci.yml": [bump, refresh],
        "nightly.yml": [bump, refresh, base],
    }


def test_release_gate_cli_serializes_workflow_specific_commits(history, mocker, capsys):
    git, commit = history
    base = git("rev-parse", "HEAD")
    refresh = commit({RELEASE_INPUTS[1]: "refreshed\n"})
    bump = commit({"pyproject.toml": "new version\n"})
    mocker.patch.object(sys, "argv", ["release_commits.py", bump, "--tagged"])
    release_commits.main()
    assert json.loads(capsys.readouterr().out) == {
        "ci.yml": [bump, refresh],
        "nightly.yml": [bump, refresh, base],
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"src/code.py": "changed\n"},
        {RELEASE_INPUTS[0]: "changed\n", "src/code.py": "changed\n"},
        {RELEASE_INPUTS[0]: None},
        {},
    ],
)
def test_refresh_message_cannot_hide_substantive_deleting_or_empty_commit(
    history, changes
):
    _, commit = history
    head = commit(changes, "chore(release): refresh generated release inputs")
    assert workflow_commits(head) == {"ci.yml": [head], "nightly.yml": [head]}


def test_adding_a_generated_file_cannot_borrow_parent_nightly(history):
    _, commit = history
    commit({RELEASE_INPUTS[0]: None})
    head = commit({RELEASE_INPUTS[0]: "added\n"})
    assert workflow_commits(head)["nightly.yml"] == [head]


def test_version_files_are_only_skipped_for_tagged_release(history):
    git, commit = history
    base = git("rev-parse", "HEAD")
    bump = commit({"pyproject.toml": "new version\n"})
    assert workflow_commits(bump) == {"ci.yml": [bump], "nightly.yml": [bump]}
    assert workflow_commits(bump, tagged=True) == {
        "ci.yml": [bump, base],
        "nightly.yml": [bump, base],
    }


def test_mixed_version_bump_cannot_skip_a_code_change(history):
    _, commit = history
    head = commit({"pyproject.toml": "new version\n", "src/code.py": "changed\n"})
    assert workflow_commits(head, tagged=True) == {
        "ci.yml": [head],
        "nightly.yml": [head],
    }


def test_nightly_never_skips_past_the_refresh_parent(history):
    _, commit = history
    code = commit({"src/code.py": "changed\n"})
    refresh = commit({RELEASE_INPUTS[1]: "new rules\n"})
    assert workflow_commits(refresh)["nightly.yml"] == [refresh, code]


def test_a_merge_is_not_treated_as_a_refresh(history):
    git, commit = history
    git("branch", "side")
    commit({RELEASE_INPUTS[0]: "new pins\n"})
    git("checkout", "side")
    commit({RELEASE_INPUTS[1]: "new rules\n"})
    git("checkout", "main")
    git("merge", "--no-ff", "side", "-m", "refresh inputs")
    head = git("rev-parse", "HEAD")
    assert workflow_commits(head) == {"ci.yml": [head], "nightly.yml": [head]}
