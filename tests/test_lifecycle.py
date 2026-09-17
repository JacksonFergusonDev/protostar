"""Focused acceptance for read-only project lifecycle inspection."""

import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from protostar.cli import main, schema, ui
from protostar.cli.reviews import review_payload
from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import ConfigurationError, InvalidUsageError, ProtostarError
from protostar.executor import SystemExecutor
from protostar.lifecycle import inspect_project
from protostar.manifest import EnvironmentManifest
from protostar.recipe import RecipeIntent, Tool, establish_recipe


def source_text(value):
    return (
        '[files]\n".github/renovate.json" = \'' + json.dumps({"value": value}) + "'\n"
    )


@pytest.fixture
def project(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.toml"
    source.write_text(source_text("original"))
    blueprint = TemplateBlueprint.load(str(source))
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    recipe = replace(recipe, fallback=tuple((tool, False) for tool in Tool))
    manifest = EnvironmentManifest(
        template_reference=blueprint.reference, recipe=recipe
    )
    manifest.filesystem.add_file_injection(
        ".github/renovate.json", json.dumps({"value": "original"})
    )
    manifest.filesystem.add_structured(
        "pyproject.toml", '[project]\nname = "demo"\n', producer="seed"
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    mocker.patch.object(
        executor.process_runner, "run", side_effect=AssertionError("process")
    )
    executor.execute()
    mocker.patch("protostar.lifecycle.resolve_hook_revisions", return_value=())
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess.run"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen"))
    mocker.patch(
        "protostar.config.UserConfig.load",
        side_effect=AssertionError("global defaults"),
    )
    return source


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): (
            p.read_bytes() if p.is_file() else None,
            stat.S_IMODE(p.stat().st_mode),
        )
        for p in root.rglob("*")
    }


def test_inspection_accepted_edits_and_preservation_are_read_only(project):
    project.write_text(source_text("updated") + '"new.txt" = "new\\n"\n')
    before = snapshot(Path.cwd())
    review = inspect_project()
    assert any(
        edit.path == ".github/renovate.json"
        and json.loads(edit.after) == {"value": "updated"}
        for edit in review.edits
    )
    assert snapshot(Path.cwd()) == before
    Path(".github/renovate.json").write_text(json.dumps({"value": "local"}))
    review = inspect_project()
    assert any(c.location.file == ".github/renovate.json" for c in review.conflicts)
    assert not any(e.path == ".github/renovate.json" for e in review.edits)
    assert any(e.path == "new.txt" for e in review.edits)
    project.write_text(source_text("original"))
    review = inspect_project()
    assert any(p.location.file == ".github/renovate.json" for p in review.preserved)
    assert not any(c.location.file == ".github/renovate.json" for c in review.conflicts)
    Path(".github/renovate.json").unlink()
    assert any(p.deleted for p in inspect_project().preserved)


@pytest.mark.parametrize("command", ["status", "diff"])
def test_json_and_human_review_exit_zero_even_with_conflicts(
    project, command, monkeypatch, capsys
):
    Path(".github/renovate.json").write_text(json.dumps({"value": "local"}))
    project.write_text(source_text("remote"))
    monkeypatch.setattr("sys.argv", ["protostar", command, "--json"])
    monkeypatch.setattr(ui, "is_json_mode", False)
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload == review_payload(inspect_project())
    assert payload["status"] == "reviewed"
    assert payload["review"]["conflicts"]
    assert not any(item["path"] == ".github/renovate.json" for item in payload["diffs"])
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", command])
    main()
    assert "Conflict: .github/renovate.json" in capsys.readouterr().out


@pytest.mark.parametrize("target", ["pyproject.toml", ".protostar.lock.toml"])
def test_missing_enrollment_is_actionable(project, target):
    Path(target).unlink()
    with pytest.raises(ConfigurationError) as caught:
        inspect_project()
    assert caught.value.hint is not None
    assert "init --force-merge" in caught.value.hint


