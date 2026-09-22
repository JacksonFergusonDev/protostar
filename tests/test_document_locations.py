"""The resolver deciding which file holds a document, and the catalog it reads."""

import pytest

from protostar.documents import (
    LOCATIONS,
    YAML_DOCUMENTS,
    codecov,
    document_locations,
    github_workflows,
    pre_commit,
    readthedocs,
    renovate,
    yaml_spec,
    zensical,
)
from protostar.documents.locations import (
    DocumentLocations,
    Resolution,
    resolve_location,
)
from protostar.merge import ConflictReason, MergeConflict, MergeLocation
from protostar.workflows import HookRunner

DOC = DocumentLocations("a.yaml", aliases=("a.yml",), competitors=("a.json5",))
SHARED = DocumentLocations("w.yml", aliases=("w.yaml",), exclusive=False)


def resolve(locations, present, owned=()):
    return resolve_location(locations, set(owned), lambda path: path in present)


def duplicate(path):
    return MergeConflict(MergeLocation(path), ConflictReason.DUPLICATE_IDENTITY)


def test_absent_document_is_created_at_its_target():
    assert resolve(DOC, set()) == Resolution("a.yaml", None)


def test_single_alias_is_adopted_in_place():
    assert resolve(DOC, {"a.yml"}) == Resolution("a.yml", None)


def test_owned_file_is_edited_in_place():
    assert resolve(DOC, {"a.yml"}, owned={"a.yml"}) == Resolution("a.yml", "a.yml")


@pytest.mark.parametrize(("old", "new"), [("a.yaml", "a.yml"), ("a.yml", "a.yaml")])
def test_rename_is_followed_with_its_ownership(old, new):
    assert resolve(DOC, {new}, owned={old}) == Resolution(new, old)


def test_deleted_owned_file_keeps_its_record():
    assert resolve(DOC, set(), owned={"a.yml"}) == Resolution("a.yml", "a.yml")


def test_competing_copy_next_to_an_owned_file_is_reported():
    assert resolve(DOC, {"a.yaml", "a.yml", "a.json5"}, owned={"a.yaml"}) == (
        Resolution("a.yaml", "a.yaml", (duplicate("a.yml"), duplicate("a.json5")))
    )


def test_several_unowned_configurations_are_held():
    assert resolve(DOC, {"a.yaml", "a.yml"}) == Resolution(
        None, None, (duplicate("a.yaml"), duplicate("a.yml"))
    )


def test_editable_file_next_to_a_competitor_is_held_when_unowned():
    assert resolve(DOC, {"a.yml", "a.json5"}) == Resolution(
        None, None, (duplicate("a.yml"), duplicate("a.json5"))
    )


def test_competitor_alone_holds_the_document_as_unowned():
    held = MergeConflict(MergeLocation("a.yaml"), ConflictReason.UNOWNED)
    assert resolve(DOC, {"a.json5"}) == Resolution(None, None, (held,))
    assert resolve(DOC, {"a.json5"}, owned={"a.yaml"}) == Resolution(
        None, "a.yaml", (held,)
    )


def test_tool_reading_every_file_never_conflicts():
    assert resolve(SHARED, {"w.yml", "w.yaml"}) == Resolution("w.yml", None)
    assert resolve(SHARED, {"w.yaml"}) == Resolution("w.yaml", None)
    assert resolve(SHARED, {"w.yml", "w.yaml"}, owned={"w.yaml"}) == Resolution(
        "w.yaml", "w.yaml"
    )
    assert resolve(SHARED, {"w.yml"}, owned={"w.yaml"}) == Resolution("w.yml", "w.yaml")
    assert resolve(SHARED, set(), owned={"w.yaml"}) == Resolution("w.yaml", "w.yaml")


def test_first_existing_record_is_the_owner():
    assert resolve(DOC, {"a.yml"}, owned={"a.yaml", "a.yml"}) == Resolution(
        "a.yml", "a.yml"
    )


# --- Catalog -----------------------------------------------------------------


def documents():
    """Every document's locations, with pre-commit's runner variants merged."""
    variants = pre_commit.LOCATIONS.values()
    merged = DocumentLocations(
        pre_commit.TARGET,
        aliases=tuple({p for v in variants for p in v.aliases}),
        competitors=tuple({p for v in variants for p in v.competitors}),
    )
    return [*LOCATIONS.values(), merged]


def test_registry_keys_documents_by_target():
    for target, locations in LOCATIONS.items():
        assert locations.target == target
    for locations in pre_commit.LOCATIONS.values():
        assert locations.target == pre_commit.TARGET


def test_no_path_belongs_to_two_documents():
    paths = [path for locations in documents() for path in set(locations.paths)]
    assert len(paths) == len(set(paths))
    for locations in (*LOCATIONS.values(), *pre_commit.LOCATIONS.values()):
        assert len(locations.paths) == len(set(locations.paths))


def test_yaml_spec_covers_every_editable_name_and_no_competitor():
    for locations in documents():
        spec = YAML_DOCUMENTS.get(locations.target)
        for path in locations.editable:
            assert yaml_spec(path) is spec
    for path in ("prek.toml", "mkdocs.yml", "renovate.json5"):
        assert yaml_spec(path) is None
    assert yaml_spec(".pre-commit-config.yml") is pre_commit.SPEC


def test_pre_commit_paths_depend_on_the_hook_runner():
    upstream = document_locations(pre_commit.TARGET, HookRunner.PRE_COMMIT)
    assert upstream.aliases == ()
    assert upstream.competitors == (".pre-commit-config.yml",)
    prek = document_locations(pre_commit.TARGET, HookRunner.PREK)
    assert prek.aliases == (".pre-commit-config.yml",)
    assert prek.competitors == ("prek.toml",)
    assert document_locations(pre_commit.TARGET, HookRunner.NONE) == (
        DocumentLocations(pre_commit.TARGET)
    )


def test_documents_read_from_one_path_have_only_their_target():
    assert document_locations("pyproject.toml", HookRunner.NONE) == (
        DocumentLocations("pyproject.toml")
    )


def test_declared_tool_locations():
    assert set(readthedocs.LOCATIONS.aliases) == {
        ".readthedocs.yml",
        "readthedocs.yaml",
        "readthedocs.yml",
    }
    names = {"codecov.yml", ".codecov.yml", "codecov.yaml", ".codecov.yaml"}
    assert set(codecov.LOCATIONS.editable) == {
        folder + name for folder in ("", "dev/", ".github/") for name in names
    }
    assert github_workflows.CI_LOCATIONS.aliases == (".github/workflows/ci.yaml",)
    assert not github_workflows.CI_LOCATIONS.exclusive
    assert not github_workflows.RELEASE_LOCATIONS.exclusive
    assert all(path.endswith(".json5") for path in renovate.LOCATIONS.competitors)
    assert not any(".gitlab/" in path for path in renovate.LOCATIONS.paths)
    assert zensical.LOCATIONS.competitors == ("mkdocs.yml", "mkdocs.yaml")
