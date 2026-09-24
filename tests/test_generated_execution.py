"""Three-way generated-file and append-region acceptance tests."""

from pathlib import Path

import pytest

from protostar.appends import append_marker_blocks
from protostar.config import UserConfig
from protostar.errors import ConfigurationError
from protostar.executor import SystemExecutor
from protostar.intent import AppendContribution
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.merge import ConflictReason, LineSpan, MergeLocation, ResolutionChoice
from protostar.models import ExecutionResult
from protostar.sync_state import FilePolicy, deserialize_state

ARTIFACTS = ["Dockerfile", "justfile"]


def run(mocker, setup):
    intent = EnvironmentManifest()
    intent.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(intent, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    setup(executor)
    executor.execute()
    return executor


def apply_generated(mocker, target, value, strategy=CollisionStrategy.MERGE):
    """Runs one execution that generates ``value`` at ``target``."""

    def setup(executor):
        executor.manifest.collision_strategy = strategy
        mocker.patch(
            "protostar.reconciliation.Reconciliation._write_ci_workflow",
            lambda decisions: decisions._write_generated(target, value),
        )

    return run(mocker, setup)


def baseline_of(path):
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    return next(r for r in state.files if r.path == path).baseline


@pytest.mark.parametrize("path", ARTIFACTS)
def test_generated_lifecycle(tmp_path, monkeypatch, mocker, path):
    monkeypatch.chdir(tmp_path)
    target = Path(path)

    def apply(value):
        return apply_generated(mocker, target, value)

    apply("v1\r\n")
    state = Path(".protostar.lock.toml")
    assert baseline_of(path) == "v1\r\n"
    initial = state.read_bytes()
    assert not apply("v1\r\n").journal.touched_paths
    assert state.read_bytes() == initial
    apply("v2\n")
    assert target.read_bytes() == b"v2\n"
    baseline = state.read_bytes()
    target.write_bytes(b"local\r\n")
    assert not apply("v2\n").diagnostics
    conflict = apply("v3\n")
    assert conflict.diagnostics[0].conflict.location.file == path
    assert conflict.diagnostics[0].conflict.location.lines == LineSpan(1, 1)
    assert target.read_bytes() == b"local\r\n"
    assert state.read_bytes() == baseline
    target.write_bytes(b"v3\n")
    converged = apply("v3\n")
    assert target.as_posix() not in converged.journal.touched_paths
    assert baseline_of(path) == "v3\n"
    target.unlink()
    assert not apply("v3\n").journal.touched_paths
    assert apply("v4\n").diagnostics
    assert not target.exists()
    state.unlink()
    target.write_bytes(b"v4\n")
    apply("v4\n")
    assert not deserialize_state(state.read_text()).files
    target.write_bytes(b"// commented JSONC\n{}")
    assert apply("v5\n").diagnostics
    assert target.read_bytes() == b"// commented JSONC\n{}"


GENERATED = "build:\n    uv build\n\ntest:\n    uv run pytest\n\nlint:\n    uv run ruff check .\n"


def test_local_edits_merge_with_generator_updates(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    apply_generated(mocker, target, GENERATED)
    target.write_text(GENERATED.replace("uv build", "uv build --sdist"))
    update = GENERATED.replace("ruff check .", "ruff check --fix .")

    result = apply_generated(mocker, target, update)

    assert not result.diagnostics
    assert target.read_text() == update.replace("uv build", "uv build --sdist")
    # The baseline is the generated text, so the local edit stays a local edit.
    assert baseline_of("justfile") == update
    assert not apply_generated(mocker, target, update).journal.touched_paths


def test_overlapping_edits_keep_the_whole_file_and_report_lines(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    apply_generated(mocker, target, GENERATED)
    edited = GENERATED.replace("uv run pytest", "uv run pytest -x").replace(
        "uv build", "uv build --sdist"
    )
    target.write_text(edited)
    state = Path(".protostar.lock.toml").read_bytes()
    update = GENERATED.replace("uv run pytest", "uv run pytest -q").replace(
        "ruff check .", "ruff check --fix ."
    )

    result = apply_generated(mocker, target, update)

    # The clean lint hunk is not applied alone: the file is kept whole.
    assert target.read_text() == edited
    assert Path(".protostar.lock.toml").read_bytes() == state
    (event,) = [d for d in result.diagnostics if d.conflict]
    assert event.conflict.reason is ConflictReason.DIVERGED
    assert event.conflict.location.lines == LineSpan(5, 1)
    assert event.message == "Preserving local contribution in justfile: line 5."
    payload = ExecutionResult(
        result.journal.created_paths,
        result.journal.mutated_paths,
        tuple(result.diagnostics),
    ).to_dict()
    assert payload["diagnostics"][0]["conflict"]["lines"] == {"start": 5, "count": 1}
    # Resolving the conflict by hand lets the next run finish the update.
    target.write_text(update.replace("uv build", "uv build --sdist"))
    assert not apply_generated(mocker, target, update).diagnostics
    assert baseline_of("justfile") == update


def test_crlf_checkout_merges_in_its_own_newline_style(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    apply_generated(mocker, target, GENERATED)
    # A checkout with core.autocrlf rewrites every line ending, not the content.
    target.write_bytes(GENERATED.replace("\n", "\r\n").encode())
    update = GENERATED.replace("uv build", "uv build --wheel")

    assert not apply_generated(mocker, target, update).diagnostics
    assert target.read_bytes() == update.replace("\n", "\r\n").encode()
    assert baseline_of("justfile") == update


def test_undecodable_local_bytes_are_kept(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    apply_generated(mocker, target, GENERATED)
    target.write_bytes(b"\xff\xfe not utf-8\n")

    result = apply_generated(mocker, target, GENERATED + "extra:\n    true\n")

    assert target.read_bytes() == b"\xff\xfe not utf-8\n"
    (event,) = [d for d in result.diagnostics if d.conflict]
    assert event.conflict.location.lines is None
    assert event.conflict.reason is ConflictReason.DIVERGED


def test_overwrite_replaces_local_edits(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    apply_generated(mocker, target, GENERATED)
    target.write_text("local\n")
    update = GENERATED + "extra:\n    true\n"

    apply_generated(mocker, target, update, CollisionStrategy.OVERWRITE)

    assert target.read_text() == update
    assert baseline_of("justfile") == update


@pytest.mark.parametrize("suffix", [".py", ".md", ".css", ".js"])
def test_region_lifecycle_and_surrounding_bytes(suffix):
    path = Path("file" + suffix)
    first = append_marker_blocks(
        "prefix\r\n", [AppendContribution("test:id", "v1")], path
    )
    original = first.content + "suffix\r\n"
    changed = append_marker_blocks(
        original, [AppendContribution("test:id", "v2")], path, baselines=first.baselines
    )
    assert changed.content.startswith("prefix\r\n")
    assert changed.content.endswith("suffix\r\n")
    assert "v2" in changed.content
    assert "v1" not in changed.content
    edited = changed.content.replace("v2", "local")
    repeat = append_marker_blocks(
        edited, [AppendContribution("test:id", "v2")], path, baselines=changed.baselines
    )
    assert repeat.content == edited
    assert not repeat.conflicts
    conflict = append_marker_blocks(
        edited, [AppendContribution("test:id", "v3")], path, baselines=changed.baselines
    )
    assert conflict.content == edited
    # The one payload line conflicts: line 4, after the prefix, the blank
    # separator, and the begin marker.
    ((location, reason),) = [(c.location, c.reason) for c in conflict.conflicts]
    assert location == MergeLocation(
        path.as_posix(), identity="test:id", lines=LineSpan(4, 1)
    )
    assert reason is ConflictReason.DIVERGED
    assert conflict.baselines == changed.baselines
    converged = append_marker_blocks(
        changed.content.replace("v2", "v3"),
        [AppendContribution("test:id", "v3")],
        path,
        baselines=changed.baselines,
    )
    assert converged.baselines != changed.baselines
    deleted = append_marker_blocks(
        "prefix\r\nsuffix\r\n",
        [AppendContribution("test:id", "v3")],
        path,
        baselines=converged.baselines,
    )
    assert deleted.content == "prefix\r\nsuffix\r\n"
    assert not deleted.conflicts
    unowned = append_marker_blocks(
        first.content, [AppendContribution("test:id", "v2")], path
    )
    assert not unowned.baselines
    ((location, reason),) = [(c.location, c.reason) for c in unowned.conflicts]
    assert location == MergeLocation(path.as_posix(), identity="test:id")
    assert reason is ConflictReason.UNOWNED
    restored = append_marker_blocks(
        edited,
        [AppendContribution("test:id", "v3")],
        path,
        overwrite=True,
        baselines=changed.baselines,
    )
    assert "v3" in restored.content


def region(content, identity="test:id"):
    return AppendContribution(identity, content)


def test_region_edits_merge_with_desired_updates():
    path = Path("AGENTS.md")
    first = append_marker_blocks("# Notes\n", [region("a\nb\nc")], path)
    edited = first.content.replace("\na\n", "\nA\n")

    result = append_marker_blocks(
        edited, [region("a\nb\nC")], path, baselines=first.baselines
    )

    assert not result.conflicts
    assert "\nA\nb\nC\n" in result.content
    desired = append_marker_blocks("# Notes\n", [region("a\nb\nC")], path)
    assert result.baselines == desired.baselines


def test_crlf_file_regions_still_update():
    path = Path("AGENTS.md")
    first = append_marker_blocks("# Notes\n", [region("a\nb")], path)
    checkout = first.content.replace("\n", "\r\n")

    result = append_marker_blocks(
        checkout, [region("a\nB")], path, baselines=first.baselines
    )

    assert not result.conflicts
    assert result.content == checkout.replace("\r\nb\r\n", "\r\nB\r\n")


def test_region_conflicts_are_numbered_in_the_final_file():
    path = Path("AGENTS.md")
    first = append_marker_blocks(
        "# Notes\n", [region("one", "test:upper"), region("x\ny", "test:lower")], path
    )
    edited = first.content.replace("\nx\n", "\nlocal\n")

    # The lower region is reconciled first, then the upper one grows by two
    # lines, so the lower conflict must be numbered after that growth.
    result = append_marker_blocks(
        edited,
        [region("remote\ny", "test:lower"), region("one\ntwo\nthree", "test:upper")],
        path,
        baselines=first.baselines,
    )

    (conflict,) = result.conflicts
    lines = result.content.splitlines()
    assert conflict.location.identity == "test:lower"
    span = conflict.location.lines
    assert span is not None
    assert lines[span.start - 1] == "local"
    assert span.count == 1


def test_seed_and_deleted_region_file(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    def setup(e):
        e.manifest.filesystem.add_file_injection("seed.py", "invalid Python seed")
        e.manifest.filesystem.add_region(".envrc", "v1", identity="test:old")

    run(mocker, setup)
    Path("seed.py").unlink()
    Path(".envrc").unlink()

    def revision(e):
        setup(e)
        e.manifest.filesystem.add_file_injection("new.py", "new")
        e.manifest.filesystem.add_region(".envrc", "v2", identity="test:new")

    run(mocker, revision)
    assert not Path("seed.py").exists()
    assert not Path(".envrc").exists()
    assert Path("new.py").read_text() == "new"


def test_generated_and_regions_rollback(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region(".envrc", "v1", identity="test:region")

    run(mocker, setup)
    paths = [Path("justfile"), Path(".envrc"), Path(".protostar.lock.toml")]
    for path in paths:
        path.chmod(0o640)
    originals = {p: (p.read_bytes(), p.stat().st_mode) for p in paths}

    def revision(e):
        e.manifest.filesystem.add_region(".envrc", "v2", identity="test:region")
        mocker.patch.object(
            e,
            "_write_justfile",
            side_effect=lambda: e._write_generated(Path("justfile"), "changed"),
        )
        mocker.patch.object(
            e, "_write_state", side_effect=ConfigurationError("failure")
        )

    with pytest.raises(ConfigurationError):
        run(mocker, revision)
    assert {p: (p.read_bytes(), p.stat().st_mode) for p in paths} == originals


def test_real_producer_wiring_and_noop(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.reconciliation.generate_justfile", return_value="just v1\n")
    mocker.patch(
        "protostar.reconciliation.generate_dockerfile", return_value="docker v1\n"
    )

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.tooling.wants_docker = True
        e.manifest.filesystem.add_region(".envrc", "v1", identity="test:region")

    run(mocker, setup)
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    text = [r for r in state.files if r.policy is FilePolicy.TEXT]
    assert {r.path for r in text} == set(ARTIFACTS)
    for record in text:
        assert record.baseline == Path(record.path).read_bytes().decode()
    original = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert not run(mocker, setup).journal.touched_paths
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == original
    mocker.patch("protostar.reconciliation.generate_justfile", return_value="just v2\n")
    run(mocker, setup)
    assert Path("justfile").read_text() == "just v2\n"


def test_edited_dockerfile_still_appends_ignore_patterns(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path("Dockerfile").write_bytes(b"user docker\r\n")
    Path(".dockerignore").write_text("# custom\nmy-pattern\n")

    def setup(e):
        e.manifest.tooling.wants_docker = True
        e.manifest.filesystem.vcs_ignores.add("new-pattern")

    run(mocker, setup)
    assert Path("Dockerfile").read_bytes() == b"user docker\r\n"
    assert Path(".dockerignore").read_text().startswith("# custom\nmy-pattern\n")
    assert "new-pattern" in Path(".dockerignore").read_text()


@pytest.mark.parametrize(
    "content",
    ["# region: protostar 12345678", "# endregion: protostar 12345678"],
)
def test_desired_region_cannot_inject_boundaries(content):
    with pytest.raises(ConfigurationError):
        append_marker_blocks("", [AppendContribution("test:id", content)], Path("x.py"))


def justfile_regions(mocker, base, recipe):
    """Runs one execution generating ``base`` with a template recipe region."""
    mocker.patch("protostar.reconciliation.generate_justfile", return_value=base)

    def configure(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region(
            "justfile", recipe, identity="template:recipes"
        )

    return run(mocker, configure)


def test_generated_justfile_with_regions_merges(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    justfile_regions(mocker, "base v1\n", "recipe v1")
    assert not justfile_regions(mocker, "base v1\n", "recipe v1").journal.touched_paths
    target = Path("justfile")
    target.write_bytes(target.read_bytes().replace(b"base v1", b"user base"))

    justfile_regions(mocker, "base v1\n", "recipe v2")

    assert "user base" in target.read_text()
    assert "recipe v2" in target.read_text()
    region = append_marker_blocks(
        "base v1\n", [AppendContribution("template:recipes", "recipe v2")], target
    )
    record = next(
        r
        for r in deserialize_state(Path(".protostar.lock.toml").read_text()).files
        if r.path == "justfile"
    )
    assert record.baseline == region.content
    assert record.regions[0].baseline == region.baselines["template:recipes"]
    target.unlink()
    justfile_regions(mocker, "base v1\n", "recipe v3")
    assert not target.exists()


def test_regions_update_while_the_generated_file_conflicts(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    justfile_regions(mocker, "base v1\n", "recipe v1")
    target = Path("justfile")
    target.write_bytes(target.read_bytes().replace(b"base v1", b"user base"))

    result = justfile_regions(mocker, "base v2\n", "recipe v2")

    # The base line conflicts, so the file is not merged, but the unedited
    # region is owned on its own and still updates.
    assert [d.conflict.location.lines for d in result.diagnostics if d.conflict] == [
        LineSpan(1, 1)
    ]
    assert "user base" in target.read_text()
    assert "recipe v2" in target.read_text()
    record = next(
        r
        for r in deserialize_state(Path(".protostar.lock.toml").read_text()).files
        if r.path == "justfile"
    )
    assert record.baseline is not None
    assert "base v1" in record.baseline
    assert "recipe v1" in record.baseline


def test_unowned_generated_file_can_manage_new_region(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path("justfile").write_text("user recipes\n")

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region(
            "justfile", "managed recipe", identity="template:recipes"
        )

    run(mocker, setup)
    original = Path("justfile").read_bytes()
    run(mocker, setup)
    assert Path("justfile").read_bytes() == original
    record = deserialize_state(Path(".protostar.lock.toml").read_text()).files[0]
    assert record.policy is FilePolicy.REGIONS
    assert record.baseline is None
    assert record.regions
    Path("justfile").unlink()
    run(mocker, setup)
    assert not Path("justfile").exists()


def test_generated_region_omission_never_prunes(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.reconciliation.generate_justfile", return_value="base\n")

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region("justfile", "keep", identity="test:omitted")

    run(mocker, setup)
    original = Path("justfile").read_bytes()
    baseline = Path(".protostar.lock.toml").read_bytes()
    mocker.patch(
        "protostar.reconciliation.generate_justfile", return_value="changed base\n"
    )
    run(mocker, lambda e: setattr(e.manifest.tooling, "wants_just", True))
    assert Path("justfile").read_bytes() == original
    assert Path(".protostar.lock.toml").read_bytes() == baseline


def test_agents_md_region_merges_updates_and_protects_edits(
    tmp_path, monkeypatch, mocker
):
    from protostar.models import InitRequest
    from protostar.modules import AgentsModule, BootstrapModule
    from protostar.orchestrator import Orchestrator

    class Commands(BootstrapModule):
        def __init__(self, *typecheck):
            self.typecheck = list(typecheck)

        @property
        def name(self):
            return "Commands"

        def build(self, manifest):
            manifest.tooling.just_lint_commands.append("uv run lint-tool .")
            manifest.tooling.just_typecheck_commands.extend(self.typecheck)

    def apply(*typecheck):
        manifest = Orchestrator(
            [AgentsModule(), Commands(*typecheck)],
            UserConfig(),
            InitRequest(collision_strategy=CollisionStrategy.MERGE),
        ).plan()
        executor = SystemExecutor(manifest, UserConfig())
        mocker.patch.object(executor, "_check_ide_extensions")
        executor.execute()
        return executor

    monkeypatch.chdir(tmp_path)
    target = Path("AGENTS.md")
    target.write_text("# Team notes\n\nUse feature branches.\n")

    apply()
    assert target.read_text().startswith("# Team notes\n\nUse feature branches.\n\n")
    assert "uv run lint-tool ." in target.read_text()
    assert "AGENTS.md" not in apply().journal.touched_paths

    apply("uv run check-types .")
    assert "uv run check-types ." in target.read_text()
    assert "Use feature branches." in target.read_text()

    target.write_text(target.read_text().replace("check-types", "local-types"))
    conflict = apply("uv run check-types src")
    assert conflict.diagnostics[0].conflict.location.file == "AGENTS.md"
    assert "local-types" in target.read_text()


def test_review_reports_line_conflicts_and_preserved_edits(
    tmp_path, monkeypatch, mocker, capsys
):
    from protostar.cli.reviews import render_review
    from protostar.preparation import prepare_review

    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    mocker.patch("protostar.reconciliation.generate_justfile", return_value=GENERATED)

    def desired():
        manifest = EnvironmentManifest()
        manifest.tooling.wants_just = True
        return manifest

    run(mocker, lambda e: setattr(e.manifest.tooling, "wants_just", True))
    # A CRLF checkout is not a local edit.
    target.write_bytes(GENERATED.replace("\n", "\r\n").encode())
    assert not prepare_review(desired(), UserConfig()).preserved
    target.write_text(GENERATED.replace("uv run pytest", "uv run pytest -x"))
    (preserved,) = prepare_review(desired(), UserConfig()).preserved
    assert preserved.location.file == "justfile"
    assert not preserved.deleted

    mocker.patch(
        "protostar.reconciliation.generate_justfile",
        return_value=GENERATED.replace("uv run pytest", "uv run pytest -q"),
    )
    review = prepare_review(desired(), UserConfig())

    assert not review.edits
    assert not review.preserved
    (conflict,) = review.conflicts
    assert review.to_dict()["conflicts"] == [
        {
            "id": conflict.id,
            "file": "justfile",
            "keys": [],
            "identity": None,
            "lines": {"start": 5, "count": 1},
            "reason": "diverged",
            "choices": ["local", "desired", "both"],
            "sides": {
                "text": True,
                "base": {"value": "    uv run pytest\n"},
                "local": {"value": "    uv run pytest -x\n"},
                "desired": {"value": "    uv run pytest -q\n"},
            },
        }
    ]
    render_review(review)
    assert (
        f"Conflict {conflict.id}: justfile line 5: diverged; "
        "resolve with local, desired, both."
    ) in capsys.readouterr().out


@pytest.mark.parametrize(
    ("choice", "line"),
    [
        (ResolutionChoice.LOCAL, "    uv run pytest -x\n"),
        (ResolutionChoice.DESIRED, "    uv run pytest -q\n"),
        (ResolutionChoice.BOTH, "    uv run pytest -x\n    uv run pytest -q\n"),
    ],
)
def test_resolved_line_conflict_is_applied_and_owns_the_update(
    tmp_path, monkeypatch, mocker, choice, line
):
    from protostar.preparation import prepare_review

    monkeypatch.chdir(tmp_path)
    target = Path("justfile")
    mocker.patch("protostar.reconciliation.generate_justfile", return_value=GENERATED)

    def desired():
        manifest = EnvironmentManifest()
        manifest.tooling.wants_just = True
        return manifest

    run(mocker, lambda e: setattr(e.manifest.tooling, "wants_just", True))
    target.write_text(GENERATED.replace("uv run pytest\n", "uv run pytest -x\n"))
    update = GENERATED.replace("uv run pytest\n", "uv run pytest -q\n")
    mocker.patch("protostar.reconciliation.generate_justfile", return_value=update)
    (conflict,) = prepare_review(desired(), UserConfig()).conflicts

    review = prepare_review(desired(), UserConfig(), resolutions={conflict.id: choice})
    executor = SystemExecutor(desired(), UserConfig(), review=review)
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()

    assert not review.conflicts
    assert [c.id for c in review.resolved] == [conflict.id]
    assert target.read_text() == GENERATED.replace("    uv run pytest\n", line)
    assert baseline_of("justfile") == update
    assert not prepare_review(desired(), UserConfig()).conflicts


def test_resolved_region_conflict_is_numbered_in_the_final_file():
    path = Path("AGENTS.md")
    first = append_marker_blocks(
        "# Notes\n", [region("one", "test:upper"), region("x\ny", "test:lower")], path
    )
    edited = first.content.replace("\nx\n", "\nlocal\n")
    payloads = [region("remote\ny", "test:lower"), region("one\ntwo", "test:upper")]
    (conflict,) = append_marker_blocks(
        edited, payloads, path, baselines=first.baselines
    ).conflicts

    result = append_marker_blocks(
        edited,
        payloads,
        path,
        baselines=first.baselines,
        resolutions={conflict.id: ResolutionChoice.DESIRED},
    )

    assert not result.conflicts
    (resolved,) = result.resolved
    assert resolved.id == conflict.id
    assert "remote\ny" in result.content
    assert result.baselines["test:lower"].count("remote") == 1
    span = resolved.location.lines
    assert span is not None
    # Numbered after the upper region grew, it points at the settled line.
    assert result.content.splitlines()[span.start - 1] == "remote"


def test_region_preserved_deviations_ignore_newline_style(
    tmp_path, monkeypatch, mocker
):
    from protostar.preparation import prepare_review

    monkeypatch.chdir(tmp_path)

    def desired():
        manifest = EnvironmentManifest()
        manifest.filesystem.add_region(".envrc", "export A=1", identity="test:env")
        return manifest

    run(
        mocker,
        lambda e: e.manifest.filesystem.add_region(
            ".envrc", "export A=1", identity="test:env"
        ),
    )
    target = Path(".envrc")
    applied = target.read_text()

    target.write_bytes(applied.replace("\n", "\r\n").encode())
    assert not prepare_review(desired(), UserConfig()).preserved
    target.write_text(applied.replace("A=1", "A=2"))
    (edited,) = prepare_review(desired(), UserConfig()).preserved
    assert (edited.location.identity, edited.deleted) == ("test:env", False)
    target.write_text("# no region\n")
    (deleted,) = prepare_review(desired(), UserConfig()).preserved
    assert (deleted.location.identity, deleted.deleted) == ("test:env", True)