def test_identity_change_and_missing_source_fail(project):
    data = Path("pyproject.toml").read_text()
    Path("other.toml").write_text(project.read_text())
    modified = data.replace(
        project.resolve().as_posix(),
        (project.parent / "other.toml").resolve().as_posix(),
    )
    assert modified != data
    Path("pyproject.toml").write_text(modified)
    with pytest.raises(ProtostarError):
        inspect_project()
    Path("pyproject.toml").write_text(data)
    project.unlink()
    with pytest.raises(ProtostarError):
        inspect_project()


def test_capabilities_publish_review_schema():
    from protostar.cli.parser import build_parser

    capabilities = schema._build_capabilities_schema(build_parser())
    assert {"status", "diff"} <= capabilities["commands"].keys()
    assert "sync" in capabilities["commands"]
    assert capabilities["review_schema"]["properties"]["status"]["const"] == "reviewed"


def test_missing_bindings_and_values_are_actionable_and_private(project, monkeypatch):
    import tomlkit

    project.write_text('[files]\n"secret.txt" = "<% CUSTOM %>"\n')
    with pytest.raises(ProtostarError) as caught:
        inspect_project()
    assert caught.value.hint
    data = tomlkit.parse(Path("pyproject.toml").read_text())
    data["tool"]["protostar"]["bindings"] = {"CUSTOM": "LIFECYCLE_TEST_SECRET"}
    Path("pyproject.toml").write_text(tomlkit.dumps(data))
    monkeypatch.delenv("LIFECYCLE_TEST_SECRET", raising=False)
    with pytest.raises(ConfigurationError) as caught:
        inspect_project()
    assert caught.value.hint is not None
    assert "LIFECYCLE_TEST_SECRET" in caught.value.hint
    monkeypatch.setenv("LIFECYCLE_TEST_SECRET", "private-value")
    review = inspect_project()
    assert "private-value" not in __import__(
        "protostar.sync_state", fromlist=["serialize_state"]
    ).serialize_state(review.candidate_state)


@pytest.mark.parametrize("archive_kind", ["zip", "tar"])
def test_remote_archives_are_in_memory_and_reject_unsafe_members(
    tmp_path, mocker, archive_kind
):
    import io
    import tarfile
    import zipfile

    from protostar.errors import SecurityViolationError
    from protostar.network import acquire_inspection_source

    def archive_bytes(name):
        output = io.BytesIO()
        if archive_kind == "zip":
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr(name, "[files]\n")
                archive.writestr("repo/template/example.txt", "hello")
        else:
            with tarfile.open(fileobj=output, mode="w") as archive:
                for path, text in [
                    (name, "[files]\n"),
                    ("repo/template/example.txt", "hello"),
                ]:
                    member = tarfile.TarInfo(path)
                    content = text.encode()
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
        return output.getvalue()

    opener = mocker.Mock()
    mocker.patch("protostar.network._get_opener", return_value=opener)
    opener.open.return_value = io.BytesIO(archive_bytes("repo/protostar.toml"))
    mocker.patch(
        "tempfile.TemporaryDirectory", side_effect=AssertionError("disk acquisition")
    )
    acquired = acquire_inspection_source("https://example.com/source." + archive_kind)
    assert acquired.template_bytes == b"[files]\n"
    assert acquired.files == {"example.txt": "hello"}
    opener.open.return_value = io.BytesIO(archive_bytes("../protostar.toml"))
    with pytest.raises(SecurityViolationError):
        acquire_inspection_source("https://example.com/source." + archive_kind)


def test_registry_frozen_once_and_tasks_reported_without_execution(project, mocker):
    project.write_text(
        'system_tasks = [["untrusted", "system"]]\npost_install_tasks = [["untrusted", "post"]]\n'
        + source_text("original")
    )
    registry = mocker.patch(
        "protostar.lifecycle.resolve_hook_revisions", return_value=()
    )
    review = inspect_project()
    registry.assert_called_once_with()
    assert ("untrusted", "system") in review.initialization_only
    assert ("untrusted", "post") in review.initialization_only


