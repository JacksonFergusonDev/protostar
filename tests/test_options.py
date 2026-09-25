"""Template options and the ``requires`` conditions that gate content on them."""

import json
from pathlib import Path

import pytest

from protostar.config import TemplateBlueprint, TemplateSource
from protostar.errors import (
    ConfigurationError,
    InvalidOptionValueError,
    TemplateResolutionError,
)
from protostar.options import (
    Condition,
    OptionValue,
    TemplateOption,
    Term,
    parse_condition,
    parse_options,
    resolve_options,
)

DATABASE = TemplateOption("database", "none", ("none", "postgres", "sqlite"))
COMPOSE = TemplateOption("compose", False)


class TestCondition:
    def test_a_single_term_or_an_array_of_terms_parses(self) -> None:
        assert parse_condition("pytest", "x", "t") == Condition((Term("pytest"),))
        assert parse_condition(["compose", "database=postgres"], "x", "t") == Condition(
            (Term("compose"), Term("database", "postgres"))
        )

    @pytest.mark.parametrize(
        "raw", [[], 5, [5], "", "a b", "=x", "database=", "database=a=b", "database=-x"]
    )
    def test_a_malformed_requires_is_rejected(self, raw: object) -> None:
        with pytest.raises(ConfigurationError, match="Invalid requires"):
            parse_condition(raw, "x", "t")

    def test_every_term_must_hold(self) -> None:
        condition = parse_condition(
            ["pytest", "compose", "database=postgres"], "x", "t"
        )
        options: dict[str, OptionValue] = {"compose": True, "database": "postgres"}
        assert condition.holds({"pytest"}, options)
        assert not condition.holds(set(), options)
        assert not condition.holds({"pytest"}, {**options, "compose": False})
        assert not condition.holds({"pytest"}, {**options, "database": "sqlite"})

    def test_a_bare_term_never_matches_a_choice_value(self) -> None:
        # A choice option holding a truthy string is not "on".
        assert not Term("database").holds(set(), {"database": "postgres"})


class TestOptions:
    def test_bool_and_choice_options_parse(self) -> None:
        options = parse_options(
            {
                "compose": {"default": False, "description": "Ship compose."},
                "database": {"choices": ["none", "postgres"], "default": "none"},
            },
            "t",
        )
        assert options["compose"] == TemplateOption(
            "compose", False, description="Ship compose."
        )
        assert options["database"] == TemplateOption(
            "database", "none", ("none", "postgres")
        )

    @pytest.mark.parametrize(
        "raw",
        [
            {"compose": {"description": "no default"}},
            {"compose": {"default": "yes"}},
            {"compose": {"default": False, "type": "bool"}},
            {"compose": {"default": False, "description": 5}},
            {"database": {"choices": ["only"], "default": "only"}},
            {"database": {"choices": ["a", "a"], "default": "a"}},
            {"database": {"choices": ["a", "b c"], "default": "a"}},
            {"database": {"choices": ["a", "b"], "default": "c"}},
            {"database": {"choices": ["a", "b"], "default": True}},
            {"bad-name": {"default": False}},
            {"compose": False},
        ],
    )
    def test_a_malformed_option_is_rejected(self, raw: dict[str, object]) -> None:
        with pytest.raises(ConfigurationError):
            parse_options(raw, "t")

    def test_command_line_values_parse_to_the_option_type(self) -> None:
        assert COMPOSE.parse("true") is True
        assert COMPOSE.parse("False") is False
        assert DATABASE.parse("postgres") == "postgres"
        with pytest.raises(InvalidOptionValueError) as bool_error:
            COMPOSE.parse("yes")
        assert bool_error.value.values == ("true", "false")
        with pytest.raises(InvalidOptionValueError) as choice_error:
            DATABASE.parse("mysql")
        assert choice_error.value.details() == {
            "option": "database",
            "values": ["none", "postgres", "sqlite"],
        }

    def test_a_recorded_value_of_the_wrong_type_is_rejected(self) -> None:
        with pytest.raises(InvalidOptionValueError):
            COMPOSE.check("true")
        with pytest.raises(InvalidOptionValueError):
            DATABASE.check(True)

    def test_unchosen_options_take_their_defaults(self) -> None:
        options = {"compose": COMPOSE, "database": DATABASE}
        assert resolve_options(options, {}) == {"compose": False, "database": "none"}
        assert resolve_options(options, {"database": "sqlite"}) == {
            "compose": False,
            "database": "sqlite",
        }

    def test_a_value_for_an_option_the_template_lacks_is_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="no option named cache"):
            resolve_options({"compose": COMPOSE}, {"cache": True})


