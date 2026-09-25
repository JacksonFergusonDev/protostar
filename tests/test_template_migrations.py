"""Template-declared migrations: moved, removed, and renamed things across versions."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from protostar.cli import main, ui
from protostar.config import TemplateSource, UserConfig
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
    TemplateResolutionError,
)
from protostar.executor import SystemExecutor
from protostar.lifecycle import locate_project, prepare_project
from protostar.merge import ConflictReason
from protostar.migrations import (
    Migration,
    MigrationOutcome,
    Rename,
    parse_migrations,
    rename_variables,
    select_migrations,
)
from protostar.models import InitRequest
from protostar.orchestrator import Orchestrator
from protostar.recipe import RecipeIntent, Tool, establish_recipe, read_recipe
from protostar.sync_state import FilePolicy, FileState, read_workspace_state
from protostar.template_check import CheckRule, check_template

REPOSITORY = "https://github.com/org/tmpl"

V1 = """version = "1.0.0"
[files]
"settings.py" = "A = 1\\n"
"setup.cfg" = "[metadata]\\n"
"legacy.txt" = "old\\n"
"org.txt" = "<% ORG %>"
[variables.ORG]
description = "The organization."
"""

V2 = """version = "2.0.0"
[files]
"config.py" = "A = 1\\n"
"org.txt" = "<% ORGANIZATION %>"
[variables.ORGANIZATION]
description = "The organization."

