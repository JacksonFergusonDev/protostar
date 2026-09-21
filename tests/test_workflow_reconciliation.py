"""GitHub Actions workflow reconciliation scenarios over real generator output."""

from typing import Any, cast

import pytest

from protostar.github_workflows import reconcile_workflow
from protostar.merge import ConflictReason, MergeConflict
from protostar.sync_state import FilePolicy, FileState
from protostar.workflows import (
    CIWorkflowSpec,
    generate_ci_workflow,
    generate_release_workflow,
)
from protostar.yaml_ast import (
    CI_WORKFLOW_TARGET,
    RELEASE_WORKFLOW_TARGET,
    YamlReconciliation,
    decode_yaml_baseline,
    encode_yaml_baseline,
)

RUFF = "      - name: Run Ruff Linter\n        run: uv run ruff check ."
SETUP_UV = "astral-sh/setup-uv@v10.0.0"
BUMPED_UV = "astral-sh/setup-uv@v11.0.0"


def ci(*flags: str, systems: tuple[str, ...] = ("Linux",), python: str = "3.14") -> str:
    return generate_ci_workflow(
        CIWorkflowSpec(list(systems), python, set(flags), [RUFF])
    )


def run(
    local: str | None,
    desired: str,
    previous: YamlReconciliation | None = None,
    *,
    target: str = CI_WORKFLOW_TARGET,
    overwrite: bool = False,
) -> YamlReconciliation:
    record = (
        FileState(
            target,
            FilePolicy.YAML,
            encode_yaml_baseline(cast(dict[str, Any], previous.baseline)),
        )
        if previous is not None
        else None
    )
    return reconcile_workflow(
        target,
        local or "",
        desired,
        record,
        missing_file=local is None,
        overwrite=overwrite,
    )


def load(content: str) -> Any:
    return decode_yaml_baseline(content)


def steps(content: str, job: str = "test") -> list[Any]:
    return cast(list[Any], load(content)["jobs"][job]["steps"])


def names(content: str, job: str = "test") -> list[str]:
    return [step.get("name") for step in steps(content, job)]


def step(content: str, name: str, job: str = "test") -> Any:
    return next(s for s in steps(content, job) if s.get("name") == name)


def owned(result: YamlReconciliation) -> str:
    return encode_yaml_baseline(cast(dict[str, Any], result.baseline))


def reasons(result: YamlReconciliation) -> list[ConflictReason]:
    return [conflict.reason for conflict in result.conflicts]


def keys(conflict: MergeConflict) -> tuple[str, ...]:
    return conflict.location.keys


def test_new_file_is_verbatim_and_repeat_is_a_noop():
    desired = ci("pytest", "codecov")
    first = run(None, desired)
    assert first.content == desired
    assert not first.conflicts
    repeat = run(first.content, desired, first)
    assert repeat.content == desired
    assert repeat.baseline == first.baseline
    assert not repeat.conflicts


def test_local_additions_survive_an_update():
    desired = ci("pytest")
    first = run(None, desired)
    local = (
        first.content.replace(
            '          enable-cache: true\n          python-version: "3.14"\n',
            '          enable-cache: true\n          python-version: "3.14"\n'
            "          cache-dependency-glob: uv.lock\n",
        )
        .replace(
            "      - name: Run tests\n",
            "      - name: Start services\n        run: docker compose up -d\n\n"
            "      - name: Run tests\n",
        )
        .replace("on:\n", "on:\n  workflow_dispatch:\n")
        + "\n  docs:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo docs\n"
    )
    result = run(local, desired.replace(SETUP_UV, BUMPED_UV), first)
    assert not result.conflicts
    content = result.content
    assert step(content, "Install uv")["uses"] == BUMPED_UV
    assert step(content, "Install uv", "lint")["uses"] == BUMPED_UV
    assert step(content, "Install uv")["with"]["cache-dependency-glob"] == "uv.lock"
    assert names(content) == [
        "Checkout",
        "Install uv",
        "Install dependencies",
        "Start services",
        "Run tests",
    ]
    assert "workflow_dispatch" in load(content)["on"]
    assert steps(content, "docs") == [{"run": "echo docs"}]


