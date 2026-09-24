"""Documents are edited wherever their tool reads them, without subprocesses."""

from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.documents import codecov, pre_commit, readthedocs, zensical
from protostar.errors import ConfigurationError, StaleReviewError
from protostar.executor import SystemExecutor
from protostar.intent import StructuredFormat
from protostar.manifest import CollisionStrategy, EnvironmentManifest, HookRunner
from protostar.merge import ConflictReason, MergeConflict, MergeLocation
from protostar.modules import CodecovModule, ReadTheDocsModule, ZensicalModule
from protostar.preparation import prepare_review
from protostar.registry import RemoteHook, ResolvedHookRevision
from protostar.sync_state import FilePolicy, FileState, PinProvenance, deserialize_state
from protostar.yaml_ast import decode_yaml_baseline

STATE = Path("protostar.lock")
RTD = Path(readthedocs.TARGET)
RTD_YML = Path(".readthedocs.yml")
CI = Path(".github/workflows/ci.yml")
CI_YAML = Path(".github/workflows/ci.yaml")
HOOKS = Path(pre_commit.TARGET)
HOOKS_YML = Path(".pre-commit-config.yml")


def duplicate(path, keys=()):
    return MergeConflict(MergeLocation(path, keys), ConflictReason.DUPLICATE_IDENTITY)


def module_intent(module, strategy=CollisionStrategy.MERGE, content=None):
    intent = EnvironmentManifest(collision_strategy=strategy)
    module.build(intent)
    # These runs exercise document placement; installing tools would need uv.
    intent.dependencies.dev_dependencies.clear()
    if content is not None:
        [(target, [contribution])] = intent.filesystem.structured.items()
        intent.filesystem.structured[target] = [
            type(contribution)(
                contribution.producer, content, format=contribution.format
            )
        ]
    return intent


def rtd(content=None, strategy=CollisionStrategy.MERGE):
    return module_intent(ReadTheDocsModule(), strategy, content)


def scaffold(module):
    intent = EnvironmentManifest()
    module.build(intent)
    [(_, [contribution])] = intent.filesystem.structured.items()
    return contribution.content


