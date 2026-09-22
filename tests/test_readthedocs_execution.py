""".readthedocs.yaml merges without subprocesses: one build, never grafted onto another."""

from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.documents import readthedocs
from protostar.executor import SystemExecutor
from protostar.intent import StructuredFormat
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.merge import ConflictReason, MergeConflict, MergeLocation
from protostar.modules import ReadTheDocsModule
from protostar.sync_state import FilePolicy, deserialize_state
from protostar.yaml_ast import decode_yaml_baseline

TARGET = Path(readthedocs.TARGET)
STATE = Path(".protostar.lock.toml")
JOBS_HELD = MergeConflict(
    MergeLocation(readthedocs.TARGET, ("build", "jobs")), ConflictReason.UNOWNED
)
STRATEGIES = pytest.mark.parametrize(
    "strategy", [CollisionStrategy.MERGE, CollisionStrategy.OVERWRITE]
)

# The shape of the Sphinx example Read the Docs documents.
SPHINX = """# Read the Docs configuration
version: 2

build:
  os: ubuntu-24.04
  tools:
    python: "3.12"

sphinx:
  configuration: docs/conf.py

python:
  install:
    - requirements: docs/requirements.txt
"""


def scaffold() -> str:
    intent = EnvironmentManifest()
    ReadTheDocsModule().build(intent)
    [contribution] = intent.filesystem.structured[readthedocs.TARGET]
    return contribution.content