[[migrations]]
version = "2.0.0"
rename = [{ from = "settings.py", to = "config.py" }]
remove = ["setup.cfg", "legacy.txt"]
rename_variables = [{ from = "ORG", to = "ORGANIZATION" }]
"""


def test_migrations_parse_oldest_first():
    data = {
        "version": "3.0.0",
        "migrations": [
            {"version": "3.0.0", "remove": ["b.txt"]},
            {
                "version": "2.0.0",
                "rename": [{"from": "a.py", "to": "b.py"}],
                "rename_variables": [{"from": "ORG", "to": "ORGANIZATION"}],
            },
        ],
    }
    assert parse_migrations(data, "t") == (
        Migration(
            "2.0.0",
            rename=(Rename("a.py", "b.py"),),
            rename_variables=(Rename("ORG", "ORGANIZATION"),),
        ),
        Migration("3.0.0", remove=("b.txt",)),
    )
    assert parse_migrations({}, "t") == ()


@pytest.mark.parametrize(
    ("data", "match"),
    [
        ({"migrations": [{"version": "1.0"}]}, "must declare its version"),
        ({"version": "x", "migrations": [{"version": "1.0"}]}, "declare its version"),
        ({"version": "1.0", "migrations": {}}, "array of tables"),
        ({"version": "1.0", "migrations": [{"version": "one"}]}, "not a PEP 440"),
        ({"version": "1.0", "migrations": [{"version": "2.0"}]}, "newer than"),
        (
            {"version": "1.0", "migrations": [{"version": "1.0"}, {"version": "1"}]},
            "same version",
        ),
        ({"version": "1.0", "migrations": [{"version": "1.0", "x": 1}]}, "unknown"),
        (
            {"version": "1.0", "migrations": [{"version": "1.0", "remove": ["../x"]}]},
            "not a relative path",
        ),
        (
            {"version": "1.0", "migrations": [{"version": "1.0", "remove": "x"}]},
            "array of paths",
        ),
        (
            {
                "version": "1.0",
                "migrations": [
                    {"version": "1.0", "rename": [{"from": "a", "to": "a"}]}
                ],
            },
            "different 'from' and 'to'",
        ),
        (
            {
                "version": "1.0",
                "migrations": [
                    {
                        "version": "1.0",
                        "rename_variables": [{"from": "PROJECT_NAME", "to": "NAME"}],
                    }
                ],
            },
            "not a custom variable",
        ),
    ],
)
def test_malformed_migrations_are_template_errors(data, match):
    with pytest.raises(TemplateResolutionError, match=match):
        parse_migrations(data, "t")


MIGRATIONS = (Migration("1.1.0"), Migration("2.0.0"), Migration("3.0.0"))


def test_migrations_run_between_the_applied_and_the_new_version():
    assert select_migrations(MIGRATIONS, "1.1.0", "3.0.0") == MIGRATIONS[1:]
    assert select_migrations(MIGRATIONS, "1.0.0", "2.5") == MIGRATIONS[:2]
    assert select_migrations(MIGRATIONS, "3.0.0", "3.0.0") == ()
    # An unknown applied version runs everything; ownership guards each step.
    assert select_migrations(MIGRATIONS, None, "2.0.0") == MIGRATIONS[:2]
    assert select_migrations(MIGRATIONS, "not a version", "1.1") == MIGRATIONS[:1]
    assert select_migrations(MIGRATIONS, "1.0.0", None) == ()


def test_moving_back_across_a_migration_is_refused():
    assert select_migrations(MIGRATIONS, "2.5.0", "2.0.0", "2.0.0") == ()
    with pytest.raises(ConfigurationError, match=r"undo its 3\.0\.0 migration"):
        select_migrations((), "3.0.0", "2.0.0", "3.0.0")
    with pytest.raises(ConfigurationError, match="an unversioned revision"):
        select_migrations((), "3.0.0", None, "3.0.0")


def test_variable_renames_are_idempotent():
    migrations = (Migration("1", rename_variables=(Rename("ORG", "ORGANIZATION"),)),)
    assert rename_variables({"ORG": "acme"}, migrations) == {"ORGANIZATION": "acme"}
    assert rename_variables({"ORGANIZATION": "x", "ORG": "y"}, migrations) == {
        "ORGANIZATION": "x",
        "ORG": "y",
    }


def test_seed_records_validate_digest_and_retirement():
    FileState("a.txt", FilePolicy.SEED, digest="a" * 64, retired=True)
    with pytest.raises(ConfigurationError):
        FileState("a.txt", FilePolicy.SEED, digest="short")
    with pytest.raises(ConfigurationError):
        FileState("a.txt", FilePolicy.TEXT, "x", digest="a" * 64)
    with pytest.raises(ConfigurationError):
        FileState("a.txt", FilePolicy.TEXT, "x", retired=True)


@pytest.fixture
def repo(forge):
    repository = forge.repository(REPOSITORY)
    repository.commit({"protostar.toml": V1}, tag="v1.0.0")
    repository.commit({"protostar.toml": V2}, tag="v2.0.0")
    return repository


@pytest.fixture
def project(repo, tmp_path, monkeypatch, mocker):
    """A project enrolled from v1.0.0, with ORG recorded as acme."""
    enroll(tmp_path, monkeypatch, mocker)
    return repo


def enroll(tmp_path, monkeypatch, mocker):
    """Enrolls a project from v1.0.0 of the forge template and settles it."""
    monkeypatch.chdir(tmp_path)
    blueprint = TemplateSource.load(f"{REPOSITORY}/tree/v1.0.0").render({"ORG": "acme"})
    recipe = establish_recipe(
        UserConfig(),
        RecipeIntent(reference=blueprint.reference, variables=(("ORG", "acme"),)),
    )
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
    prepare_project().apply()


def cli(monkeypatch, capsys, *args, code=0):
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", *args, "--json"])
    if code:
        with pytest.raises(SystemExit) as caught:
            main()
        assert caught.value.code == code
    else:
        main()
    return json.loads(capsys.readouterr().out)


def records():
    state = read_workspace_state(Path.cwd())
    assert state is not None
    return {record.path: record for record in state.files}


def test_seeds_record_the_digest_of_what_was_written(project):
    record = records()["settings.py"]
    assert record.digest == hashlib.sha256(b"A = 1\n").hexdigest()
    assert not record.retired


def test_upgrade_moves_edits_removes_retires_and_renames(project, monkeypatch, capsys):
    Path("settings.py").write_text("A = 2  # mine\n")
    Path("legacy.txt").write_text("old, and edited\n")

    payload = cli(monkeypatch, capsys, "sync", "--to", "v2.0.0", code=1)

    assert payload["status"] == "partial"
    steps = {
        step["path"]: (step["target"], step["outcome"])
        for step in payload["review"]["migrations"]
    }
    assert steps == {
        "settings.py": ("config.py", "moved"),
        "setup.cfg": (None, "removed"),
        "legacy.txt": (None, "retired"),
    }
    # The local edit moved with the file, and the old path is gone.
    assert Path("config.py").read_text() == "A = 2  # mine\n"
    assert not Path("settings.py").exists()
    assert not Path("setup.cfg").exists()
    assert Path("legacy.txt").read_text() == "old, and edited\n"
    # The variable kept its value under its new name.
    recipe = read_recipe(Path("pyproject.toml"))
    assert recipe is not None
    assert dict(recipe.variables) == {"ORGANIZATION": "acme"}
    assert Path("org.txt").read_text() == "acme"
    owned = records()
    assert "settings.py" not in owned
    assert "setup.cfg" not in owned
    assert owned["config.py"].digest == hashlib.sha256(b"A = 1\n").hexdigest()
    assert owned["legacy.txt"].retired
    state = read_workspace_state(Path.cwd())
    assert state is not None
    assert state.template is not None
    assert state.template.migrated == "2.0.0"
    (conflict,) = payload["review"]["conflicts"]
    assert (conflict["file"], conflict["reason"]) == (
        "legacy.txt",
        ConflictReason.RETRACTED.value,
    )
    assert conflict["choices"] == ["local", "desired"]

    # The retired file stays a decision after the version moved on.
    review = prepare_project().review
    assert not review.migrations
    assert [c.location.file for c in review.conflicts] == ["legacy.txt"]


@pytest.mark.parametrize(("choice", "kept"), [("desired", False), ("local", True)])
def test_a_retired_seed_is_settled_by_a_resolution(
    project, monkeypatch, capsys, choice, kept
):
    Path("legacy.txt").write_text("edited\n")
    cli(monkeypatch, capsys, "sync", "--to", "v2.0.0", code=1)
    (conflict,) = prepare_project().review.conflicts

    payload = cli(monkeypatch, capsys, "sync", "--resolve", f"{conflict.id}={choice}")

    assert payload["status"] == "success"
    assert Path("legacy.txt").exists() is kept
    assert "legacy.txt" not in records()
    assert not prepare_project().review.pending


def test_a_retired_seed_deleted_by_hand_is_let_go(project, monkeypatch, capsys):
    Path("legacy.txt").write_text("edited\n")
    cli(monkeypatch, capsys, "sync", "--to", "v2.0.0", code=1)
    Path("legacy.txt").unlink()

    cli(monkeypatch, capsys, "sync")

    assert "legacy.txt" not in records()


def test_migrations_run_once(project, monkeypatch, capsys):
    cli(monkeypatch, capsys, "sync", "--to", "v2.0.0")
    Path("setup.cfg").write_text("mine now\n")

    review = prepare_project().review

    assert not review.migrations
    assert not review.pending
    assert Path("setup.cfg").read_text() == "mine now\n"


def test_status_previews_migrations_without_writing(project, monkeypatch, capsys):
    before = {path: path.read_bytes() for path in Path.cwd().rglob("*.*")}
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr(
        "sys.argv", ["protostar", "sync", "--to", "v2.0.0", "--dry-run"]
    )

    main()

    out = capsys.readouterr().out
    assert "Migration 2.0.0: settings.py moves to config.py." in out
    assert "Migration 2.0.0: setup.cfg is removed." in out
    assert "Removed: setup.cfg" in out
    assert "+++ /dev/null" in out
    assert {path: path.read_bytes() for path in Path.cwd().rglob("*.*")} == before


def test_a_rename_never_overwrites_an_existing_file(project, monkeypatch, capsys):
    Path("config.py").write_text("mine\n")

    payload = cli(monkeypatch, capsys, "sync", "--to", "v2.0.0")

    steps = {step["path"]: step["outcome"] for step in payload["review"]["migrations"]}
    assert steps["settings.py"] == MigrationOutcome.TARGET_EXISTS.value
    assert Path("config.py").read_text() == "mine\n"
    assert Path("settings.py").exists()
    assert "settings.py" in records()


def test_a_deleted_seed_stays_deleted_where_it_moved(project, monkeypatch, capsys):
    Path("settings.py").unlink()

    payload = cli(monkeypatch, capsys, "sync", "--to", "v2.0.0")

    assert not Path("settings.py").exists()
    assert not Path("config.py").exists()
    assert "config.py" in records()
    assert any(item["file"] == "config.py" for item in payload["review"]["preserved"])


def test_moving_back_across_a_migration_fails_before_any_change(
    project, monkeypatch, capsys
):
    cli(monkeypatch, capsys, "sync", "--to", "v2.0.0")
    before = Path("pyproject.toml").read_text()

    with pytest.raises(ConfigurationError, match=r"undo its 2\.0\.0 migration"):
        locate_project("v1.0.0")

    assert Path("pyproject.toml").read_text() == before


def test_a_failed_upgrade_rolls_both_paths_of_a_rename_back(project, mocker):
    Path("settings.py").write_text("A = 2\n")
    located = locate_project("v2.0.0")
    prepared = prepare_project(located)
    real = type(prepared).apply

    def fail_on_state(self, **kwargs):
        from protostar.fs_transaction import TransactionAwareFS

        original = TransactionAwareFS.write_bytes

        def write_bytes(fs, path, content):
            if Path(path).name == "protostar.lock":
                raise OSError("disk full")
            return original(fs, path, content)

        mocker.patch.object(TransactionAwareFS, "write_bytes", write_bytes)
        return real(self, **kwargs)

    with pytest.raises(FileSystemError):
        fail_on_state(prepared)

    assert Path("settings.py").read_text() == "A = 2\n"
    assert not Path("config.py").exists()
    assert Path("setup.cfg").exists()


def test_projects_without_a_recorded_version_run_every_migration(
    forge, tmp_path, monkeypatch, mocker, capsys
):
    repository = forge.repository(REPOSITORY)
    repository.commit(
        {"protostar.toml": V1.replace('version = "1.0.0"\n', "")}, tag="v1.0.0"
    )
    repository.commit({"protostar.toml": V2}, tag="v2.0.0")
    enroll(tmp_path, monkeypatch, mocker)
    state = read_workspace_state(Path.cwd())
    assert state is not None
    assert state.template is not None
    assert state.template.version is None

    cli(monkeypatch, capsys, "sync", "--to", "v2.0.0")

    assert Path("config.py").exists()
    assert not Path("setup.cfg").exists()


def test_seeds_without_a_digest_are_retired_rather_than_deleted(
    project, monkeypatch, capsys
):
    from protostar.sync_state import SyncState, serialize_state

    state = read_workspace_state(Path.cwd())
    assert state is not None
    Path("protostar.lock").write_text(
        serialize_state(
            SyncState(
                state.producer_version,
                state.template,
                tuple(replace(record, digest=None) for record in state.files),
                state.dependencies,
                state.hook_pins,
            )
        )
    )

    payload = cli(monkeypatch, capsys, "sync", "--to", "v2.0.0", code=1)

    steps = {step["path"]: step["outcome"] for step in payload["review"]["migrations"]}
    assert steps["setup.cfg"] == MigrationOutcome.RETIRED.value
    assert Path("setup.cfg").exists()


def test_check_template_reports_inconsistent_migrations(tmp_path):
    template = tmp_path / "protostar.toml"
    template.write_text(
        """name = "t"
