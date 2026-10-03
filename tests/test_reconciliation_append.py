"""Contracts of appending structured contributions and regions, and of migrations."""

import hashlib
import sys
from pathlib import Path

import pytest

from protostar.appends import append_marker_blocks
from protostar.config import UserConfig
from protostar.documents import pyproject_layout
from protostar.errors import ConfigurationError, FileSystemError
from protostar.intent import (
    AppendContribution,
    StructuredContribution,
    StructuredFormat,
    TemplateOrigin,
    TemplateReference,
    region_tag,
)
from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from protostar.merge import ConflictReason, MergeConflict, MergeLocation
from protostar.migrations import Migration, MigrationOutcome, MigrationStep, Rename
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import ReviewWorkspace
from protostar.sync_state import (
    FilePolicy,
    FileState,
    RegionState,
    SyncState,
    encode_toml_baseline,
)

OWNED = "[owned]\nanswer = 42\n"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


@pytest.fixture
def reconciliation(workspace):
    return Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )


def declare(reconciliation, path, content=OWNED):
    reconciliation.manifest.filesystem.add_structured(path, content, producer="test")


def accepted(workspace, path):
    content = workspace.contents.get(path)
    return None if content is None else content.decode()


def warning(file, reason):
    return DiagnosticEvent(
        DiagnosticPhase.EXECUTOR,
        f"Kept your version of {file}: it conflicts with the update.",
        Severity.WARNING,
        conflict=MergeConflict(MergeLocation(file), reason),
    )


# ---- structured TOML contributions ---- #


def test_a_yaml_contribution_does_not_stop_the_documents_after_it(
    reconciliation, workspace
):
    reconciliation.manifest.filesystem.add_structured(
        ".readthedocs.yaml",
        "{}\n",
        producer="test",
        document_format=StructuredFormat.YAML,
    )
    declare(reconciliation, "custom.toml")

    reconciliation._append_files()

    assert accepted(workspace, "custom.toml") == OWNED


def test_a_contribution_path_is_rendered_with_the_project_context(
    reconciliation, workspace
):
    reconciliation.manifest.metadata["project_name"] = "demo"
    reconciliation.manifest.filesystem.structured["conf/<% PROJECT_NAME %>.toml"] = [
        StructuredContribution("test", OWNED)
    ]

    reconciliation._append_files()

    assert accepted(workspace, "conf/demo.toml") == OWNED


def test_a_held_document_does_not_stop_the_documents_after_it(
    reconciliation, workspace, monkeypatch
):
    declare(reconciliation, "first.toml")
    declare(reconciliation, "second.toml")
    locate = reconciliation._locate
    monkeypatch.setattr(
        reconciliation,
        "_locate",
        lambda path, policy: None if path == "first.toml" else locate(path, policy),
    )

    reconciliation._append_files()

    assert accepted(workspace, "first.toml") is None
    assert accepted(workspace, "second.toml") == OWNED


def test_a_document_whose_settings_sit_outside_its_root_table_is_kept_and_reported(
    reconciliation, workspace
):
    Path("zensical.toml").write_text("[other]\nx = 1\n", encoding="utf-8")
    declare(reconciliation, "zensical.toml", '[project]\nsite_name = "docs"\n')
    declare(reconciliation, "custom.toml")

    reconciliation._append_files()

    assert accepted(workspace, "zensical.toml") is None
    assert reconciliation.diagnostics == [
        warning("zensical.toml", ConflictReason.UNOWNED)
    ]
    assert accepted(workspace, "custom.toml") == OWNED


def test_a_deleted_project_file_is_not_recreated_by_a_contribution(
    reconciliation, workspace
):
    reconciliation._preserve_deleted_pyproject = True
    declare(reconciliation, "pyproject.toml", '[project]\nname = "app"\n')
    declare(reconciliation, "custom.toml")

    reconciliation._append_files()

    assert accepted(workspace, "pyproject.toml") is None
    assert reconciliation.diagnostics == [
        warning("pyproject.toml", ConflictReason.DELETED_ANCESTOR)
    ]
    assert accepted(workspace, "custom.toml") == OWNED