def test_changed_action_ref_is_kept_silently_and_converges():
    pinned = "actions/checkout@0123456789abcdef0123456789abcdef01234567"
    desired = ci("pytest")
    first = run(None, desired)
    local = first.content.replace("actions/checkout@v7", f"{pinned} # v7")
    bumped = desired.replace("actions/checkout@v7", "actions/checkout@v8")
    result = run(local, bumped, first)
    assert not result.conflicts
    assert result.content == local
    assert step(owned(result), "Checkout")["uses"] == ("actions/checkout@v7")
    renovated = first.content.replace("actions/checkout@v7", "actions/checkout@v8")
    converged = run(renovated, bumped, first)
    assert converged.content == renovated
    assert step(owned(converged), "Checkout")["uses"] == ("actions/checkout@v8")


def test_changed_action_is_an_ordinary_conflict():
    desired = ci("pytest")
    first = run(None, desired)
    local = first.content.replace("actions/checkout@v7", "my-org/checkout@v1", 1)
    result = run(
        local, desired.replace("actions/checkout@v7", "actions/checkout@v8"), first
    )
    assert reasons(result) == [ConflictReason.DIVERGED]
    assert keys(result.conflicts[0]) == ("jobs", "lint", "steps", "Checkout", "uses")
    assert step(result.content, "Checkout", "lint")["uses"] == "my-org/checkout@v1"
    assert step(result.content, "Checkout")["uses"] == "actions/checkout@v8"


def test_turning_codecov_off_removes_unedited_upload_steps():
    first = run(None, ci("pytest", "codecov"))
    result = run(first.content, ci("pytest"), first)
    assert not result.conflicts
    assert result.content == ci("pytest")


def test_retracting_an_edited_step_keeps_it_with_a_conflict():
    first = run(None, ci("pytest", "codecov"))
    local = first.content.replace(
        "          fail_ci_if_error: true", "          fail_ci_if_error: false"
    )
    result = run(local, ci("pytest"), first)
    assert reasons(result) == [ConflictReason.RETRACTED]
    assert keys(result.conflicts[0]) == (
        "jobs",
        "test",
        "steps",
        "Upload coverage to Codecov",
    )
    assert names(result.content)[-2:] == ["Run tests", "Upload coverage to Codecov"]
    assert step(result.content, "Run tests")["run"] == "uv run pytest"
    overwritten = run(local, ci("pytest"), first, overwrite=True)
    assert overwritten.content == ci("pytest")
    assert not overwritten.conflicts


def test_turning_codecov_on_inserts_steps_after_run_tests():
    first = run(None, ci("pytest"))
    local = first.content + "\n      - name: Upload artifacts\n        run: echo mine\n"
    result = run(local, ci("pytest", "codecov"), first)
    assert not result.conflicts
    assert names(result.content)[-4:] == [
        "Run tests",
        "Upload coverage to Codecov",
        "Upload test analytics to Codecov",
        "Upload artifacts",
    ]


def test_switching_to_a_matrix_updates_steps_in_place():
    first = run(None, ci("pytest", "codecov"))
    desired = ci("pytest", "codecov", systems=("Linux", "MacOS"))
    result = run(first.content, desired, first)
    assert not result.conflicts
    # Semantically identical; a changed scalar keeps the local quote style.
    assert load(result.content) == load(desired)
    assert list(load(result.content)["jobs"]["test"]) == list(
        load(desired)["jobs"]["test"]
    )


def test_matrix_edits_conflict_only_on_their_own_list():
    desired = ci("pytest", systems=("Linux", "MacOS"), python="3.13")
    first = run(None, desired)
    local = first.content.replace(
        'python-version: ["3.13", "3.14"]', 'python-version: ["3.14"]'
    )
    changed = ci("pytest", systems=("Linux", "MacOS", "Windows"), python="3.12")
    result = run(local, changed, first)
    assert reasons(result) == [ConflictReason.DIVERGED]
    assert keys(result.conflicts[0])[-1] == "python-version"
    matrix = load(result.content)["jobs"]["test"]["strategy"]["matrix"]
    assert matrix["python-version"] == ["3.14"]
    assert matrix["os"] == ["ubuntu-latest", "macos-latest", "windows-latest"]