def test_structured_conflict_has_safe_sibling_and_state_only_advancement(
    project, mocker
):
    # Enroll a named TOML producer, then evolve that producer at the same source.
    injection = "[tool.example]\nvalue = 1\n"
    project.write_text("[dev.pyproject]\nexample = " + "'''" + injection + "'''\n")
    manifest = EnvironmentManifest(
        template_reference=TemplateBlueprint.load(str(project)).reference
    )
    assert manifest.template_reference is not None
    manifest.filesystem.add_structured(
        "pyproject.toml",
        injection,
        producer="template:" + manifest.template_reference.identity + ":example",
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    mocker.patch.object(
        executor.process_runner, "run", side_effect=AssertionError("process")
    )
    executor.execute()
    text = Path("pyproject.toml").read_text()
    Path("pyproject.toml").write_text(text.replace("value = 1", "value = 3"))
    project.write_text(
        "[dev.pyproject]\nexample = "
        + "'''"
        + "[tool.example]\nvalue = 2\nsafe = true\n"
        + "'''\n"
    )
    review = inspect_project()
    assert any(
        c.location.keys == ("tool", "example", "value") for c in review.conflicts
    )
    edit = next(e for e in review.edits if e.path == "pyproject.toml")
    assert b"value = 3" in edit.after
    assert b"safe = true" in edit.after
    Path("pyproject.toml").write_text(text.replace("value = 1", "value = 2"))
    project.write_text(
        "[dev.pyproject]\nexample = " + "'''" + "[tool.example]\nvalue = 2\n" + "'''\n"
    )
    review = inspect_project()
    assert review.state_changed
    assert not any(
        b"value = " in e.after for e in review.edits if e.path == "pyproject.toml"
    )


@pytest.mark.parametrize("target", ["pyproject.toml", ".protostar.lock.toml"])
def test_json_failure_envelope_and_no_ancestor_search(
    project, target, monkeypatch, capsys
):
    Path(target).unlink()
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "status", "--json"])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "init --force-merge" in payload["error"]["hint"]
    nested = Path("nested")
    nested.mkdir()
    monkeypatch.chdir(nested)
    with pytest.raises(ConfigurationError, match="recipe is missing"):
        inspect_project()


def test_unified_diff_marks_missing_final_newlines():
    from protostar.cli.reviews import unified_diff
    from protostar.preparation import PreparedEdit

    assert (
        unified_diff(PreparedEdit("example", b"old", b"new")).count(
            "\\ No newline at end of file"
        )
        == 2
    )


def test_source_symlink_is_rejected(project):
    from protostar.errors import UnsupportedFilesystemNodeError

    moved = project.with_name("real.toml")
    project.rename(moved)
    project.symlink_to(moved)
    with pytest.raises(UnsupportedFilesystemNodeError):
        inspect_project()


def invoke_sync(monkeypatch, capsys, *flags, code=0):
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync", "--json", *flags])
    if code:
        with pytest.raises(SystemExit) as caught:
            main()
        assert caught.value.code == code
    else:
        main()
    return json.loads(capsys.readouterr().out)


def test_sync_preview_parity_captured_revision_and_repeat(project, mocker):
    from protostar.lifecycle import prepare_project

    project.write_text(source_text("updated") + '"new.txt" = "safe\\n"\n')
    prepared = prepare_project()
    registry = mocker.patch("protostar.lifecycle.resolve_hook_revisions")
    project.write_text(source_text("later"))
    result = prepared.apply()
    registry.assert_not_called()
    for edit in prepared.review.edits:
        assert Path(edit.path).read_bytes() == edit.after
    assert "new.txt" in result.created_paths
    project.write_text(source_text("updated") + '"new.txt" = "safe\\n"\n')
    repeated = prepare_project()
    assert not repeated.review.pending
    before = snapshot(Path.cwd())
    assert not repeated.apply().touched_paths
    assert snapshot(Path.cwd()) == before


