"""Community health files: their content, where they land, and who renders them."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from protostar.community import (
    CommunitySpec,
    generate_bug_report_form,
    generate_code_of_conduct,
    generate_feature_request_form,
    generate_issue_config,
    generate_security_policy,
)
from protostar.config import UserConfig
from protostar.documents import community
from protostar.executor import SystemExecutor
from protostar.intent import AppendContribution
from protostar.manifest import EnvironmentManifest
from protostar.merge import ConflictReason
from protostar.modules import CommitizenModule, CommunityModule, JustModule
from protostar.orchestrator import CONTRIBUTING_REGION_ID, Orchestrator
from protostar.recipe import Tool
from protostar.sync_state import deserialize_state
from protostar.workflows import TargetOS

HOSTED = CommunitySpec(
    contact_email="ada@example.com",
    repository_url="https://github.com/ada/engine",
    supported_os=(TargetOS.LINUX, TargetOS.MACOS),
)
UNHOSTED = CommunitySpec(contact_email=None, repository_url=None, supported_os=())
STATE = Path("protostar.lock")


def load_yaml(text):
    return YAML(typ="safe").load(text)


# --- Generators ------------------------------------------------------------


def test_code_of_conduct_is_the_contributor_covenant_naming_the_contact():
    content = generate_code_of_conduct(HOSTED)

    assert content.startswith("# Contributor Covenant Code of Conduct\n")
    assert "version 2.1" in content
    assert "enforcement at <ada@example.com>." in content
    assert "[INSERT CONTACT METHOD]" not in content
    # Dash markers, as every scaffolded Markdown linter requires.
    assert "\n* " not in content


def test_code_of_conduct_keeps_the_placeholder_without_a_contact():
    assert "[INSERT CONTACT METHOD]" in generate_code_of_conduct(UNHOSTED)


def test_security_policy_routes_reports_privately():
    content = generate_security_policy(HOSTED)

    assert content.startswith("# Security Policy\n")
    assert "https://github.com/ada/engine/security/advisories/new" in content
    assert "by email to <ada@example.com>" in content


def test_security_policy_without_a_host_or_contact_still_routes_privately():
    content = generate_security_policy(UNHOSTED)

    assert "Report them to the maintainers privately." in content
    assert "advisories" not in content


def test_bug_report_form_offers_the_supported_platforms():
    form = load_yaml(generate_bug_report_form(HOSTED))

    [platform] = [field for field in form["body"] if field.get("id") == "os"]
    assert platform["type"] == "dropdown"
    assert platform["attributes"]["options"] == ["Linux", "MacOS", "Other"]
    [version] = [field for field in form["body"] if field.get("id") == "version"]
    assert version["attributes"]["label"] == "<% PROJECT_NAME %> version"


def test_bug_report_form_asks_for_a_platform_without_supported_ones():
    form = load_yaml(generate_bug_report_form(UNHOSTED))

    [platform] = [field for field in form["body"] if field.get("id") == "os"]
    assert platform["type"] == "input"


def test_feature_request_form_asks_for_the_problem_first():
    form = load_yaml(generate_feature_request_form())

    assert form["labels"] == ["enhancement"]
    assert form["body"][0]["id"] == "problem"


def test_issue_config_links_private_reports_only_when_hosted():
    config = load_yaml(generate_issue_config(HOSTED))

    assert config["blank_issues_enabled"] is True
    assert config["contact_links"][0]["url"] == (
        "https://github.com/ada/engine/security/advisories/new"
    )
    assert generate_issue_config(UNHOSTED) is None


# --- Module ----------------------------------------------------------------


def test_community_module_declares_the_metadata_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest(
        metadata={
            "author_email": "ada@example.com",
            "github_username": "ada",
            "supported_os": ["Linux"],
        }
    )
    module = CommunityModule()
    assert module.config_key == Tool.COMMUNITY.value

    module.build(manifest)

    files = manifest.filesystem.file_injections
    assert manifest.tooling.wants_community
    assert set(files) == {
        community.CODE_OF_CONDUCT_TARGET,
        community.SECURITY_TARGET,
        community.BUG_REPORT_TARGET,
        community.FEATURE_REQUEST_TARGET,
        community.ISSUE_CONFIG_TARGET,
    }
    assert (
        f"github.com/ada/{tmp_path.name}/security" in files[community.SECURITY_TARGET]
    )
    # The tooling-derived files wait for every module to build.
    assert not manifest.filesystem.regions
    assert community.PULL_REQUEST_TARGET not in files


def test_community_module_skips_the_issue_config_without_a_host():
    manifest = EnvironmentManifest()

    CommunityModule().build(manifest)

    assert community.ISSUE_CONFIG_TARGET not in manifest.filesystem.file_injections


def test_commitizen_adopts_conventional_commits():
    manifest = EnvironmentManifest()

    CommitizenModule().build(manifest)

    assert manifest.tooling.conventional_commits


# --- Orchestration ---------------------------------------------------------


@pytest.fixture
def config() -> UserConfig:
    return UserConfig(python_version="3.13")


def test_plan_renders_the_guide_and_template_from_every_module(
    tmp_path, monkeypatch, config
):
    monkeypatch.chdir(tmp_path)
    engine = Orchestrator([CommunityModule(), CommitizenModule(), JustModule()], config)

    manifest = engine.plan()

    [region] = manifest.filesystem.regions[community.CONTRIBUTING_TARGET]
    assert region.id == CONTRIBUTING_REGION_ID
    assert region.content.startswith("# Contributing to <% PROJECT_NAME %>")
    assert "## Commit Messages" in region.content
    template = manifest.filesystem.file_injections[community.PULL_REQUEST_TARGET]
    assert "- [ ] Commit messages follow Conventional Commits." in template


def test_plan_attributes_the_guide_to_the_community_tool(tmp_path, monkeypatch, config):
    monkeypatch.chdir(tmp_path)
    manifest = Orchestrator([CommunityModule()], config).plan()

    region = [
        c
        for c in manifest.producer_contributions
        if c.path
        == (
            "filesystem",
            "regions",
            community.CONTRIBUTING_TARGET,
            CONTRIBUTING_REGION_ID,
        )
    ]
    assert [(c.producer, c.tool) for c in region] == [
        ("module:CommunityModule", Tool.COMMUNITY)
    ]


def test_plan_omits_community_files_unless_enabled(tmp_path, monkeypatch, config):
    monkeypatch.chdir(tmp_path)
    manifest = Orchestrator([CommitizenModule()], config).plan()

    assert community.CONTRIBUTING_TARGET not in manifest.filesystem.regions
    assert community.PULL_REQUEST_TARGET not in manifest.filesystem.file_injections


def test_plan_reports_an_existing_guide_under_github_as_a_collision(
    tmp_path, monkeypatch, config
):
    monkeypatch.chdir(tmp_path)
    Path(".github").mkdir()
    Path(".github/CONTRIBUTING.md").write_text("# Team notes\n")

    manifest = Orchestrator([CommunityModule()], config).plan()

    assert Path(".github/CONTRIBUTING.md") in manifest.collisions


# --- Placement -------------------------------------------------------------


@pytest.mark.parametrize("locations", community.LOCATIONS, ids=lambda loc: loc.target)
def test_no_two_locations_differ_only_by_case(locations):
    # On macOS and Windows such paths name one file, which would then look like
    # a duplicate of itself.
    folded = [path.casefold() for path in locations.paths]
    assert len(folded) == len(set(folded))


def community_intent():
    intent = EnvironmentManifest()
    CommunityModule().build(intent)
    intent.filesystem.add_region(
        community.CONTRIBUTING_TARGET,
        "# Contributing\n",
        identity=CONTRIBUTING_REGION_ID,
    )
    return intent


def run(intent, mocker):
    executor = SystemExecutor(intent, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    process.assert_not_called()
    return executor


def records():
    return {r.path: r for r in deserialize_state(STATE.read_text()).files}


def test_a_fresh_project_gets_every_file_at_its_target(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    run(community_intent(), mocker)

    for target in (
        community.CONTRIBUTING_TARGET,
        community.CODE_OF_CONDUCT_TARGET,
        community.SECURITY_TARGET,
        community.BUG_REPORT_TARGET,
        community.FEATURE_REQUEST_TARGET,
    ):
        assert Path(target).is_file(), target


def test_files_under_github_are_adopted_not_duplicated(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path(".github").mkdir()
    guide = Path(".github/CONTRIBUTING.md")
    conduct = Path(".github/CODE_OF_CONDUCT.md")
    guide.write_text("# Team notes\n")
    conduct.write_text("# Our conduct\n")

    run(community_intent(), mocker)

    assert not Path(community.CONTRIBUTING_TARGET).exists()
    assert not Path(community.CODE_OF_CONDUCT_TARGET).exists()
    assert guide.read_text().startswith("# Team notes\n")
    assert "# Contributing\n" in guide.read_text()
    assert conduct.read_text() == "# Our conduct\n"
    assert guide.as_posix() in records()


def test_a_markdown_issue_template_holds_its_form(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    folder = Path(".github/ISSUE_TEMPLATE")
    folder.mkdir(parents=True)
    (folder / "bug_report.md").write_text("---\nname: Bug\n---\n")

    executor = run(community_intent(), mocker)

    assert not Path(community.BUG_REPORT_TARGET).exists()
    assert Path(community.FEATURE_REQUEST_TARGET).exists()
    [held] = [d.conflict for d in executor.diagnostics if d.conflict is not None]
    assert held.location.file == community.BUG_REPORT_TARGET
    assert held.reason is ConflictReason.UNOWNED


def test_a_renamed_guide_keeps_its_region(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(community_intent(), mocker)
    moved = Path(".github/CONTRIBUTING.md")
    moved.parent.mkdir(exist_ok=True)
    Path(community.CONTRIBUTING_TARGET).rename(moved)
    Path(community.CODE_OF_CONDUCT_TARGET).rename(".github/CODE_OF_CONDUCT.md")

    intent = community_intent()
    intent.filesystem.regions[community.CONTRIBUTING_TARGET] = [
        AppendContribution(CONTRIBUTING_REGION_ID, "# Contributing guide\n")
    ]
    executor = run(intent, mocker)

    assert not [d for d in executor.diagnostics if d.conflict is not None]
    assert not Path(community.CONTRIBUTING_TARGET).exists()
    assert not Path(community.CODE_OF_CONDUCT_TARGET).exists()
    assert "# Contributing guide\n" in moved.read_text()
    owned = records()
    assert moved.as_posix() in owned
    assert community.CONTRIBUTING_TARGET not in owned
    assert ".github/CODE_OF_CONDUCT.md" in owned
    assert community.CODE_OF_CONDUCT_TARGET not in owned