OPTIONS = """
[options.compose]
default = false

[options.database]
choices = ["none", "postgres"]
default = "none"
"""


class TestTemplateValidation:
    def test_conditions_on_every_gated_kind_parse(self) -> None:
        blueprint = TemplateBlueprint._parse(
            OPTIONS
            + """
[[optional]]
requires = "database=postgres"
dependencies = ["psycopg"]

[[optional]]
requires = ["compose", "pytest"]
dev_dependencies = ["pytest-docker"]

[dev.pyproject.db]
requires = "database=postgres"
content = "[tool.example]\\ndb = true"

[appends.".envrc".compose]
requires = "compose"
content = "export COMPOSE=1"
""",
            "t",
        )
        assert str(blueprint.pyproject_injections["db"].requires) == "database=postgres"
        assert str(blueprint.appends[".envrc"]["compose"].requires) == "compose"
        assert [str(block.requires) for block in blueprint.optional] == [
            "database=postgres",
            "compose, pytest",
        ]

    @pytest.mark.parametrize(
        ("requires", "message"),
        [
            ('"cache"', "neither a tool nor a declared option"),
            ('"database"', "is a choice among: none, postgres"),
            ('"database=mysql"', "is a choice among"),
            ('"compose=true"', "is on or off"),
            ('"pytest=yes"', "neither a tool nor a declared option"),
        ],
    )
    def test_a_term_that_does_not_fit_is_rejected(
        self, requires: str, message: str
    ) -> None:
        with pytest.raises(ConfigurationError, match=message):
            TemplateBlueprint._parse(
                OPTIONS
                + f'[[optional]]\nrequires = {requires}\ndependencies = ["x"]\n'
                + '[[optional]]\nrequires = ["compose", "database=none"]\n'
                + 'dependencies = ["y"]\n',
                "t",
            )

    def test_an_option_no_condition_names_is_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="no requires names: database"):
            TemplateBlueprint._parse(
                OPTIONS + '[[optional]]\nrequires = "compose"\ndependencies = ["x"]\n',
                "t",
            )

    def test_an_option_named_like_a_tool_is_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="share a name with a tool: ruff"):
            TemplateBlueprint._parse(
                "[options.ruff]\ndefault = false\n"
                '[[optional]]\nrequires = "ruff"\ndependencies = ["x"]\n',
                "t",
            )

    def test_an_option_named_like_a_variable_is_rejected(self, tmp_path) -> None:
        template = tmp_path / "protostar.toml"
        template.write_text(
            "[options.region]\ndefault = false\n"
            '[[optional]]\nrequires = "region"\ndependencies = ["x"]\n'
            '[files]\n"a.txt" = "<% region %>"\n'
        )
        with pytest.raises(
            TemplateResolutionError, match="share a name with variables"
        ):
            _ = TemplateSource.load(str(template)).options

    def test_optional_files_must_be_shipped(self, tmp_path) -> None:
        template = tmp_path / "protostar.toml"
        template.write_text(
            OPTIONS.split("[options.database]")[0]
            + '[[optional]]\nrequires = "compose"\nfiles = ["compose.yaml"]\n'
        )
        with pytest.raises(ConfigurationError, match="doesn't ship"):
            TemplateSource.load(str(template)).render({})

    def test_optional_files_cover_template_directories(self, tmp_path) -> None:
        (tmp_path / "template" / "db").mkdir(parents=True)
        (tmp_path / "template" / "db" / "schema.sql").write_text("create table x;\n")
        (tmp_path / "template" / "README.md").write_text("hi\n")
        template = tmp_path / "protostar.toml"
        template.write_text(
            OPTIONS.split("[options.database]")[0]
            + '[[optional]]\nrequires = "compose"\nfiles = ["db/"]\n'
        )
        blueprint = TemplateSource.load(str(template)).render({})
        assert [len(blueprint.gated(path)) for path in sorted(blueprint.files)] == [
            0,
            1,
        ]