def test_an_owned_project_file_the_user_deleted_stays_deleted(
    reconciliation, workspace
):
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState(
            "pyproject.toml",
            FilePolicy.TOML,
            encode_toml_baseline({"project": {"name": "app"}}),
        )
    )
    declare(reconciliation, "pyproject.toml", "[tool.ruff]\nline-length = 99\n")

    reconciliation._append_files()

    assert accepted(workspace, "pyproject.toml") is None
    assert [event.conflict.reason for event in reconciliation.diagnostics] == [
        ConflictReason.DELETED_ANCESTOR
    ]


def test_an_owned_document_is_updated_without_proposals(reconciliation, workspace):
    Path("custom.toml").write_text(OWNED, encoding="utf-8")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState(
            "custom.toml",
            FilePolicy.TOML,
            encode_toml_baseline({"owned": {"answer": 42}}),
        )
    )
    declare(reconciliation, "custom.toml", OWNED + "new = 1\n")

    reconciliation._append_files()

    assert accepted(workspace, "custom.toml") == OWNED + "new = 1\n"
    assert reconciliation.proposals == []


def test_a_layout_that_could_not_be_applied_is_reported_with_its_reason(
    reconciliation, workspace, monkeypatch
):
    monkeypatch.setattr(
        pyproject_layout, "format_sections", lambda _: "[foreign]\nanswer = 42\n"
    )
    declare(reconciliation, "pyproject.toml", '[project]\nname = "app"\n')

    reconciliation._append_files()

    assert [(e.severity, e.message) for e in reconciliation.diagnostics] == [
        (
            Severity.WARNING,
            "Left pyproject.toml unformatted: "
            "AST Parity mismatch during pyproject.toml formatting.",
        )
    ]


def test_a_failed_toml_write_names_the_operation_path_and_cause(
    reconciliation, monkeypatch
):
    declare(reconciliation, "custom.toml")
    error = OSError("disk full")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(reconciliation.fs, "write_text", fail)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._append_files()

    assert caught.value.operation == "mutate configuration AST"
    assert caught.value.path == "custom.toml"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


PYTHON = '[project]\nname = "app"\nrequires-python = ">=3.12"\n'


@pytest.mark.parametrize(
    ("local", "desired", "dirty"),
    [
        # The pin moves, so the resolver's answer is stale.
        ('[project]\nname = "app"\nrequires-python = ">=3.9"\n', PYTHON, True),
        # The pin appears.
        ('[project]\nname = "app"\n', PYTHON, True),
        # The pin stays while other settings change.
        (PYTHON, PYTHON + 'description = "A project."\n', False),
        # No project table at all, then a pin.
        ("[tool.x]\ny = 1\n", PYTHON, True),
    ],
)
def test_a_moved_python_requirement_marks_the_resolver_output_stale(
    reconciliation, workspace, local, desired, dirty
):
    Path("pyproject.toml").write_text(local, encoding="utf-8")
    declare(reconciliation, "pyproject.toml", desired)
    reconciliation.manifest.collision_strategy = CollisionStrategy.OVERWRITE

    reconciliation._append_files()

    assert accepted(workspace, "pyproject.toml") is not None
    assert reconciliation._resolution_dirty is dirty


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
def test_a_located_document_is_checked_against_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "custom.toml").write_text(OWNED, encoding="utf-8")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / "custom.toml").symlink_to(root / "custom.toml")
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )

    located = reconciliation._locate("custom.toml", FilePolicy.TOML)

    assert located is not None
    assert located.path == Path("custom.toml")


# ---- regions ---- #

NOTES = Path("notes.md")


def framed(content, identity="template:notes", target=NOTES):
    """Returns a file's text holding one region, and the baseline that records it."""
    result = append_marker_blocks("", [AppendContribution(identity, content)], target)
    return result.content, result.baselines[identity]