def run(mocker, content=None, strategy=CollisionStrategy.MERGE):
    intent = EnvironmentManifest(collision_strategy=strategy)
    intent.filesystem.add_structured(
        readthedocs.TARGET,
        content or scaffold(),
        producer="module:ReadTheDocsModule",
        document_format=StructuredFormat.YAML,
    )
    executor = SystemExecutor(intent, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    process.assert_not_called()
    return executor


def conflicts(executor):
    return [d.conflict for d in executor.diagnostics if d.conflict is not None]


def local():
    return decode_yaml_baseline(TARGET.read_text())


def jobs(document):
    return document["build"]["jobs"]


def test_scaffold_is_created_verbatim_and_owned(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    assert TARGET.read_text() == scaffold()
    [record] = deserialize_state(STATE.read_text()).files
    assert record.policy is FilePolicy.YAML
    initial = (TARGET.read_bytes(), STATE.read_bytes())
    repeated = run(mocker)
    assert not repeated.journal.touched_paths
    assert (TARGET.read_bytes(), STATE.read_bytes()) == initial


def test_existing_configuration_gains_the_build_and_keeps_its_settings(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    original = (
        "# Read the Docs configuration\n"
        "version: 2\n\n"
        "build:\n"
        "  os: ubuntu-24.04\n"
        "  tools:\n"
        '    python: "3.12"\n\n'
        "search:\n"
        "  ranking:\n"
        "    api/*: -1\n"
    )
    TARGET.write_text(original)
    executor = run(mocker)
    assert not conflicts(executor)
    assert "# Read the Docs configuration" in TARGET.read_text()
    assert local() == {
        **decode_yaml_baseline(scaffold()),
        "search": {"ranking": {"api/*": -1}},
    }


def test_sync_updates_unedited_settings_and_keeps_user_edits(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.write_text(
        TARGET.read_text()
        .replace("os: ubuntu-24.04", "os: ubuntu-lts-latest")
        .replace(
            '      - cp -r site/* "$READTHEDOCS_OUTPUT/html/"\n',
            '      - cp -r site/* "$READTHEDOCS_OUTPUT/html/"\n'
            "    post_build:\n"
            "      - echo done\n",
        )
    )
    changed = (
        scaffold()
        .replace("os: ubuntu-24.04", "os: ubuntu-26.04")
        .replace("uv sync --only-group docs", "uv sync --frozen --only-group docs")
    )
    executor = run(mocker, changed)
    document = local()
    # The user's OS choice diverged from Protostar's new default and is kept.
    assert conflicts(executor) == [
        MergeConflict(
            MergeLocation(readthedocs.TARGET, ("build", "os")), ConflictReason.DIVERGED
        )
    ]
    assert document["build"]["os"] == "ubuntu-lts-latest"
    assert jobs(document)["install"] == jobs(decode_yaml_baseline(changed))["install"]
    assert jobs(document)["post_build"] == ["echo done"]


def test_settings_protostar_stops_generating_are_retracted(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    without_pre_create = scaffold().replace(
        "    pre_create_environment:\n      - pip install uv\n", ""
    )
    executor = run(mocker, without_pre_create)
    assert not conflicts(executor)
    assert "pre_create_environment" not in jobs(local())
    assert local() == decode_yaml_baseline(without_pre_create)


def test_edited_retracted_setting_is_kept_with_a_conflict(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.write_text(
        TARGET.read_text().replace("- pip install uv", "- pip install uv==0.9.0")
    )
    executor = run(
        mocker,
        scaffold().replace("    pre_create_environment:\n      - pip install uv\n", ""),
    )
    assert conflicts(executor) == [
        MergeConflict(
            MergeLocation(
                readthedocs.TARGET, ("build", "jobs", "pre_create_environment")
            ),
            ConflictReason.RETRACTED,
        )
    ]
    assert jobs(local())["pre_create_environment"] == ["pip install uv==0.9.0"]


@STRATEGIES
@pytest.mark.parametrize(
    "sibling", [".readthedocs.yml", "readthedocs.yaml", "readthedocs.yml"]
)
def test_configuration_under_another_name_is_merged_in_place(
    tmp_path, monkeypatch, mocker, sibling, strategy
):
    monkeypatch.chdir(tmp_path)
    Path(sibling).write_text("# mine\nversion: 2\nformats:\n  - pdf\n")
    executor = run(mocker, strategy=strategy)
    assert not TARGET.exists()
    assert not conflicts(executor)
    document = decode_yaml_baseline(Path(sibling).read_text())
    assert document == {**decode_yaml_baseline(scaffold()), "formats": ["pdf"]}
    assert "# mine" in Path(sibling).read_text()
    [record] = deserialize_state(STATE.read_text()).files
    assert record.path == sibling


def test_existing_sphinx_build_under_another_name_keeps_its_steps(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    sibling = Path(".readthedocs.yml")
    sibling.write_text(SPHINX)
    executor = run(mocker)
    assert sibling.read_text() == SPHINX
    assert conflicts(executor) == [
        MergeConflict(
            MergeLocation(sibling.as_posix(), ("build", "jobs")), ConflictReason.UNOWNED
        )
    ]


@STRATEGIES
def test_custom_build_commands_are_never_combined_with_jobs(
    tmp_path, monkeypatch, mocker, strategy
):
    monkeypatch.chdir(tmp_path)
    original = (
        "version: 2\n"
        "build:\n"
        "  os: ubuntu-24.04\n"
        "  tools:\n"
        '    python: "3.12"\n'
        "  commands:\n"
        "    - make html\n"
    )
    TARGET.write_text(original)
    executor = run(mocker, strategy=strategy)
    # Read the Docs rejects build.jobs next to build.commands.
    assert TARGET.read_text() == original
    assert conflicts(executor) == [JOBS_HELD]


@STRATEGIES
@pytest.mark.parametrize(
    "setting",
    [
        "sphinx:\n  configuration: docs/conf.py\n",
        "mkdocs:\n  configuration: mkdocs.yml\n",
        "python:\n  install:\n    - requirements: docs/requirements.txt\n",
        "conda:\n  environment: environment.yml\n",
    ],
)
def test_default_build_steps_are_not_replaced(
    tmp_path, monkeypatch, mocker, setting, strategy
):
    monkeypatch.chdir(tmp_path)
    original = (
        'version: 2\nbuild:\n  os: ubuntu-24.04\n  tools:\n    python: "3.12"\n'
        + setting
    )
    TARGET.write_text(original)
    executor = run(mocker, strategy=strategy)
    assert TARGET.read_text() == original
    assert conflicts(executor) == [JOBS_HELD]


def test_existing_sphinx_build_keeps_its_steps(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    TARGET.write_text(SPHINX)
    executor = run(mocker)
    assert TARGET.read_text() == SPHINX
    assert conflicts(executor) == [JOBS_HELD]
    assert not deserialize_state(STATE.read_text()).files


def test_build_taken_over_after_scaffold_is_quiet_until_jobs_change(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    taken_over = (
        'version: 2\nbuild:\n  os: ubuntu-24.04\n  tools:\n    python: "3.12"\n'
        "  commands:\n    - make html\n"
    )
    TARGET.write_text(taken_over)
    quiet = run(mocker)
    assert not conflicts(quiet)
    assert TARGET.read_text() == taken_over
    changed = scaffold().replace(
        "uv sync --only-group docs", "uv sync --frozen --only-group docs"
    )
    for strategy in (CollisionStrategy.MERGE, CollisionStrategy.OVERWRITE):
        executor = run(mocker, changed, strategy)
        assert conflicts(executor) == [JOBS_HELD]
        assert TARGET.read_text() == taken_over


def test_held_jobs_already_matching_withhold_nothing(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    # A configuration copied from a Protostar project, plus a default-step setting.
    original = scaffold() + "python:\n  install:\n    - requirements: docs/extra.txt\n"
    TARGET.write_text(original)
    executor = run(mocker)
    assert not conflicts(executor)
    assert TARGET.read_text() == original


def test_deleted_document_stays_deleted(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.unlink()
    executor = run(mocker)
    assert not TARGET.exists()
    assert not conflicts(executor)


def test_overwrite_restores_edited_settings_and_keeps_foreign_ones(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.write_text(
        TARGET.read_text().replace('python: "3.12"', 'python: "3.11"')
        + "formats:\n  - pdf\n"
    )
    run(mocker, strategy=CollisionStrategy.OVERWRITE)
    document = local()
    assert document["build"]["tools"]["python"] == "3.12"
    assert document["formats"] == ["pdf"]