def run(intent, mocker, revisions=None):
    if revisions is not None:
        mocker.patch(
            "protostar.executor.resolve_hook_revisions", return_value=revisions
        )
    executor = SystemExecutor(intent, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    process.assert_not_called()
    return executor


def conflicts(executor):
    return [d.conflict for d in executor.diagnostics if d.conflict is not None]


def records():
    return {r.path: r for r in deserialize_state(STATE.read_text()).files}


def load(path):
    return decode_yaml_baseline(Path(path).read_text())


# --- Renames ---------------------------------------------------------------


def test_renamed_document_is_followed_in_both_directions(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(rtd(), mocker)
    RTD.rename(RTD_YML)
    changed = scaffold(ReadTheDocsModule()).replace(
        "uv sync --only-group docs", "uv sync --frozen --only-group docs"
    )
    executor = run(rtd(changed), mocker)
    assert not conflicts(executor)
    assert not RTD.exists()
    assert "--frozen" in RTD_YML.read_text()
    assert set(records()) == {RTD_YML.as_posix()}

    RTD_YML.rename(RTD)
    executor = run(rtd(changed), mocker)
    assert not conflicts(executor)
    assert not executor.journal.touched_paths - {STATE.as_posix()}
    assert set(records()) == {RTD.as_posix()}


def test_edits_made_before_a_rename_are_kept(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(rtd(), mocker)
    RTD_YML.write_text(RTD.read_text().replace("ubuntu-24.04", "ubuntu-lts-latest"))
    RTD.unlink()
    changed = scaffold(ReadTheDocsModule()).replace("3.13", "3.14")
    executor = run(rtd(changed), mocker)
    assert not conflicts(executor)
    document = load(RTD_YML)
    assert document["build"]["os"] == "ubuntu-lts-latest"
    assert document["build"]["tools"]["python"] == "3.14"


# --- Competing copies ------------------------------------------------------


def test_competing_copy_next_to_the_owned_file_is_reported(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(rtd(), mocker)
    RTD_YML.write_text("version: 2\n")
    changed = scaffold(ReadTheDocsModule()).replace("3.13", "3.14")
    executor = run(rtd(changed), mocker)
    assert conflicts(executor) == [duplicate(RTD_YML.as_posix())]
    assert RTD_YML.read_text() == "version: 2\n"
    assert '"3.14"' in RTD.read_text()


@pytest.mark.parametrize(
    "strategy", [CollisionStrategy.MERGE, CollisionStrategy.OVERWRITE]
)
def test_two_unowned_configurations_are_both_left_alone(
    tmp_path, monkeypatch, mocker, strategy
):
    monkeypatch.chdir(tmp_path)
    RTD.write_text("version: 2\n")
    RTD_YML.write_text("version: 2\n")
    executor = run(rtd(strategy=strategy), mocker)
    assert conflicts(executor) == [
        duplicate(RTD.as_posix()),
        duplicate(RTD_YML.as_posix()),
    ]
    assert RTD.read_text() == RTD_YML.read_text() == "version: 2\n"
    assert not records()


def test_codecov_root_configuration_is_merged_and_shadowing_is_reported(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    Path("codecov.yml").write_text("codecov:\n  require_ci_to_pass: true\n")
    executor = run(module_intent(CodecovModule()), mocker)
    assert not conflicts(executor)
    assert not Path(codecov.TARGET).exists()
    document = load(Path("codecov.yml"))
    assert document["codecov"] == {"require_ci_to_pass": True}
    assert document["coverage"]["precision"] == 2

    # Codecov reads the root file first, so a new canonical file is a copy.
    Path(codecov.TARGET).parent.mkdir()
    Path(codecov.TARGET).write_text("codecov: {}\n")
    executor = run(module_intent(CodecovModule()), mocker)
    assert conflicts(executor) == [duplicate(codecov.TARGET)]
    assert set(records()) == {"codecov.yml"}


def site_intent():
    intent = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    intent.filesystem.add_structured(
        zensical.TARGET, scaffold(ZensicalModule()), producer="module:ZensicalModule"
    )
    return intent


def test_owned_zensical_site_reports_an_mkdocs_configuration(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(site_intent(), mocker)
    Path("mkdocs.yml").write_text("site_name: Docs\n")
    executor = run(site_intent(), mocker)
    assert conflicts(executor) == [duplicate("mkdocs.yml")]
    assert Path(zensical.TARGET).exists()


# --- Workflows -------------------------------------------------------------


def ci_intent():
    intent = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    intent.tooling.wants_ci = True
    return intent


def test_existing_workflow_with_the_other_extension_is_merged(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    CI_YAML.parent.mkdir(parents=True)
    CI_YAML.write_text(
        "name: CI\non:\n  workflow_dispatch: {}\njobs:\n  mine:\n    runs-on: x\n"
    )
    executor = run(ci_intent(), mocker)
    assert not conflicts(executor)
    assert not CI.exists()
    jobs = load(CI_YAML)["jobs"]
    assert "mine" in jobs
    assert "test" in jobs
    assert set(records()) == {CI_YAML.as_posix()}


def test_renamed_workflow_is_followed_and_a_second_workflow_is_left_alone(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(ci_intent(), mocker)
    CI.rename(CI_YAML)
    executor = run(ci_intent(), mocker)
    assert not conflicts(executor)
    assert not CI.exists()
    assert set(records()) == {CI_YAML.as_posix()}

    # GitHub runs both files, so a new ci.yml is another workflow, not a copy.
    CI.write_text("name: Mine\non: [push]\njobs: {}\n")
    executor = run(ci_intent(), mocker)
    assert not conflicts(executor)
    assert CI.read_text() == "name: Mine\non: [push]\njobs: {}\n"
    assert set(records()) == {CI_YAML.as_posix()}


# --- Pre-commit ------------------------------------------------------------


REVISIONS = tuple(
    ResolvedHookRevision(hook, "v1.0.0", PinProvenance.REGISTRY) for hook in RemoteHook
)


def hooks_intent(runner):
    intent = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    intent.tooling.hook_runner = runner
    return intent


def test_prek_edits_a_yml_configuration_and_moves_its_pins(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(hooks_intent(HookRunner.PREK), mocker, REVISIONS)
    HOOKS.rename(HOOKS_YML)
    # An identical offline answer must not relabel the pins that moved.
    fallback = tuple(
        ResolvedHookRevision(pin.hook, pin.revision, PinProvenance.FALLBACK)
        for pin in REVISIONS
    )
    run(hooks_intent(HookRunner.PREK), mocker, fallback)
    assert not HOOKS.exists()
    state = deserialize_state(STATE.read_text())
    assert {r.path for r in state.files} == {HOOKS_YML.as_posix()}
    assert state.hook_pins
    assert {pin.path for pin in state.hook_pins} == {HOOKS_YML.as_posix()}
    assert {pin.provenance for pin in state.hook_pins} == {PinProvenance.REGISTRY}


def test_pre_commit_reports_a_yml_configuration_it_would_ignore(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    HOOKS_YML.write_text("repos: []\n")
    executor = run(hooks_intent(HookRunner.PRE_COMMIT), mocker, REVISIONS)
    assert conflicts(executor) == [
        MergeConflict(MergeLocation(pre_commit.TARGET), ConflictReason.UNOWNED)
    ]
    assert not HOOKS.exists()
    assert HOOKS_YML.read_text() == "repos: []\n"


def test_prek_leaves_a_toml_configuration_alone(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path("prek.toml").write_text("repos = []\n")
    executor = run(hooks_intent(HookRunner.PREK), mocker, REVISIONS)
    assert conflicts(executor) == [
        MergeConflict(MergeLocation(pre_commit.TARGET), ConflictReason.UNOWNED)
    ]
    assert not HOOKS.exists()


# --- Planning, review, and state -------------------------------------------


def test_collision_check_and_dry_run_see_the_file_under_its_other_name(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    RTD_YML.write_text("version: 2\n")
    intent = rtd()
    assert intent.colliding_files() == {RTD_YML}
    assert RTD_YML in intent.written_files()
    assert RTD not in intent.written_files()


def test_review_captures_competing_copies(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(rtd(), mocker)
    RTD_YML.write_text("version: 2\n")
    review = prepare_review(rtd(), UserConfig())
    assert review.conflicts == (duplicate(RTD_YML.as_posix()),)
    RTD_YML.unlink()
    executor = SystemExecutor(rtd(), UserConfig(), review=review)
    with pytest.raises(StaleReviewError):
        executor.execute()


def test_state_validates_a_baseline_recorded_under_another_name():
    baseline = "repos:\n  - repo: a\n  - repo: a\n"
    with pytest.raises(ConfigurationError):
        FileState(HOOKS_YML.as_posix(), FilePolicy.YAML, baseline)


def test_append_regions_are_rejected_under_every_name():
    intent = EnvironmentManifest()
    with pytest.raises(ConfigurationError, match="Append regions are unsupported"):
        intent.filesystem.add_region(RTD_YML.as_posix(), "x", identity="x")


def test_yaml_contributions_are_declared_by_target():
    intent = EnvironmentManifest()
    with pytest.raises(ConfigurationError, match="Unsupported structured YAML"):
        intent.filesystem.add_structured(
            RTD_YML.as_posix(),
            "version: 2\n",
            producer="test",
            document_format=StructuredFormat.YAML,
        )


# --- Hooks that validate a document ----------------------------------------


def rtd_with_hooks():
    intent = rtd()
    intent.tooling.hook_runner = HookRunner.PREK
    return intent


def rtd_hook_files():
    local = next(repo for repo in load(HOOKS)["repos"] if repo["repo"] == "local")
    return next(h for h in local["hooks"] if h["id"] == "check-readthedocs")["files"]


def test_document_hook_names_the_file_protostar_creates(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(rtd_with_hooks(), mocker, REVISIONS)
    assert rtd_hook_files() == r"^\.readthedocs\.yaml$"


def test_document_hook_names_an_adopted_alias(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    RTD_YML.write_text("version: 2\n")
    run(rtd_with_hooks(), mocker, REVISIONS)
    assert rtd_hook_files() == r"^\.readthedocs\.yml$"


def test_document_hook_follows_a_renamed_document(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(rtd_with_hooks(), mocker, REVISIONS)
    RTD.rename(RTD_YML)
    executor = run(rtd_with_hooks(), mocker, REVISIONS)
    assert not conflicts(executor)
    assert rtd_hook_files() == r"^\.readthedocs\.yml$"


def test_document_hook_matches_every_candidate_while_the_document_is_held(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    RTD.write_text("version: 2\n")
    RTD_YML.write_text("version: 2\n")
    run(rtd_with_hooks(), mocker, REVISIONS)
    assert rtd_hook_files() == (
        r"^(\.readthedocs\.yaml|\.readthedocs\.yml|readthedocs\.yaml|readthedocs\.yml)$"
    )