def region_record(
    identity="template:notes", content="desired\n", policy=FilePolicy.REGIONS
):
    text, baseline = framed(content, identity)
    return FileState(
        NOTES.as_posix(),
        policy,
        text if policy is FilePolicy.TEXT else None,
        regions=(RegionState(region_tag(identity), identity, baseline),),
    )


def region_of(reconciliation, content="desired\n", identity="template:notes"):
    reconciliation.manifest.filesystem.add_region(
        NOTES.as_posix(), content, identity=identity
    )


def test_a_region_path_is_rendered_with_the_project_context(reconciliation, workspace):
    reconciliation.manifest.metadata["project_name"] = "demo"
    reconciliation.manifest.filesystem.regions["<% PROJECT_NAME %>.md"] = [
        AppendContribution("template:notes", "desired\n")
    ]

    reconciliation._append_files()

    assert (
        accepted(workspace, "demo.md") == framed("desired\n", target=Path("demo.md"))[0]
    )


def test_a_region_in_a_held_document_keeps_the_ownership_it_has(
    reconciliation, workspace
):
    # Two other copies exist, so no one knows which the tool reads.
    for held in ("docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"):
        Path(held).parent.mkdir(exist_ok=True)
        Path(held).write_text("mine\n", encoding="utf-8")
    owned = FileState(
        "CONTRIBUTING.md",
        FilePolicy.REGIONS,
        regions=(RegionState(region_tag("template:x"), "template:x", "framed"),),
    )
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(owned)
    reconciliation.manifest.filesystem.add_region(
        "CONTRIBUTING.md", "desired\n", identity="template:x"
    )

    reconciliation._append_files()

    assert reconciliation.candidate_state.files == (owned,)
    assert workspace.contents == {}


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
def test_a_region_target_is_checked_against_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "notes.md").write_text("mine\n", encoding="utf-8")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / "notes.md").symlink_to(root / "notes.md")
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )
    region_of(reconciliation)

    reconciliation._append_files()

    assert "desired" in workspace.contents["notes.md"].decode()


@pytest.mark.parametrize("policy", [FilePolicy.TOML, FilePolicy.SEED])
def test_a_region_target_owned_under_another_policy_is_a_configuration_error(
    reconciliation, policy
):
    record = (
        FileState("notes.md", policy, encode_toml_baseline({}))
        if policy is FilePolicy.TOML
        else FileState("notes.md", policy, digest="a" * 64)
    )
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)
    region_of(reconciliation)

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._append_files()

    assert str(caught.value) == "Conflicting region ownership policy."
    assert caught.value.hint == "Keep the tracked file policy unchanged."


def test_overwrite_replaces_an_edited_region_and_merge_keeps_the_edit(
    tmp_path, monkeypatch
):
    text, _ = framed("desired\n")
    edited = text.replace("desired", "my edit")
    outcomes = {}
    for strategy in (CollisionStrategy.MERGE, CollisionStrategy.OVERWRITE):
        monkeypatch.chdir(tmp_path)
        workspace = ReviewWorkspace(tmp_path)
        NOTES.write_text(edited, encoding="utf-8")
        reconciliation = Reconciliation(
            EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
        )
        reconciliation.manifest.collision_strategy = strategy
        reconciliation.candidate_state = reconciliation.candidate_state.with_file(
            region_record()
        )
        region_of(reconciliation, "updated\n")

        reconciliation._append_files()

        outcomes[strategy] = accepted(workspace, "notes.md")

    assert outcomes[CollisionStrategy.OVERWRITE] == framed("updated\n")[0]
    assert outcomes[CollisionStrategy.MERGE] is None


def test_a_retracted_region_is_cut_from_a_generated_files_text_and_the_file_stays_owned(
    reconciliation, workspace
):
    text, _ = framed("desired\n")
    NOTES.write_text(text, encoding="utf-8")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        region_record(policy=FilePolicy.TEXT)
    )

    reconciliation._append_files()

    [record] = reconciliation.candidate_state.files
    assert record.policy is FilePolicy.TEXT
    assert record.regions == ()
    assert record.baseline == ""
    assert accepted(workspace, "notes.md") == ""


