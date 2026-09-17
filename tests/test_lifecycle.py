"""Focused acceptance for read-only project lifecycle inspection."""

import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from protostar.cli import main, schema, ui
from protostar.cli.reviews import review_payload
from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import ConfigurationError, ProtostarError
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
    Path("pyproject.toml").write_text(
        data.replace(str(project), str(project.parent / "other.toml"))
    )
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
    assert "sync" not in capabilities["commands"]
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
