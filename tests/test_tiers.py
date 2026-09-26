"""Template tiers: a workbench and a production set of tool opinions."""

import json
from pathlib import Path
from typing import Any

import pytest

from protostar.config import TemplateBlueprint, TemplateSource
from protostar.errors import ConfigurationError
from protostar.recipe import decode_recipe, establish_recipe
from protostar.tiers import (
    TemplateTiers,
    Tier,
    parse_tiers,
    resolve_tier,
    template_opinions,
)

TIERS = """
tier = "workbench"

[tiers.workbench]
mypy = false
pytest = false

[tiers.production]
mypy = true
pytest = true
"""


def _data(text: str) -> dict[str, object]:
    import tomllib

    return tomllib.loads(text)


class TestParsing:
    def test_both_tiers_and_the_default_parse(self) -> None:
        tiers = parse_tiers(_data(TIERS), "t")
        assert tiers == TemplateTiers(
            Tier.WORKBENCH,
            (("mypy", False), ("pytest", False)),
            (("mypy", True), ("pytest", True)),
        )
        assert tiers.to_dict() == {
            "default": "workbench",
            "workbench": {"mypy": False, "pytest": False},
            "production": {"mypy": True, "pytest": True},
        }

    def test_a_template_without_tiers_has_none(self) -> None:
        assert parse_tiers(_data("ruff = true\n"), "t") is None

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ('tier = "workbench"\n', "need both a default tier and"),
            ("[tiers.workbench]\nmypy = true\n", "need both a default tier and"),
            ('tier = "lab"\n[tiers.workbench]\n', "names no tier: 'lab'"),
            (
                'tier = "workbench"\n[tiers.workbench]\nmypy = true\n',
                "exactly workbench and production",
            ),
            (
                'tier = "workbench"\n[tiers.workbench]\nmypy = true\n'
                "[tiers.production]\nmypy = true\n[tiers.staging]\nmypy = true\n",
                "exactly workbench and production",
            ),
            (
                'tier = "workbench"\n[tiers.workbench]\n[tiers.production]\n',
                "must be a table of tool flags",
            ),
            (
                'tier = "workbench"\n[tiers.workbench]\nstrict = true\n'
                "[tiers.production]\nstrict = true\n",
                "not a tool flag: strict",
            ),
            (
                'tier = "workbench"\n[tiers.workbench]\nmypy = "yes"\n'
                '[tiers.production]\nmypy = "yes"\n',
                "not a tool flag: mypy",
            ),
            (
                'tier = "workbench"\n[tiers.workbench]\nmypy = false\n'
                "[tiers.production]\nmypy = true\npytest = true\n",
                "set different tools: pytest",
            ),
            (
                'mypy = true\ntier = "workbench"\n[tiers.workbench]\nmypy = false\n'
                "[tiers.production]\nmypy = true\n",
                "sets mypy both at the root and in its tiers",
            ),
        ],
    )
    def test_malformed_tiers_are_rejected(self, text: str, message: str) -> None:
        with pytest.raises(ConfigurationError, match=message) as error:
            parse_tiers(_data(text), "t")
        assert error.value.hint

    def test_the_blueprint_and_the_raw_source_read_the_same_tiers(
        self, tmp_path: Path
    ) -> None:
        template = tmp_path / "protostar.toml"
        template.write_text("ruff = true\n" + TIERS)
        source = TemplateSource.load(str(template))
        blueprint = source.render({})
        assert source.tiers == blueprint.tiers
        assert blueprint.tooling_overrides == {"ruff": True}
        assert source.opinions(None) == blueprint.opinions(None)

    def test_docker_is_a_flag_a_tier_may_set(self) -> None:
        tiers = parse_tiers(
            _data(
                'tier = "production"\n[tiers.workbench]\ndocker = false\n'
                "[tiers.production]\ndocker = true\n"
            ),
            "t",
        )
        assert tiers is not None
        assert tiers.flags(Tier.PRODUCTION) == {"docker": True}