def test_sync_partial_commits_safe_siblings_and_retains_conflict(
    project, monkeypatch, capsys
):
    Path(".github/renovate.json").write_text(json.dumps({"value": "local"}))
    project.write_text(source_text("remote") + '"safe.txt" = "accepted"\n')
    payload = invoke_sync(monkeypatch, capsys, code=1)
    assert payload["status"] == "partial"
    assert Path("safe.txt").read_text() == "accepted"
    assert json.loads(Path(".github/renovate.json").read_text()) == {"value": "local"}
    assert payload["review"]["conflicts"]
    assert "safe.txt" in payload["result"]["created_paths"]
    review = inspect_project()
    assert review.conflicts
    assert not review.edits
    assert not review.state_changed


def test_sync_check_and_dry_run_are_read_only(project, monkeypatch, capsys):
    project.write_text(source_text("updated"))
    before = snapshot(Path.cwd())
    preview = invoke_sync(monkeypatch, capsys, "--dry-run")
    assert preview == review_payload(inspect_project())
    checked = invoke_sync(monkeypatch, capsys, "--check", code=1)
    assert checked["check_passed"] is False
    assert snapshot(Path.cwd()) == before
    invoke_sync(monkeypatch, capsys)
    assert invoke_sync(monkeypatch, capsys, "--check")["check_passed"] is True
    Path(".github/renovate.json").unlink()
    assert invoke_sync(monkeypatch, capsys, "--check")["check_passed"] is True
    invoke_sync(monkeypatch, capsys)
    assert not Path(".github/renovate.json").exists()


@pytest.mark.parametrize("failure", ["state", "interrupt"])
def test_sync_fatal_failure_restores_bytes_modes_and_reports_rollback(
    project, monkeypatch, capsys, mocker, failure
):
    from protostar.errors import FileSystemError

    project.write_text(source_text("updated") + '"safe.txt" = "accepted"\n')
    Path(".github/renovate.json").chmod(0o640)
    before = snapshot(Path.cwd())
    error = (
        KeyboardInterrupt()
        if failure == "interrupt"
        else FileSystemError("write state", ".protostar.lock.toml", OSError("injected"))
    )
    mocker.patch("protostar.executor.SystemExecutor._write_state", side_effect=error)
    payload = invoke_sync(
        monkeypatch, capsys, code=130 if failure == "interrupt" else 74
    )
    assert payload["status"] == "error"
    assert payload["error"]["rollback_context"]["touched_paths"]
    assert snapshot(Path.cwd()) == before


def test_sync_tasks_and_ide_probes_never_run(project, mocker):
    from protostar.lifecycle import prepare_project

    project.write_text(
        'system_tasks = [["custom", "system"]]\n'
        'post_install_tasks = [["custom", "post"]]\n' + source_text("updated")
    )
    tasks = mocker.patch(
        "protostar.executor.SystemExecutor._run_tasks",
        side_effect=AssertionError("task"),
    )
    probe = mocker.patch(
        "protostar.executor.SystemExecutor._check_ide_extensions",
        side_effect=AssertionError("probe"),
    )
    prepared = prepare_project()
    assert ("custom", "system") in prepared.review.initialization_only
    prepared.apply()
    tasks.assert_not_called()
    probe.assert_not_called()


def test_sync_modes_are_mutually_exclusive():
    from protostar.cli.parser import build_parser

    with pytest.raises(InvalidUsageError):
        build_parser().parse_args(["sync", "--check", "--dry-run"])


def test_sync_accepted_dependencies_resolve_once(project, mocker):
    import tomlkit

    from protostar.lifecycle import prepare_project

    project.write_text('dependencies = ["example"]\n' + source_text("updated"))
    prepared = prepare_project()
    assert dict(prepared.review.resolver.requirements)

    def resolve(_runner, command, *, timeout):
        assert command == ["uv", "add", "example"]
        doc = tomlkit.parse(Path("pyproject.toml").read_text())
        doc["project"]["dependencies"] = ["example>=3"]
        Path("pyproject.toml").write_text(tomlkit.dumps(doc))
        Path("uv.lock").write_text("resolved")

    process = mocker.patch(
        "protostar.system.ProcessRunner.run", autospec=True, side_effect=resolve
    )
    prepared.apply()
    process.assert_called_once()
    process.reset_mock()
    repeated = prepare_project()
    assert not repeated.review.pending
    assert not repeated.apply().touched_paths
    process.assert_not_called()