def test_a_region_still_in_the_file_is_not_cut_from_its_text_baseline(
    reconciliation, workspace
):
    text, baseline = framed("desired\n")
    NOTES.write_text(text, encoding="utf-8")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        region_record(policy=FilePolicy.TEXT)
    )
    region_of(reconciliation, "desired\n")

    reconciliation._append_files()

    [record] = reconciliation.candidate_state.files
    assert record.baseline == text
    assert [r.baseline for r in record.regions] == [baseline]


def test_a_file_whose_regions_are_all_retracted_is_no_longer_owned(
    reconciliation, workspace
):
    text, _ = framed("desired\n")
    NOTES.write_text(text, encoding="utf-8")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        region_record()
    )
    other = FileState("other.txt", FilePolicy.TEXT, "kept\n")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(other)

    reconciliation._append_files()

    assert reconciliation.candidate_state.files == (other,)


def test_a_failed_region_write_names_the_operation_path_and_cause(
    reconciliation, monkeypatch
):
    region_of(reconciliation)
    error = OSError("disk full")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(reconciliation.fs, "write_text", fail)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._append_files()

    assert caught.value.operation == "append configurations block"
    assert caught.value.path == "notes.md"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


# ---- migrations ---- #


def template(version, migrated=None):
    return TemplateReference(
        TemplateOrigin.LOCAL, "tmpl", "a" * 64, version=version, migrated=migrated
    )


def migrating(workspace, migration, *, committed, current):
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )
    reconciliation.manifest.migrations = (migration,)
    reconciliation._committed = SyncState("0", committed)
    reconciliation.candidate_state = SyncState("0", current)
    return reconciliation


def test_a_template_cannot_move_back_across_an_applied_migration(workspace):
    reconciliation = migrating(
        workspace,
        Migration("2.0.0"),
        committed=template("2.0.0", migrated="2.0.0"),
        current=template("1.5.0"),
    )

    with pytest.raises(ConfigurationError, match=r"would undo its 2\.0\.0 migration"):
        reconciliation._migrate()


def test_migration_paths_are_rendered_with_the_project_context(workspace):
    digest = hashlib.sha256(b"seed").hexdigest()
    for name in ("demo.old", "demo.gone"):
        Path(name).write_bytes(b"seed")
    reconciliation = migrating(
        workspace,
        Migration(
            "2.0.0",
            rename=(Rename("<% PROJECT_NAME %>.old", "<% PROJECT_NAME %>.new"),),
            remove=("<% PROJECT_NAME %>.gone",),
        ),
        committed=template("1.0.0"),
        current=template("2.0.0"),
    )
    reconciliation.manifest.metadata["project_name"] = "demo"
    for name in ("demo.old", "demo.gone"):
        reconciliation.candidate_state = reconciliation.candidate_state.with_file(
            FileState(name, FilePolicy.SEED, digest=digest)
        )

    reconciliation._migrate()

    assert reconciliation.migration_steps == [
        MigrationStep("2.0.0", "demo.old", "demo.new", MigrationOutcome.MOVED),
        MigrationStep("2.0.0", "demo.gone", None, MigrationOutcome.REMOVED),
    ]
    assert workspace.contents == {"demo.new": b"seed"}
    assert workspace.removed == {"demo.old", "demo.gone"}


# ---- generated files that hold regions ---- #


def generated_text_record(identity="template:notes", body="region body\n"):
    """A generated file whose text holds one region, and the record owning both."""
    text, baseline = framed(body, identity)
    return text, FileState(
        NOTES.as_posix(),
        FilePolicy.TEXT,
        "generated\n" + text,
        regions=(RegionState(region_tag(identity), identity, baseline),),
    )


