"""Which templates are trusted, and the screen that confirms an untrusted sync."""

import pytest
from textual.widgets import Button

from protostar.cli.tui.app import DecisionApp
from protostar.cli.tui.keys import LeaveScreen
from protostar.cli.tui.trust import TrustScreen
from protostar.config import TemplateAliasConfig, UserConfig
from protostar.intent import DependencyGroup, ResolverFootprint, TemplateOrigin
from protostar.preparation import ResolverAction
from protostar.recipe import RecipeSource

REPOSITORY = "https://github.com/acme/templates"
COMMANDS = (("uv", "add", "fastapi"), ("uv", "run", "prek", "install"))


def config(source, *, trusted=True):
    return UserConfig(
        templates={"team": TemplateAliasConfig(source=source, trusted=trusted)}
    )


def remote(path=""):
    return RecipeSource(TemplateOrigin.REMOTE, REPOSITORY, path, "v1.0.0")


def test_a_built_in_template_is_always_trusted(tmp_path):
    source = RecipeSource(TemplateOrigin.BUILT_IN, "cli")
    assert source.trusted_by(UserConfig(), tmp_path)


def test_a_local_template_is_trusted_by_an_alias_to_its_directory(tmp_path):
    template = tmp_path / "team"
    template.mkdir()
    (template / "protostar.toml").write_text("")
    source = RecipeSource(TemplateOrigin.LOCAL, "team/protostar.toml")
    assert source.trusted_by(config(str(template)), tmp_path)
    assert source.trusted_by(config(str(template / "protostar.toml")), tmp_path)
    assert not source.trusted_by(config(str(template), trusted=False), tmp_path)
    assert not source.trusted_by(config(str(tmp_path / "other")), tmp_path)
    assert not source.trusted_by(UserConfig(), tmp_path)


@pytest.mark.parametrize(
    ("alias", "path", "trusted"),
    [
        (REPOSITORY, "", True),
        (f"{REPOSITORY}/tree/v2.0.0", "", True),
        (f"{REPOSITORY}/blob/main/protostar.toml", "", True),
        (f"{REPOSITORY}/tree/main/services/api", "services/api", True),
        (
            "https://raw.githubusercontent.com/acme/templates/main/services/api/protostar.toml",
            "services/api",
            True,
        ),
        # Another template in the same repository trusts nothing here.
        (f"{REPOSITORY}/tree/main/services/web", "services/api", False),
        (REPOSITORY, "services/api", False),
        # A subdirectory or a slashed branch can't be told apart without the
        # repository's refs, so the root template is not trusted by it.
        (f"{REPOSITORY}/tree/feature/x", "", False),
        ("https://github.com/acme/other", "", False),
        ("https://github.com/acme/templates?x=1", "", False),
    ],
)
def test_a_repository_template_is_trusted_only_by_an_alias_naming_it(
    tmp_path, alias, path, trusted
):
    assert remote(path).trusted_by(config(alias), tmp_path) is trusted


def test_a_remote_alias_never_trusts_a_local_template(tmp_path):
    source = RecipeSource(TemplateOrigin.LOCAL, "team/protostar.toml")
    assert not source.trusted_by(config(REPOSITORY), tmp_path)
    assert not remote().trusted_by(config(str(tmp_path)), tmp_path)


@pytest.mark.asyncio
async def test_the_trust_screen_applies_only_once_confirmed():
    app = DecisionApp(TrustScreen(COMMANDS))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        apply = app.screen.query_one("#apply", Button)
        assert apply.disabled
        await pilot.press("a")
        assert app.is_running
        await pilot.press("t")
        assert not apply.disabled
        await pilot.press("t")
        assert apply.disabled
        await pilot.press("t", "a")
    assert app.return_value == COMMANDS


@pytest.mark.asyncio
async def test_escape_on_the_trust_screen_asks_before_leaving():
    app = DecisionApp(TrustScreen(COMMANDS))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        assert isinstance(app.screen, LeaveScreen)
        await pilot.press("enter")
    assert app.return_value is None


def test_trust_screen_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = DecisionApp(TrustScreen(COMMANDS))
    assert snap_compare(app, terminal_size=(100, 30))


@pytest.mark.parametrize(
    ("requirements", "lock_required", "commands"),
    [
        (
            ((DependencyGroup.MAIN, ("fastapi",)), (DependencyGroup.DEV, ("pytest",))),
            False,
            (("uv", "add", "fastapi"), ("uv", "add", "--dev", "pytest")),
        ),
        ((), True, (("uv", "lock"),)),
        ((), False, ()),
    ],
)
def test_a_review_lists_the_resolver_commands_it_runs(
    requirements, lock_required, commands
):
    action = ResolverAction(
        requirements, frozenset(), lock_required, ResolverFootprint()
    )
    assert action.commands == commands