TEMPLATE = """
ruff = false
pytest = false

[options.compose]
description = "Ship a compose.yaml."
default = false

[options.database]
choices = ["none", "postgres"]
default = "none"

[[optional]]
requires = "database=postgres"
dependencies = ["psycopg"]

[[optional]]
requires = "compose"
files = ["compose.yaml"]

[files]
"compose.yaml" = "services: {}\\n"
"README.md" = "demo\\n"

[dev.pyproject.database]
requires = "database=postgres"
content = "[tool.example]\\ndatabase = true"

[appends.".envrc".compose]
requires = "compose"
content = "export COMPOSE=1"
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


def test_options_choose_content_at_init_and_again_on_sync(
    tmp_path, monkeypatch, capsys, mocker
):
    import tomllib

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

    def pyproject():
        return tomllib.loads(Path("pyproject.toml").read_text())

    payload = _run(
        monkeypatch,
        capsys,
        "init",
        "--template",
        "demo",
        "--option",
        "database=postgres",
    )
    assert payload["status"] == "success"
    assert pyproject()["project"]["dependencies"] == ["psycopg>=1"]
    assert pyproject()["tool"]["example"] == {"database": True}
    assert pyproject()["tool"]["protostar"]["options"] == {"database": "postgres"}
    assert not Path("compose.yaml").exists()
    assert "COMPOSE" not in (
        Path(".envrc").read_text() if Path(".envrc").exists() else ""
    )

    payload = _run(
        monkeypatch,
        capsys,
        "sync",
        "--option",
        "compose=true",
        "--option",
        "database=none",
    )
    assert payload["status"] == "success"
    assert Path("compose.yaml").read_text() == "services: {}\n"
    assert "export COMPOSE=1" in Path(".envrc").read_text()
    assert pyproject()["project"]["dependencies"] == []
    assert "example" not in pyproject()["tool"]
    # A flag pins its value, even the default, like a tool flag.
    assert pyproject()["tool"]["protostar"]["options"] == {
        "compose": True,
        "database": "none",
    }

    _run(monkeypatch, capsys, "sync", "--option", "compose=false")
    assert not Path("compose.yaml").exists()
    assert "COMPOSE" not in Path(".envrc").read_text()

    # A template that stops offering an option drops its recorded value.
    template.write_text(
        TEMPLATE.split("[options.database]")[0]
        + '[[optional]]\nrequires = "compose"\nfiles = ["compose.yaml"]\n'
        + '[files]\n"compose.yaml" = "services: {}\\n"\n"README.md" = "demo\\n"\n'
    )
    _run(monkeypatch, capsys, "sync")
    assert pyproject()["tool"]["protostar"]["options"] == {"compose": False}


def test_an_unknown_or_invalid_option_flag_is_refused(tmp_path, monkeypatch, capsys):
    from protostar.cli import main, ui

    template = tmp_path / "protostar.toml"
    template.write_text(TEMPLATE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ui, "is_json_mode", False)
    for flag, message in (
        ("cache=true", "no option named 'cache'"),
        ("database=mysql", "has no value 'mysql'"),
        ("compose", "must be NAME=VALUE"),
    ):
        monkeypatch.setattr(
            "sys.argv",
            ["protostar", "init", "--from", str(template), "--option", flag, "--json"],
        )
        with pytest.raises(SystemExit):
            main()
        error = json.loads(capsys.readouterr().out)
        assert message in error["error"]["message"]