class TestResolution:
    def test_opinions_are_the_root_flags_then_the_tiers(self) -> None:
        tiers = parse_tiers(_data(TIERS), "t")
        root = {"ruff": True}
        assert template_opinions(root, tiers, None) == {
            "ruff": True,
            "mypy": False,
            "pytest": False,
        }
        assert template_opinions(root, tiers, Tier.PRODUCTION) == {
            "ruff": True,
            "mypy": True,
            "pytest": True,
        }
        assert template_opinions(root, None, Tier.PRODUCTION) == root

    def test_the_chosen_tier_beats_the_default(self) -> None:
        tiers = parse_tiers(_data(TIERS), "t")
        assert resolve_tier(tiers, None) is Tier.WORKBENCH
        assert resolve_tier(tiers, Tier.PRODUCTION) is Tier.PRODUCTION
        assert resolve_tier(None, None) is None

    def test_a_tier_for_a_template_without_tiers_is_an_error(self) -> None:
        with pytest.raises(ConfigurationError, match="declares no tiers") as error:
            resolve_tier(None, Tier.WORKBENCH)
        assert error.value.hint


class TestConditions:
    def test_content_can_require_a_tier(self) -> None:
        blueprint = TemplateBlueprint._parse(
            TIERS
            + '[[optional]]\nrequires = "tier=production"\ndependencies = ["x"]\n',
            "t",
        )
        assert str(blueprint.optional[0].requires) == "tier=production"

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("", "declares no tiers"),
            (TIERS, "the tier is one of: workbench, production"),
        ],
    )
    def test_a_tier_term_that_does_not_fit_is_rejected(
        self, text: str, message: str
    ) -> None:
        term = "tier" if text else "tier=production"
        with pytest.raises(ConfigurationError, match=message):
            TemplateBlueprint._parse(
                text + f'[[optional]]\nrequires = "{term}"\ndependencies = ["x"]\n',
                "t",
            )

    def test_an_option_named_tier_is_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="tool or the tier: tier"):
            TemplateBlueprint._parse(
                "[options.tier]\ndefault = false\n"
                '[[optional]]\nrequires = "tier"\ndependencies = ["x"]\n',
                "t",
            )


class TestRecipe:
    def test_a_recorded_tier_round_trips(self) -> None:
        from protostar.config import UserConfig
        from protostar.intent import TemplateOrigin, TemplateReference
        from protostar.recipe import RecipeIntent

        recipe = establish_recipe(
            UserConfig(),
            RecipeIntent(
                TemplateReference(TemplateOrigin.BUILT_IN, "cli", "digest"),
                tier=Tier.PRODUCTION,
            ),
        )
        assert recipe.to_dict()["tier"] == "production"
        assert decode_recipe(recipe.to_dict()).tier is Tier.PRODUCTION

    def test_an_unknown_or_template_less_tier_is_invalid(self) -> None:
        from protostar.config import UserConfig

        data = establish_recipe(UserConfig()).to_dict()
        with pytest.raises(ConfigurationError, match="Invalid"):
            decode_recipe({**data, "tier": "workbench"})
        data = {
            **data,
            "mode": "template",
            "source": {"origin": "built-in", "locator": "cli"},
        }
        assert decode_recipe(data).tier is None
        with pytest.raises(ConfigurationError, match="Invalid"):
            decode_recipe({**data, "tier": "lab"})


TEMPLATE = """
ruff = false
direnv = false
just = false
tier = "workbench"

[tiers.workbench]
pytest = false

[tiers.production]
pytest = true

[[optional]]
requires = "tier=production"
files = ["tests/test_smoke.py"]

[files]
"tests/test_smoke.py" = "def test_smoke():\\n    assert True\\n"
"README.md" = "demo\\n"
"""


def _resolve(_runner, command, *, timeout):
    """Stands in for uv: records added packages and writes the lock."""
    import tomlkit

    if command[:2] == ["uv", "add"]:
        doc = tomlkit.parse(Path("pyproject.toml").read_text())
        args = command[2:]
        if args[0] == "--dev":
            entries = doc.setdefault("dependency-groups", {}).setdefault("dev", [])
            args = args[1:]
        elif args[0] == "--group":
            groups = doc.setdefault("dependency-groups", {})
            entries = groups.setdefault(args[1], [])
            args = args[2:]
        else:
            entries = doc["project"].setdefault("dependencies", [])
        entries.extend(package + ">=1" for package in args)
        Path("pyproject.toml").write_text(tomlkit.dumps(doc))
    Path("uv.lock").write_text("resolved")


def _run(monkeypatch, capsys, *args):
    from protostar.cli import main, ui

    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", *args, "--json"])
    main()
    return json.loads(capsys.readouterr().out.splitlines()[-1])