def test_duplicate_step_names_hold_that_job_only():
    desired = ci("pytest")
    first = run(None, desired)
    local = first.content.replace(
        "      - name: Run tests\n",
        "      - name: Run tests\n        run: echo first\n\n      - name: Run tests\n",
    )
    result = run(local, desired.replace(SETUP_UV, BUMPED_UV), first)
    [conflict] = result.conflicts
    assert conflict.reason is ConflictReason.DUPLICATE_IDENTITY
    assert keys(conflict) == ("jobs", "test")
    assert step(result.content, "Install uv")["uses"] == SETUP_UV
    assert step(result.content, "Install uv", "lint")["uses"] == BUMPED_UV


def test_existing_unowned_job_is_never_grafted_into():
    local = "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo mine\n"
    result = run(local, ci("pytest"))
    assert steps(result.content) == [{"run": "echo mine"}]
    assert "Run Ruff Linter" in names(result.content, "lint")
    unowned = [c for c in result.conflicts if c.reason is ConflictReason.UNOWNED]
    assert ("jobs", "test") in [keys(c) for c in unowned]


def test_shared_anchor_blocks_only_the_shared_edit():
    desired = ci("pytest")
    first = run(None, desired)
    local = first.content.replace(
        f"uses: {SETUP_UV}", f"uses: &uv {SETUP_UV}", 1
    ).replace(f"uses: {SETUP_UV}", "uses: *uv")
    result = run(local, desired.replace(SETUP_UV, BUMPED_UV), first)
    assert ConflictReason.SHARED_STRUCTURE in reasons(result)
    assert "&uv" in result.content
    assert "*uv" in result.content


def test_indentless_file_keeps_its_style():
    desired = ci("pytest")
    first = run(None, desired)
    local = (
        first.content.replace("\n      - ", "\n    - ")
        .replace("\n        ", "\n      ")
        .replace("\n          ", "\n        ")
    )
    result = run(local, desired.replace(SETUP_UV, BUMPED_UV), first)
    assert not result.conflicts
    assert result.content == local.replace(SETUP_UV, BUMPED_UV)


def test_deleted_file_and_deleted_job_stay_deleted():
    desired = ci("pytest")
    first = run(None, desired)
    bumped = desired.replace(SETUP_UV, BUMPED_UV)
    gone = run(None, bumped, first)
    assert gone.content == ""
    assert ConflictReason.DELETED_ANCESTOR in reasons(gone)
    without_lint = first.content.split("  test:\n")[0].split("  lint:\n")[0] + (
        "  test:\n" + first.content.split("  test:\n")[1]
    )
    silent = run(without_lint, desired, first)
    assert silent.content == without_lint
    assert not silent.conflicts
    changed = run(without_lint, bumped, first)
    assert "lint" not in load(changed.content)["jobs"]
    assert step(changed.content, "Install uv")["uses"] == BUMPED_UV
    assert [keys(c)[:2] for c in changed.conflicts] == [("jobs", "lint")]


@pytest.mark.parametrize("overwrite", [False, True])
def test_release_workflow_merges_by_job_and_step(overwrite):
    desired = generate_release_workflow()
    first = run(None, desired, target=RELEASE_WORKFLOW_TARGET)
    local = first.content.replace(
        '              - "v*"\n', '              - "v*"\n          workflow_dispatch:\n'
    ) + (
        "\n      - name: Create GitHub release\n"
        "        uses: softprops/action-gh-release@v2\n"
    )
    result = run(
        local,
        desired.replace(SETUP_UV, BUMPED_UV),
        first,
        target=RELEASE_WORKFLOW_TARGET,
        overwrite=overwrite,
    )
    assert not result.conflicts
    assert result.content == local.replace(SETUP_UV, BUMPED_UV)