def test_sync_metadata_only_resolves_lock_once(project, mocker):
    from protostar.lifecycle import prepare_project

    project.write_text(
        '[dev.pyproject]\nmetadata = "[project]\\nrequires-python = \\"'
        + ">=3.13"
        + '\\"\\n"\n'
    )
    prepared = prepare_project()
    assert prepared.review.resolver.lock_required

    def resolve(_runner, command, *, timeout):
        assert command == ["uv", "lock"]
        Path("uv.lock").write_text("refreshed")

    process = mocker.patch(
        "protostar.system.ProcessRunner.run", autospec=True, side_effect=resolve
    )
    prepared.apply()
    process.assert_called_once()
    process.reset_mock()
    assert not prepare_project().apply().touched_paths
    process.assert_not_called()


def test_sync_check_counts_baseline_only_advancement(project, monkeypatch, capsys):
    invoke_sync(monkeypatch, capsys)
    project.write_text(source_text("converged"))
    Path(".github/renovate.json").write_text(json.dumps({"value": "converged"}))
    review = inspect_project()
    assert review.state_changed
    assert not review.edits
    assert not review.resolver.pending
    before = Path(".github/renovate.json").read_bytes()
    invoke_sync(monkeypatch, capsys, "--check", code=1)
    result = invoke_sync(monkeypatch, capsys)
    assert result["result"]["touched_paths"] == [".protostar.lock.toml"]
    assert Path(".github/renovate.json").read_bytes() == before
    assert invoke_sync(monkeypatch, capsys, "--check")["check_passed"]


def test_sync_stale_review_aborts_before_mutation(project):
    from protostar.errors import StaleReviewError
    from protostar.lifecycle import prepare_project

    project.write_text(source_text("updated") + '"new.txt" = "safe"\n')
    prepared = prepare_project()
    Path("pyproject.toml").write_text(
        "# concurrent\n" + Path("pyproject.toml").read_text()
    )
    before = snapshot(Path.cwd())
    with pytest.raises(StaleReviewError):
        prepared.apply()
    assert snapshot(Path.cwd()) == before


@pytest.mark.parametrize("timeout", [False, True])
def test_sync_resolver_failure_restores_entire_transaction(
    project, monkeypatch, capsys, mocker, timeout
):
    from protostar.errors import CommandExecutionError, CommandTimeoutError

    project.write_text('dependencies = ["example"]\n' + source_text("updated"))
    Path("uv.lock").write_text("original lock")
    Path("uv.lock").chmod(0o640)
    before = snapshot(Path.cwd())

    def fail(_runner, command, *, timeout):
        Path("pyproject.toml").write_text("resolver mutation")
        Path("uv.lock").write_text("resolver lock")
        raise error

    error = (
        CommandTimeoutError(["uv", "add", "example"], 600)
        if timeout
        else CommandExecutionError(["uv", "add", "example"], 2)
    )
    mocker.patch("protostar.system.ProcessRunner.run", autospec=True, side_effect=fail)
    terminate = mocker.patch(
        "protostar.system.ProcessRunner.terminate_active_process_tree"
    )
    payload = invoke_sync(monkeypatch, capsys, code=1)
    terminate.assert_called_once()
    assert payload["error"]["type"] == type(error).__name__
    assert payload["error"]["rollback_context"]
    assert snapshot(Path.cwd()) == before