@pytest.fixture
def demo(tmp_path, monkeypatch, mocker) -> Path:
    """A trusted ``demo`` alias to TEMPLATE, and an empty project to apply it in."""
    template = tmp_path / "template" / "protostar.toml"
    template.parent.mkdir()
    template.write_text(TEMPLATE)
    config = tmp_path / "config.toml"
    config.write_text(
        f'[templates.demo]\nsource = "{template.as_posix()}"\ntrusted = true\n'
    )
    monkeypatch.setenv("PROTOSTAR_CONFIG", str(config))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    mocker.patch(
        "protostar.system.ProcessRunner.run", autospec=True, side_effect=_resolve
    )
    mocker.patch("protostar.lifecycle.resolve_hook_revisions", return_value=())
    return template


def _recipe() -> dict[str, Any]:
    import tomllib

    return tomllib.loads(Path("pyproject.toml").read_text())["tool"]["protostar"]


def test_a_project_follows_the_default_tier_until_it_chooses(demo, monkeypatch, capsys):
    payload = _run(monkeypatch, capsys, "init", "--template", "demo")
    assert payload["status"] == "success"
    assert "tier" not in _recipe()
    assert not _recipe().get("tools", {}).get("pytest")
    assert not Path("tests/test_smoke.py").exists()

    payload = _run(monkeypatch, capsys, "sync", "--tier", "production")
    assert payload["status"] == "success"
    assert _recipe()["tier"] == "production"
    assert Path("tests/test_smoke.py").exists()
    assert "pytest" in Path("pyproject.toml").read_text()

    # The recorded tier holds on a plain sync.
    _run(monkeypatch, capsys, "sync")
    assert _recipe()["tier"] == "production"
    assert Path("tests/test_smoke.py").exists()

    # A flag pins its tier, even the default.
    _run(monkeypatch, capsys, "sync", "--tier", "workbench")
    assert _recipe()["tier"] == "workbench"
    assert not Path("tests/test_smoke.py").exists()


def test_init_records_a_pinned_tier(demo, monkeypatch, capsys):
    payload = _run(
        monkeypatch, capsys, "init", "--template", "demo", "--tier", "production"
    )
    assert payload["status"] == "success"
    assert _recipe()["tier"] == "production"
    assert Path("tests/test_smoke.py").exists()


def test_an_explicit_tool_flag_beats_the_tier(demo, monkeypatch, capsys):
    _run(
        monkeypatch,
        capsys,
        "init",
        "--template",
        "demo",
        "--tier",
        "production",
        "--no-pytest",
    )
    assert _recipe()["tools"] == {"pytest": False}
    # Content gated on the tier still follows the tier.
    assert Path("tests/test_smoke.py").exists()


def test_a_template_that_drops_its_tiers_drops_the_recorded_tier(
    demo, monkeypatch, capsys
):
    _run(monkeypatch, capsys, "init", "--template", "demo", "--tier", "production")
    demo.write_text(
        'ruff = false\ndirenv = false\njust = false\n[files]\n"README.md" = "demo\\n"\n'
    )
    payload = _run(monkeypatch, capsys, "sync")
    assert payload["status"] == "success"
    assert "tier" not in _recipe()


def test_tier_needs_a_template_that_declares_tiers(tmp_path, monkeypatch, capsys):
    from protostar.cli import main, ui

    template = tmp_path / "protostar.toml"
    template.write_text('[files]\n"README.md" = "demo\\n"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ui, "is_json_mode", False)
    for args, message in (
        (["--from", str(template)], "declares no tiers"),
        ([], "--tier needs a template"),
    ):
        monkeypatch.setattr(
            "sys.argv", ["protostar", "init", *args, "--tier", "workbench", "--json"]
        )
        with pytest.raises(SystemExit):
            main()
        error = json.loads(capsys.readouterr().out)
        assert message in error["error"]["message"]


def test_an_unknown_tier_is_refused_by_the_parser(tmp_path, monkeypatch, capsys):
    from protostar.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--tier", "lab"])
    with pytest.raises(SystemExit):
        main()
    assert "invalid choice: 'lab'" in capsys.readouterr().out


def test_the_listing_shows_each_templates_tiers(demo, monkeypatch, capsys):
    from protostar.cli import main, ui

    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--list-templates", "--json"])
    with pytest.raises(SystemExit):
        main()
    listed = {t["alias"]: t for t in json.loads(capsys.readouterr().out)["templates"]}
    assert listed["demo"]["tiers"] == {
        "default": "workbench",
        "workbench": {"pytest": False},
        "production": {"pytest": True},
    }
    assert listed["cli"]["tiers"] is None

    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--list-templates"])
    with pytest.raises(SystemExit):
        main()
    assert "workbench tier" in capsys.readouterr().out
