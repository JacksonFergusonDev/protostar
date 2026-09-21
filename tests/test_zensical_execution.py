"""zensical.toml merges without subprocesses: seeds, managed settings, and holds."""

import tomllib
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.documents import zensical
from protostar.executor import SystemExecutor
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.merge import ConflictReason, MergeConflict, MergeLocation
from protostar.modules import ZensicalModule
from protostar.sync_state import FilePolicy, deserialize_state

TARGET = Path(zensical.TARGET)
STATE = Path(".protostar.lock.toml")
UNOWNED = MergeConflict(MergeLocation(zensical.TARGET), ConflictReason.UNOWNED)

# The shape `zensical new` writes: dotted pymdownx keys, its own nav and palette.
UPSTREAM = """[project]
site_name = "Documentation"
nav = [
  { "Get started" = "index.md" },
]

[project.theme]
features = [
  "content.code.copy",
  "navigation.sections",
]

[[project.theme.palette]]
scheme = "slate"

[project.markdown_extensions]
admonition = {}
pymdownx.details = {}
pymdownx.highlight.anchor_linenums = true
"""


def scaffold() -> str:
    intent = EnvironmentManifest()
    ZensicalModule().build(intent)
    [contribution] = intent.filesystem.structured[zensical.TARGET]
    return contribution.content


def run(mocker, content=None, strategy=CollisionStrategy.MERGE):
    intent = EnvironmentManifest(collision_strategy=strategy)
    intent.filesystem.add_structured(
        zensical.TARGET, content or scaffold(), producer="module:ZensicalModule"
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
    return tomllib.loads(TARGET.read_text())["project"]


def test_scaffold_is_created_verbatim_and_owned(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    assert TARGET.read_text() == scaffold().replace("<% PROJECT_NAME %>", tmp_path.name)
    [record] = deserialize_state(STATE.read_text()).files
    assert record.policy is FilePolicy.TOML
    initial = (TARGET.read_bytes(), STATE.read_bytes())
    repeated = run(mocker)
    assert not repeated.journal.touched_paths
    assert (TARGET.read_bytes(), STATE.read_bytes()) == initial


def test_existing_site_gains_only_managed_settings(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    TARGET.write_text(UPSTREAM)
    executor = run(mocker)
    assert not conflicts(executor)
    # Missing features join the user's list, the plugin table follows their last
    # table, and the dotted pymdownx spelling is not duplicated by a quoted one.
    added_features = "".join(
        f'  "{feature}",\n'
        for feature in (
            "content.tabs.link",
            "content.tooltips",
            "navigation.footer",
            "navigation.instant",
            "navigation.instant.prefetch",
            "navigation.top",
            "search.highlight",
        )
    )
    assert TARGET.read_text() == (
        UPSTREAM.replace(
            '  "navigation.sections",\n', f'  "navigation.sections",\n{added_features}'
        )
        + "\n[project.plugins.mkdocstrings]\n"
        "handlers.python.options.show_root_heading = true\n"
        "handlers.python.options.show_source = true\n"
    )


def test_existing_site_without_extensions_keeps_zensical_defaults(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    TARGET.write_text('[project]\nsite_name = "Documentation"\n')
    run(mocker)
    project = local()
    assert "markdown_extensions" not in project
    assert "nav" not in project
    assert set(project) == {"site_name", "theme", "plugins"}


def test_sync_updates_managed_settings_and_keeps_user_edits(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.write_text(
        TARGET.read_text()
        .replace('    { "Home" = "index.md" },\n', '    { "Guide" = "guide.md" },\n')
        .replace('    "navigation.top",\n', "")
        .replace(
            '    "search.highlight",\n',
            '    "search.highlight",\n    "navigation.tabs",\n',
        )
        .replace(
            "pymdownx.tilde = {}\n", "pymdownx.tilde = {}\npymdownx.snippets = {}\n"
        )
        .replace('primary = "white"', 'primary = "indigo"')
    )
    edited = local()
    changed = (
        scaffold()
        .replace(
            '    "search.highlight",\n',
            '    "search.highlight",\n    "search.suggest",\n',
        )
        .replace(
            "handlers.python.options.show_source = true\n",
            'handlers.python.options.show_source = true\nhandlers.python.options.members_order = "source"\n',
        )
        .replace("Add your project description here.", "A new default.")
        .replace("pymdownx.tilde = {}\n", "")
    )
    executor = run(mocker, changed)
    assert not conflicts(executor)
    project = local()
    assert project["theme"]["features"] == [
        *edited["theme"]["features"],
        "search.suggest",
    ]
    assert "navigation.top" not in project["theme"]["features"]
    options = project["plugins"]["mkdocstrings"]["handlers"]["python"]["options"]
    assert options["members_order"] == "source"
    # Seeded settings are the user's once written.
    for key in ("site_description", "nav", "markdown_extensions"):
        assert project[key] == edited[key]
    assert project["theme"]["palette"] == edited["theme"]["palette"]


def test_existing_mkdocs_configuration_is_not_displaced(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path("mkdocs.yml").write_text("site_name: Docs\n")
    for strategy in (CollisionStrategy.MERGE, CollisionStrategy.OVERWRITE):
        executor = run(mocker, strategy=strategy)
        assert not TARGET.exists()
        assert conflicts(executor) == [UNOWNED]


@pytest.mark.parametrize(
    "strategy", [CollisionStrategy.MERGE, CollisionStrategy.OVERWRITE]
)
def test_top_level_layout_is_left_alone(tmp_path, monkeypatch, mocker, strategy):
    monkeypatch.chdir(tmp_path)
    original = 'site_name = "Docs"\n\n[theme]\nfeatures = ["navigation.tabs"]\n'
    TARGET.write_text(original)
    executor = run(mocker, strategy=strategy)
    assert TARGET.read_text() == original
    assert conflicts(executor) == [UNOWNED]


def test_deleted_document_stays_deleted(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.unlink()
    executor = run(mocker)
    assert not TARGET.exists()
    assert not conflicts(executor)


def test_overwrite_reseeds_and_keeps_foreign_settings(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(mocker)
    TARGET.write_text(
        TARGET.read_text()
        .replace('    { "Home" = "index.md" },\n', '    { "Guide" = "guide.md" },\n')
        .replace(
            "[project.theme]\n", 'repo_url = "https://example.com"\n\n[project.theme]\n'
        )
    )
    run(mocker, strategy=CollisionStrategy.OVERWRITE)
    project = local()
    assert project["nav"] == [{"Home": "index.md"}]
    assert project["repo_url"] == "https://example.com"


def test_scaffold_lists_exactly_zensical_default_extensions():
    """Listing extensions replaces Zensical's defaults, so the scaffold mirrors them."""
    config = pytest.importorskip("zensical.config")
    extensions = tomllib.loads(scaffold())["project"]["markdown_extensions"]
    names = {
        f"pymdownx.{name}" if key == "pymdownx" else key
        for key, value in extensions.items()
        for name in (value if key == "pymdownx" else [key])
    }
    assert names == set(config.DEFAULT_MARKDOWN_EXTENSIONS)