@pytest.mark.parametrize("mode", [[], ["--dry-run"], ["--check"]])
def test_sync_human_rendering_agrees_with_review(project, monkeypatch, capsys, mode):
    project.write_text(source_text("updated"))
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync", *mode])
    if mode == ["--check"]:
        with pytest.raises(SystemExit) as caught:
            main()
        assert caught.value.code == 1
    else:
        main()
    output = capsys.readouterr().out
    assert "Accepted: .github/renovate.json" in output
    if mode == ["--dry-run"]:
        assert "--- a/.github/renovate.json" in output
        assert (
            json.loads(Path(".github/renovate.json").read_text())["value"] == "original"
        )
    elif mode == ["--check"]:
        assert "Check failed" in output
    else:
        assert "Applied changes" in output
        assert (
            json.loads(Path(".github/renovate.json").read_text())["value"] == "updated"
        )


def test_sync_application_schema_and_flags_are_published():
    from protostar.cli.parser import build_parser

    capabilities = schema._build_capabilities_schema(build_parser())
    application = capabilities["application_schema"]
    assert application["properties"]["status"]["enum"] == ["success", "partial"]
    assert {"--dry-run", "--check"} <= {
        name
        for flag in capabilities["commands"]["sync"]["flags"]
        for name in flag["names"]
    }


def test_same_source_evolution_combines_conflicts_deletions_regions_and_resolver(
    project, monkeypatch, capsys, mocker
):
    """A mixed revision applies safe intent and then converges beside local drift."""
    import tomlkit

    from protostar.lifecycle import prepare_project
    from protostar.sync_state import deserialize_state

    def revision(value, *, evolved=False):
        files = source_text(value)
        files += (
            '"deleted.txt" = "keep absent"\n"omitted.txt" = "retain ownership"\n'
            if not evolved
            else '"safe.txt" = "accepted"\n'
        )
        return (
            ('dependencies = ["example"]\n' if evolved else "")
            + files
            + '[appends."notes.txt".managed]\ncontent = "'
            + value
            + '"\n'
            + "[dev.pyproject]\nexample = '''[tool.example]\nvalue = "
            + ("2\nsafe = true" if evolved else "1")
            + "\n'''\n"
        )

    project.write_text(revision("original"))
    prepare_project().apply()
    Path("deleted.txt").unlink()
    Path(".github/renovate.json").write_text(json.dumps({"value": "local"}))
    target = Path("pyproject.toml")
    target.write_text(target.read_text().replace("value = 1", "value = 3"))
    Path("notes.txt").write_text("local prefix\n" + Path("notes.txt").read_text())
    project.write_text(revision("remote", evolved=True))
    before = snapshot(Path.cwd())
    review = inspect_project()
    assert len(review.conflicts) == 2
    assert review.resolver.pending
    assert snapshot(Path.cwd()) == before
    preview = invoke_sync(monkeypatch, capsys, "--dry-run")
    assert preview == review_payload(review)
    assert "uv.lock" not in {item["path"] for item in preview["diffs"]}
    invoke_sync(monkeypatch, capsys, "--check", code=1)
    assert snapshot(Path.cwd()) == before

    def resolve(_runner, command, *, timeout):
        assert command == ["uv", "add", "example"]
        doc = tomlkit.parse(target.read_text())
        doc["project"]["dependencies"] = ["example>=3"]
        target.write_text(tomlkit.dumps(doc))
        Path("uv.lock").write_text("resolved")

    process = mocker.patch(
        "protostar.system.ProcessRunner.run", autospec=True, side_effect=resolve
    )
    result = invoke_sync(monkeypatch, capsys, code=1)
    assert result["status"] == "partial"
    process.assert_called_once()
    assert not Path("deleted.txt").exists()
    assert Path("omitted.txt").read_text() == "retain ownership"
    assert Path("safe.txt").read_text() == "accepted"
    assert Path("notes.txt").read_text().startswith("local prefix\n")
    assert "remote" in Path("notes.txt").read_text()
    assert tomlkit.parse(target.read_text())["tool"]["example"] == {
        "value": 3,
        "safe": True,
    }
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    assert any(record.path == "omitted.txt" for record in state.files)
    process.reset_mock()
    after = snapshot(Path.cwd())
    for _ in range(2):
        repeated = inspect_project()
        assert repeated.conflicts
        assert not repeated.edits
        assert not repeated.state_changed
        assert not repeated.resolver.pending
        assert invoke_sync(monkeypatch, capsys, code=1)["result"]["touched_paths"] == []
        assert snapshot(Path.cwd()) == after
    process.assert_not_called()


