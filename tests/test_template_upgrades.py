"""Versioned remote templates: pinned revisions, update reports, and sync --to."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
import tomlkit

from protostar.cli import main, ui
from protostar.config import TemplateSource, UserConfig
from protostar.errors import (
    NetworkFetchError,
    TemplateRefNotFoundError,
    UnversionedTemplateError,
)
from protostar.executor import SystemExecutor
from protostar.lifecycle import TemplateUpstream, locate_project, prepare_project
from protostar.manifest import EnvironmentManifest
from protostar.models import InitRequest
from protostar.network import RefKind
from protostar.orchestrator import Orchestrator
from protostar.recipe import RecipeIntent, Tool, establish_recipe, read_recipe
from protostar.sync_state import read_workspace_state

REPOSITORY = "https://github.com/org/tmpl"


def template(version: str, *, extra: str = "") -> dict[str, str]:
    return {
        "protostar.toml": f'version = "{version}"\n'
        f'[files]\n".github/renovate.json" = \'{{"release": "{version}"}}\'\n'
        + extra
        + f'[appends.".envrc".environment]\ncontent = "export RELEASE={version}"\n',
    }


@pytest.fixture
def repo(forge):
    repository = forge.repository(REPOSITORY)
    repository.commit(template("1.0.0"), tag="v1.0.0")
    repository.commit(template("1.1.0"), tag="v1.1.0", branch="main")
    return repository


@pytest.fixture
def project(repo, tmp_path, monkeypatch, mocker):
    """A project enrolled from v1.0.0 of the forge template."""
    monkeypatch.chdir(tmp_path)
    blueprint = TemplateSource.load(f"{REPOSITORY}/tree/v1.0.0").render({})
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    recipe = replace(recipe, fallback=tuple((tool, False) for tool in Tool))
    manifest = Orchestrator(
        [], UserConfig(), InitRequest(recipe=recipe, template_blueprint=blueprint)
    ).plan()
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
    # Settle what the lifecycle adds beyond this bare plan, so the project
    # starts with no pending work.
    prepare_project().apply()
    return repo


def sync(monkeypatch, capsys, *flags, code=0):
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", *flags, "--json"])
    if code:
        with pytest.raises(SystemExit) as caught:
            main()
        assert caught.value.code == code
    else:
        main()
    return json.loads(capsys.readouterr().out)


def release():
    return json.loads(Path(".github/renovate.json").read_text())["release"]


def recorded_source():
    recipe = read_recipe(Path("pyproject.toml"))
    assert recipe is not None
    assert recipe.source is not None
    return recipe.source


def recorded_template():
    state = read_workspace_state(Path.cwd())
    assert state is not None
    assert state.template is not None
    return state.template


def test_enrollment_records_the_ref_in_the_recipe_and_its_commit_in_the_ledger(
    project,
):
    source = recorded_source()
    assert (source.locator, source.path, source.ref) == (REPOSITORY, "", "v1.0.0")
    state = recorded_template()
    assert state.ref == "v1.0.0"
    assert state.revision == project.tags["v1.0.0"]
    assert release() == "1.0.0"


def test_status_reports_a_newer_release_without_failing_the_check(
    project, monkeypatch, capsys
):
    payload = sync(monkeypatch, capsys, "status")
    assert payload["pending"] is False
    assert payload["template"] == {
        "ref": "v1.0.0",
        "revision": project.tags["v1.0.0"],
        "kind": "tag",
        "newer": "v1.1.0",
        "moved": None,
        "reachable": True,
    }
    check = sync(monkeypatch, capsys, "sync", "--check")
    assert check["check_passed"] is True


def test_status_prints_the_available_release(project, monkeypatch, capsys):
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "status"])
    main()
    out = capsys.readouterr().out
    assert "Template v1.0.0" in out
    assert "v1.1.0 available (sync --to v1.1.0)." in out


def test_sync_to_moves_the_recipe_the_ledger_and_the_content(
    project, monkeypatch, capsys
):
    before = recorded_template()
    envrc = Path(".envrc").read_text()

    payload = sync(monkeypatch, capsys, "sync", "--to", "v1.1.0")

    assert payload["status"] == "success"
    assert payload["template"]["ref"] == "v1.1.0"
    assert payload["template"]["newer"] is None
    assert recorded_source().ref == "v1.1.0"
    after = recorded_template()
    assert after.revision == project.tags["v1.1.0"]
    assert after.identity == before.identity
    assert release() == "1.1.0"
    # The region keeps its tag across the upgrade, so it merges in place.
    assert Path(".envrc").read_text() == envrc.replace("1.0.0", "1.1.0")
    assert not prepare_project().review.pending


def test_sync_to_latest_names_the_newest_release(project, monkeypatch, capsys):
    project.commit(template("2.0.0rc1"), tag="v2.0.0rc1")
    sync(monkeypatch, capsys, "sync", "--to", "latest")
    assert recorded_source().ref == "v1.1.0"


def test_sync_to_previews_an_upgrade_with_dry_run(project, monkeypatch, capsys):
    before = Path("pyproject.toml").read_text()
    payload = sync(monkeypatch, capsys, "sync", "--to", "v1.1.0", "--dry-run")
    assert {edit["path"] for edit in payload["review"]["edits"]} >= {
        ".github/renovate.json",
        "pyproject.toml",
    }
    assert Path("pyproject.toml").read_text() == before


def test_a_moved_tag_changes_nothing_until_the_recipe_moves(
    project, monkeypatch, capsys
):
    moved = project.commit(template("1.0.1"))
    project.tags["v1.0.0"] = moved

    payload = sync(monkeypatch, capsys, "status")

    assert payload["pending"] is False
    assert payload["template"]["moved"] == moved
    assert release() == "1.0.0"
    sync(monkeypatch, capsys, "sync", "--to", "v1.0.0")
    assert release() == "1.0.1"


def test_a_branch_follows_only_when_asked(project, monkeypatch, capsys):
    sync(monkeypatch, capsys, "sync", "--to", "main")
    assert recorded_source().ref == "main"
    project.commit(template("1.2.0.dev0"), branch="main")

    payload = sync(monkeypatch, capsys, "status")
    assert payload["template"]["kind"] == RefKind.BRANCH.value
    assert payload["template"]["moved"] == project.branches["main"]
    assert release() == "1.1.0"

    sync(monkeypatch, capsys, "sync", "--to", "main")
    assert release() == "1.2.0.dev0"


def test_editing_the_recipe_ref_moves_the_template(project, monkeypatch, capsys):
    document = tomlkit.parse(Path("pyproject.toml").read_text())
    document["tool"]["protostar"]["source"]["ref"] = "v1.1.0"
    Path("pyproject.toml").write_text(tomlkit.dumps(document))

    sync(monkeypatch, capsys, "sync")

    assert release() == "1.1.0"
    state = recorded_template()
    assert state.revision == project.tags["v1.1.0"]


def test_status_works_offline_from_the_recorded_commit(project, forge):
    forge.offline = True
    with pytest.raises(NetworkFetchError):
        locate_project()
    # The listing is optional; only the download is not.
    forge.offline = False
    listing_url = f"{REPOSITORY}.git/info/refs?service=git-upload-pack"
    original = forge.respond

    def refuse_listing(url):
        if url == listing_url:
            from urllib.error import URLError

            raise URLError("offline")
        return original(url)

    forge.respond = refuse_listing
    located = locate_project()
    assert located.upstream is not None
    assert located.upstream.reachable is False
    assert not prepare_project(located).review.pending
    with pytest.raises(NetworkFetchError):
        locate_project("v1.1.0")


def test_unknown_refs_are_rejected_before_anything_changes(project):
    before = Path("pyproject.toml").read_text()
    with pytest.raises(TemplateRefNotFoundError, match="v9"):
        locate_project("v9")
    assert Path("pyproject.toml").read_text() == before


def test_templates_without_revisions_cannot_move(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.toml"
    source.write_text('[files]\n"a.txt" = "a"\n')
    blueprint = TemplateSource.load(str(source)).render({})
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    manifest = EnvironmentManifest(
        template_reference=blueprint.reference, recipe=recipe
    )
    manifest.filesystem.add_structured(
        "pyproject.toml", '[project]\nname = "demo"\n', producer="seed"
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()

    with pytest.raises(UnversionedTemplateError):
        locate_project("v1.0.0")
    assert locate_project().upstream is None


def test_upgrade_variables_come_from_flags_and_are_recorded(
    project, monkeypatch, capsys
):
    project.commit(
        template("2.0.0", extra='"region.txt" = "<% REGION %>"\n'), tag="v2.0.0"
    )

    error = sync(monkeypatch, capsys, "sync", "--to", "v2.0.0", code=65)
    assert error["error"]["missing_variables"] == ["REGION"]
    assert recorded_source().ref == "v1.0.0"

    sync(monkeypatch, capsys, "sync", "--to", "v2.0.0", "--var", "REGION=eu")

    assert Path("region.txt").read_text() == "eu"
    recipe = read_recipe(Path("pyproject.toml"))
    assert recipe is not None
    assert dict(recipe.variables) == {"REGION": "eu"}


def test_interactive_upgrade_asks_for_new_variables(project, monkeypatch, mocker):
    project.commit(
        template("2.0.0", extra='"region.txt" = "<% REGION %>"\n'), tag="v2.0.0"
    )
    mocker.patch("protostar.cli.reviews.is_interactive", return_value=True)
    screen = mocker.patch(
        "protostar.cli.main.edit_variables",
        side_effect=lambda draft, config, flagged, **_: replace(
            draft, variables=(("REGION", "us"),)
        ),
    )
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync", "--to", "v2.0.0"])

    main()

    assert screen.call_args.kwargs["command"] == "sync"
    assert Path("region.txt").read_text() == "us"


def test_payloads_match_the_published_schemas(project, monkeypatch, capsys):
    import jsonschema  # type: ignore[import-untyped]

    from protostar.cli.schema import application_schema, review_schema

    jsonschema.validate(sync(monkeypatch, capsys, "status"), review_schema())
    jsonschema.validate(
        sync(monkeypatch, capsys, "sync", "--to", "v1.1.0"), application_schema()
    )


@pytest.mark.parametrize(
    ("upstream", "expected"),
    [
        (
            TemplateUpstream("main", "a" * 40, RefKind.BRANCH, moved="b" * 40),
            "main moved to bbbbbbbbbbbb (sync --to main).",
        ),
        (
            TemplateUpstream("v1.0.0", "a" * 40, reachable=False),
            "its repository could not be checked for updates.",
        ),
        (
            TemplateUpstream("gone", "a" * 40),
            "the repository no longer has this ref.",
        ),
        (
            TemplateUpstream("v1.0.0", "a" * 40, RefKind.TAG),
            "Template v1.0.0 @ aaaaaaaaaaaa; up to date.",
        ),
    ],
)
def test_status_line_encodes_on_legacy_consoles(upstream, expected, capsys):
    from protostar.cli.reviews import render_upstream

    render_upstream(upstream)

    out = capsys.readouterr().out
    assert expected in out
    out.encode("cp1252")