description = "d"
version = "2.0.0"
[files]
"old.py" = ""
"kept.txt" = ""
"x.txt" = "<% ORG %>"
[variables.ORG]
description = "The organization."

[[migrations]]
version = "2.0.0"
rename = [{ from = "old.py", to = "new.py" }]
remove = ["kept.txt"]
rename_variables = [{ from = "ORG", to = "ORGANIZATION" }]
"""
    )

    findings = [
        finding
        for finding in check_template(str(template)).findings
        if finding.rule is CheckRule.INCONSISTENT_MIGRATION
    ]

    messages = [finding.message for finding in findings]
    assert messages == [
        "Migration 2.0.0 removes kept.txt, which the template still ships.",
        "Migration 2.0.0 renames old.py, which the template still ships.",
        "Migration 2.0.0 renames a file to new.py, which the template doesn't ship.",
        "Migration 2.0.0 renames variable ORG to ORGANIZATION, which the template "
        "doesn't use.",
        "Migration 2.0.0 renames variable ORG, which the template still uses.",
    ]
    assert findings[0].line == 14


def test_migrations_leave_foreign_and_deleted_files_alone(project, monkeypatch, capsys):
    project.commit(
        {
            "protostar.toml": V2.replace(
                'version = "2.0.0"\n', 'version = "2.1.0"\n', 1
            )
            + '\n[[migrations]]\nversion = "2.1.0"\n'
            'rename = [{ from = "README.md", to = "docs/README.md" }]\n'
            'remove = ["notes.md"]\n'
        },
        tag="v2.1.0",
    )
    Path("README.md").write_text("mine\n")
    Path("notes.md").write_text("mine\n")
    Path("setup.cfg").unlink()

    payload = cli(monkeypatch, capsys, "sync", "--to", "v2.1.0")

    steps = {step["path"]: step["outcome"] for step in payload["review"]["migrations"]}
    assert steps["setup.cfg"] == MigrationOutcome.FORGOTTEN.value
    assert steps["README.md"] == MigrationOutcome.NOT_OWNED.value
    assert steps["notes.md"] == MigrationOutcome.NOT_OWNED.value
    assert Path("README.md").read_text() == "mine\n"
    assert Path("notes.md").read_text() == "mine\n"
    assert "setup.cfg" not in records()