def test_recipe_tool_evolution_retains_keyed_hook_edits_and_deleted_artifacts(
    project, mocker
):
    """Omitted opinions evolve, explicit opt-outs retain ownership on re-enable."""
    import tomlkit
    from ruamel.yaml import YAML

    yaml = YAML(typ="rt")

    from protostar.lifecycle import prepare_project
    from protostar.recipe import SelectionLayer

    def resolve(_runner, command, *, timeout):
        assert command[:3] == ["uv", "add", "--dev"]
        doc = tomlkit.parse(Path("pyproject.toml").read_text())
        groups = doc.setdefault("dependency-groups", {})
        existing = groups.setdefault("dev", [])
        existing.extend(package + ">=1" for package in command[3:])
        Path("pyproject.toml").write_text(tomlkit.dumps(doc))
        Path("uv.lock").write_text("resolved")

    process = mocker.patch(
        "protostar.system.ProcessRunner.run", autospec=True, side_effect=resolve
    )
    project.write_text("ruff = true\nprek = true\nrenovate = true\n")
    prepare_project().apply()
    hooks = Path(".pre-commit-config.yaml")
    data = yaml.load(hooks.read_text())
    local = next(repo for repo in data["repos"] if repo["repo"] == "local")
    next(hook for hook in local["hooks"] if hook["id"] == "ruff-check")["entry"] = (
        "local ruff"
    )
    with hooks.open("w") as stream:
        yaml.dump(data, stream)
    Path(".github/renovate.json").unlink()
    process.reset_mock()
    recipe_doc = tomlkit.parse(Path("pyproject.toml").read_text())
    recipe_doc["tool"]["protostar"]["tools"] = {"renovate": False}
    Path("pyproject.toml").write_text(tomlkit.dumps(recipe_doc))
    retained = Path(".protostar.lock.toml").read_bytes()
    project.write_text("ruff = true\nprek = true\nrenovate = true\nmypy = true\n")
    prepared = prepare_project()
    selections = {selection.tool: selection for selection in prepared.review.selections}
    assert not selections[Tool.RENOVATE].enabled
    assert selections[Tool.RENOVATE].layer is SelectionLayer.PROJECT
    assert selections[Tool.MYPY].enabled
    assert not any(
        "renovate" in diagnostic.message.lower()
        for diagnostic in prepared.review.diagnostics
    )
    prepared.apply()
    process.assert_called_once()
    data = yaml.load(hooks.read_text())
    local = next(repo for repo in data["repos"] if repo["repo"] == "local")
    assert (
        next(hook for hook in local["hooks"] if hook["id"] == "ruff-check")["entry"]
        == "local ruff"
    )
    assert any(hook["id"] == "mypy" for hook in local["hooks"])
    assert not Path(".github/renovate.json").exists()
    from protostar.sync_state import deserialize_state

    before = deserialize_state(retained.decode())
    after = deserialize_state(Path(".protostar.lock.toml").read_text())
    record = next(
        record for record in before.files if record.path == ".github/renovate.json"
    )
    assert record in after.files
    recipe_doc = tomlkit.parse(Path("pyproject.toml").read_text())
    recipe_doc["tool"]["protostar"]["tools"]["renovate"] = True
    Path("pyproject.toml").write_text(tomlkit.dumps(recipe_doc))
    process.reset_mock()
    prepared = prepare_project()
    assert any(
        item.deleted and item.location.file == ".github/renovate.json"
        for item in prepared.review.preserved
    )
    prepared.apply()
    assert not Path(".github/renovate.json").exists()
    process.assert_not_called()
    assert not inspect_project().pending