@pytest.mark.parametrize(
    "record",
    [
        FileState("notes.md", FilePolicy.TOML, encode_toml_baseline({})),
        FileState("notes.md", FilePolicy.SEED, digest="a" * 64),
    ],
)
def test_a_generated_file_owned_under_another_policy_is_a_configuration_error(
    reconciliation, record
):
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._write_generated(NOTES, "generated\n")

    assert str(caught.value) == "Conflicting generated ownership policy."
    assert caught.value.hint == "Keep the tracked file policy unchanged."


def test_a_file_owned_only_for_regions_is_left_to_the_region_step(
    reconciliation, workspace
):
    text, _ = framed("desired\n")
    NOTES.write_text(text, encoding="utf-8")
    record = region_record()
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    reconciliation._write_generated(NOTES, "generated\n")

    assert workspace.contents == {}
    assert reconciliation.candidate_state.files == (record,)


def test_a_region_declared_in_a_generated_file_is_rendered_with_the_project_context(
    reconciliation, workspace
):
    reconciliation.manifest.metadata["project_name"] = "demo"
    region_of(reconciliation, "name: <% PROJECT_NAME %>\n")

    reconciliation._write_generated(NOTES, "generated\n")

    assert "name: demo\n" in accepted(workspace, "notes.md")


def test_a_region_already_in_the_generated_text_is_replaced_by_the_declared_one(
    reconciliation, workspace
):
    old, _ = framed("old\n")
    region_of(reconciliation, "new\n")

    reconciliation._write_generated(NOTES, "generated\n" + old)

    assert accepted(workspace, "notes.md") == "generated\n" + framed("new\n")[0]


def test_an_owned_file_the_user_deleted_stays_deleted_unless_overwritten(
    reconciliation, workspace
):
    record = region_record()
    region_of(reconciliation)
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    reconciliation._write_generated(NOTES, "generated\n")

    assert workspace.contents == {}
    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            "Kept your version of notes.md: it conflicts with the update.",
            Severity.WARNING,
            conflict=MergeConflict(
                MergeLocation("notes.md"), ConflictReason.DELETED_ANCESTOR
            ),
        )
    ]

    reconciliation.manifest.collision_strategy = CollisionStrategy.OVERWRITE
    reconciliation._write_generated(NOTES, "generated\n")

    assert "generated\n" in accepted(workspace, "notes.md")


def test_an_undecodable_file_cannot_have_its_omitted_regions_retracted(
    reconciliation, workspace
):
    _, record = generated_text_record()
    NOTES.write_bytes(b"caf\xe9\n")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._write_generated(NOTES, "generated v2\n")

    assert caught.value.operation == "read generated file"
    assert caught.value.path == "notes.md"
    assert isinstance(caught.value.original, UnicodeDecodeError)


def test_a_generated_file_deleted_with_an_omitted_region_stays_deleted(
    reconciliation, workspace
):
    _, record = generated_text_record()
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    reconciliation._write_generated(NOTES, "generated v2\n")

    assert workspace.contents == {}
    assert [d.conflict.reason for d in reconciliation.diagnostics] == [
        ConflictReason.DELETED_ANCESTOR
    ]
    [owned] = reconciliation.candidate_state.files
    assert (owned.baseline, owned.regions) == ("generated\n", ())


def test_an_omitted_region_leaves_the_record_when_the_generated_text_conflicts(
    reconciliation, workspace
):
    text, record = generated_text_record()
    other = FileState("other.txt", FilePolicy.TEXT, "kept\n")
    NOTES.write_text("mine\n" + text, encoding="utf-8")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(other)

    reconciliation._write_generated(NOTES, "generated v2\n")

    # The retraction went through, and the record forgot the region it cut.
    assert accepted(workspace, "notes.md") == "mine\n"
    [_, owned] = reconciliation.candidate_state.files
    assert (owned.path, owned.baseline, owned.regions) == (
        "notes.md",
        "generated\n",
        (),
    )
