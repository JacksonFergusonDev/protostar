import json
import random
import string
import subprocess
import sys

import pytest

from protostar.cli.main import handle_init, main
from protostar.cli.parser import build_parser
from protostar.config import TemplateSource, UserConfig
from protostar.errors import (
    ConfigurationError,
    ExitCode,
    InvalidUsageError,
    SecretDetectedError,
)
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.secret_guard import (
    MAX_VALUE_LENGTH,
    Allowlist,
    AllowlistCondition,
    AllowlistTarget,
    Rule,
    RuleSet,
    SecretFinding,
    check_variable_values,
    credential_named,
    decode_rules,
    encode_rules,
    load_rules,
    scan_value,
    shannon_entropy,
)

# Tokens are built at test time, never written as literals: GitHub push
# protection and this repository's own gitleaks hook would flag them.
_RNG = random.Random(20260922)
_ALNUM = string.ascii_letters + string.digits
_HEX = "0123456789abcdef"


def _random(alphabet: str, length: int) -> str:
    return "".join(_RNG.choice(alphabet) for _ in range(length))


_PEM_LABEL = "PRIVATE" + " KEY"

TOKENS = {
    "github-pat": "ghp_" + _random(_ALNUM, 36),
    "github-fine-grained-pat": "github_pat_" + _random(_ALNUM + "_", 82),
    "github-app-token": "ghs_" + _random(_ALNUM, 36),
    "aws-access-token": "AKIA" + _random(string.ascii_uppercase + "234567", 16),
    "slack-bot-token": "xoxb-"
    + _random(string.digits, 12)
    + "-"
    + _random(string.digits, 12)
    + "-"
    + _random(_ALNUM, 24),
    "stripe-access-token": "sk_" + "live_" + _random(_ALNUM, 24),
    "openai-api-key": "sk-proj-"
    + _random(_ALNUM + "_-", 58)
    + "T3BlbkFJ"
    + _random(_ALNUM + "_-", 58),
    "anthropic-api-key": "sk-ant-api03-" + _random(_ALNUM + "_-", 93) + "AA",
    "gitlab-pat": "glpat-" + _random(_ALNUM + "_-", 20),
    "npm-access-token": "npm_" + _random(_ALNUM, 36),
    "pypi-upload-token": "pypi-" + "AgEIcHlwaS5vcmc" + _random(_ALNUM + "-_", 60),
    "gcp-api-key": "AIza" + _random(_ALNUM + "_-", 35),
    "private-key": f"-----BEGIN {_PEM_LABEL}-----\n"
    + _random(_ALNUM + "+/", 64)
    + "\n"
    + _random(_ALNUM + "+/", 64)
    + f"\n-----END {_PEM_LABEL}-----",
}


@pytest.mark.parametrize(("rule", "value"), sorted(TOKENS.items()))
def test_scan_value_flags_provider_tokens(rule, value):
    """A token alone triggers its rule, even under an innocuous variable name."""
    assert scan_value("org_name", value) == SecretFinding("org_name", rule)


def test_scan_value_applies_translated_posix_class():
    """The Airtable rule's [[:alnum:]] class is translated, so real tokens match.

    Python compiles the untranslated class with only a warning but never matches
    a real token. The rule's keyword gate needs "airtable" nearby, as in gitleaks.
    """
    value = "pat" + _random(_ALNUM, 14) + "." + _random(_HEX, 64)

    assert scan_value("airtable_base", value) == SecretFinding(
        "airtable_base", "airtable-personnal-access-token"
    )
    assert scan_value("org_name", value) is None


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("project_slug", "my-cool-app"),
        ("org_name", "Acme Corporation"),
        ("api_base_url", "https://api.example.com/v1"),
        ("database_url", "postgres://localhost:5432/app"),
        ("version", "2.0.0-rc.1"),
        ("release_tag", "v1.0-" + _random(_HEX, 40)),
        ("commit_sha", _random(_HEX, 40)),
        ("instance_id", "3f1c2a9e-8b7d-4c6e-9f10-2a3b4c5d6e7f"),
        ("contact_email", "dev@example.com"),
        ("port", "8080"),
        ("order_ref", "123456789012345|abcdefghijklmnopqrstuvwxyz01234"),
        ("description", "Turns meeting notes into slide decks"),
        ("token_limit", "4096"),
    ],
)
def test_scan_value_leaves_ordinary_values_alone(name, value):
    """Everyday settings pass, including shapes that unfiltered rules would flag.

    Without the keyword gate, the order reference reads as a Facebook token and
    the release tag as a Sourcegraph token.
    """
    assert scan_value(name, value) is None


def test_scan_value_ignores_gitleaks_allow_marker():
    """An inline gitleaks:allow marker is not an override."""
    value = TOKENS["github-pat"] + " gitleaks:allow"

    assert scan_value("org_name", value) == SecretFinding("org_name", "github-pat")


def test_check_variable_values_reports_every_flagged_variable_without_values():
    values = {
        "zeta": TOKENS["npm-access-token"],
        "alpha": TOKENS["github-pat"],
        "slug": "my-cool-app",
    }

    with pytest.raises(SecretDetectedError) as caught:
        check_variable_values(values)

    error = caught.value
    assert error.findings == (
        SecretFinding("alpha", "github-pat"),
        SecretFinding("zeta", "npm-access-token"),
    )
    assert error.details() == {
        "findings": [
            {"variable": "alpha", "rule": "github-pat"},
            {"variable": "zeta", "rule": "npm-access-token"},
        ]
    }
    rendered = " ".join([str(error), error.hint or "", json.dumps(error.details())])
    for value in values.values():
        if value != "my-cool-app":
            assert value not in rendered


def test_check_variable_values_accepts_clean_values():
    check_variable_values({"project_slug": "my-cool-app", "port": "8080"})


def test_check_variable_values_skips_allowed_variables():
    values = {"alpha": TOKENS["github-pat"], "zeta": TOKENS["npm-access-token"]}

    with pytest.raises(SecretDetectedError) as caught:
        check_variable_values(values, allowed={"alpha"})

    assert caught.value.findings == (SecretFinding("zeta", "npm-access-token"),)
    check_variable_values(values, allowed={"alpha", "zeta"})


def test_allowed_variables_still_obey_the_length_limit():
    with pytest.raises(ConfigurationError, match="notes"):
        check_variable_values(
            {"notes": "a" * (MAX_VALUE_LENGTH + 1)}, allowed={"notes"}
        )


def test_check_variable_values_caps_length_before_scanning(mocker):
    scan = mocker.patch("protostar.secret_guard.scan_value")

    with pytest.raises(ConfigurationError, match="notes"):
        check_variable_values({"notes": "a" * (MAX_VALUE_LENGTH + 1), "ok": "fine"})

    scan.assert_not_called()


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "db_password",
        "API_KEY",
        "apikey",
        "github_token",
        "client_secret",
        "secret_key",
        "aws_access_key",
        "private_key",
        "credentials",
    ],
)
def test_credential_named_flags_credential_names(name):
    assert credential_named([name, "project_slug"]) == (name,)


@pytest.mark.parametrize(
    "name",
    ["token_limit", "max_tokens", "password_min_length", "keyboard", "api_base_url"],
)
def test_credential_named_ignores_ordinary_names(name):
    assert credential_named([name]) == ()


@pytest.mark.parametrize(
    ("data", "expected"),
    [("", 0.0), ("aaaa", 0.0), ("ab", 1.0), ("abcd", 2.0), ("é", 0.5)],
)
def test_shannon_entropy_matches_gitleaks(data, expected):
    """gitleaks divides character counts by the UTF-8 byte length."""
    assert shannon_entropy(data) == pytest.approx(expected)


# --- Detector semantics, against synthetic rules -----------------------------


@pytest.fixture
def rules(mocker):
    """Replaces the generated rule set for one test."""

    def _install(*rules: Rule, global_allowlists: tuple[Allowlist, ...] = ()) -> None:
        mocker.patch(
            "protostar.secret_guard.load_rules",
            return_value=RuleSet(rules, global_allowlists),
        )

    return _install


def test_rule_runs_only_when_a_keyword_appears(rules):
    rules(Rule(rule_id="demo", pattern=r"zz\d{4}", keywords=("demo",)))

    assert scan_value("name", "zz1234") is None
    assert scan_value("demo_name", "zz1234") == SecretFinding("demo_name", "demo")


def test_rule_without_keywords_always_runs(rules):
    rules(Rule(rule_id="demo", pattern=r"zz\d{4}", keywords=()))

    assert scan_value("name", "zz1234") == SecretFinding("name", "demo")


def test_entropy_applies_to_the_first_non_empty_group(rules):
    rules(
        Rule(
            rule_id="demo",
            pattern=r"zz(?:(x+)|(\w+))",
            keywords=("zz",),
            entropy=2.0,
        )
    )

    # The first group is empty for "abcdefgh", so the second is the secret.
    assert scan_value("name", "zzabcdefgh") is not None
    assert scan_value("name", "zzxxxxxxxx") is None


def test_explicit_secret_group_is_used(rules):
    rules(
        Rule(
            rule_id="demo",
            pattern=r"zz(\w+)-(\w+)",
            keywords=("zz",),
            entropy=2.0,
            secret_group=2,
        )
    )

    assert scan_value("name", "zzaaaa-abcdefgh") is not None
    assert scan_value("name", "zzabcdefgh-aaaa") is None


@pytest.mark.parametrize(
    ("target", "regex", "allowed"),
    [
        (AllowlistTarget.SECRET, r"^zz", True),
        (AllowlistTarget.SECRET, r"name", False),
        (AllowlistTarget.MATCH, r"^zz", True),
        (AllowlistTarget.LINE, r"^name =", True),
    ],
)
def test_allowlist_regex_targets(rules, target, regex, allowed):
    rules(
        Rule(
            rule_id="demo",
            pattern=r"zz\d{4}",
            keywords=("zz",),
            allowlists=(Allowlist(target=target, regexes=(regex,)),),
        )
    )

    assert (scan_value("name", "zz1234") is None) is allowed


def test_allowlist_conditions(rules):
    either = Allowlist(regexes=(r"^nomatch$",), stopwords=("12",))
    both = Allowlist(
        condition=AllowlistCondition.AND, regexes=(r"^nomatch$",), stopwords=("12",)
    )

    rules(
        Rule(rule_id="demo", pattern=r"zz\d{4}", keywords=("zz",)),
        global_allowlists=(either,),
    )
    assert scan_value("name", "zz1234") is None

    rules(
        Rule(rule_id="demo", pattern=r"zz\d{4}", keywords=("zz",)),
        global_allowlists=(both,),
    )
    assert scan_value("name", "zz1234") is not None


def test_specific_rule_is_reported_over_generic(rules):
    rules(
        Rule(rule_id="aaa-generic", pattern=r"zz\d{4}", keywords=("zz",)),
        Rule(rule_id="zzz-specific", pattern=r"zz\d{4}", keywords=("zz",)),
    )

    assert scan_value("name", "zz1234") == SecretFinding("name", "zzz-specific")


def test_rule_set_round_trips_through_its_stored_form():
    rule_set = RuleSet(
        rules=(
            Rule(rule_id="plain", pattern="a+", keywords=("a",)),
            Rule(
                rule_id="full",
                pattern=r"b(\w+)",
                keywords=("b", "bee"),
                entropy=2.5,
                secret_group=1,
                allowlists=(
                    Allowlist(
                        condition=AllowlistCondition.AND,
                        target=AllowlistTarget.LINE,
                        regexes=("x",),
                        stopwords=("y",),
                    ),
                ),
            ),
        ),
        global_allowlists=(Allowlist(regexes=("^z$",)),),
    )

    assert decode_rules(encode_rules(rule_set)) == rule_set
    assert encode_rules(rule_set) == encode_rules(rule_set)


def test_committed_rule_set_decodes():
    assert len(load_rules().rules) > 150


# --- Wiring ------------------------------------------------------------------


def _template(tmp_path, variable: str):
    target = tmp_path / "template.toml"
    target.write_text(f'[env]\npython_version = "3.12"\n# <% {variable} %>\n')
    return target


def _draft(tmp_path, variable: str, value: str, **changes) -> InitDraft:
    source = TemplateSource.load(str(_template(tmp_path, variable)))
    return InitDraft(
        template=DraftTemplate(source), variables=((variable, value),), **changes
    )


def test_resolve_init_rejects_entered_secret_values_before_rendering(mocker, tmp_path):
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "global.toml")
    render = mocker.patch("protostar.config.render_template")

    with pytest.raises(SecretDetectedError, match="org_name"):
        resolve_init(_draft(tmp_path, "org_name", TOKENS["github-pat"]), UserConfig())

    render.assert_not_called()


def test_resolve_init_keeps_an_allowed_value(mocker, tmp_path):
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "global.toml")
    token = TOKENS["github-pat"]
    draft = _draft(tmp_path, "org_name", token, allowed_secrets=frozenset({"org_name"}))

    _, request = resolve_init(draft, UserConfig())

    assert request.recipe is not None
    assert dict(request.recipe.variables) == {"org_name": token}


def test_resolve_init_scans_only_values_that_differ_from_the_recipe(mocker, tmp_path):
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "global.toml")
    token = TOKENS["github-pat"]
    draft = _draft(tmp_path, "org_name", token, allowed_secrets=frozenset({"org_name"}))
    _, request = resolve_init(draft, UserConfig())

    # Re-applying the recorded value needs no new confirmation.
    rerun = _draft(tmp_path, "org_name", token, existing_recipe=request.recipe)
    resolve_init(rerun, UserConfig())

    changed = _draft(
        tmp_path, "org_name", TOKENS["npm-access-token"], existing_recipe=request.recipe
    )
    with pytest.raises(SecretDetectedError, match="org_name"):
        resolve_init(changed, UserConfig())


def test_credential_variable_names_load_and_render(mocker, tmp_path):
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "global.toml")

    source = TemplateSource.load(str(_template(tmp_path, "api_token")))

    assert source.variables == frozenset({"api_token"})
    source.render({"api_token": "anything"})


def test_init_warns_about_credential_variable_names(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    template = _template(tmp_path, "api_token")
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "protostar",
            "init",
            "--from",
            str(template),
            "--var",
            "api_token=placeholder",
            "--dry-run",
            "--json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "planned"
    assert "named like credentials: api_token" in captured.err


def test_allow_secret_flag_keeps_a_flagged_value(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    template = _template(tmp_path, "org_name")
    token = TOKENS["github-pat"]
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "protostar",
            "init",
            "--from",
            str(template),
            "--var",
            f"org_name={token}",
            "--allow-secret",
            "org_name",
            "--dry-run",
            "--json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "planned"


@pytest.mark.parametrize(
    "arguments",
    [["--allow-secret", "nope"], ["--template", "cli", "--allow-secret", "org_name"]],
)
def test_allow_secret_rejects_names_the_template_lacks(
    monkeypatch, tmp_path, arguments
):
    monkeypatch.chdir(tmp_path)
    source = (
        []
        if "--template" in arguments
        else ["--from", str(_template(tmp_path, "org_name"))]
    )
    args = build_parser().parse_args(["init", *source, *arguments, "--dry-run"])

    with pytest.raises(InvalidUsageError, match="no variable named"):
        handle_init(args)


def test_json_error_envelope_lists_findings_without_values(
    capsys, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    template = _template(tmp_path, "org_name")
    token = TOKENS["github-pat"]
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "protostar",
            "init",
            "--from",
            str(template),
            "--var",
            f"org_name={token}",
            "--json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    # Security violations share one exit code.
    assert exc.value.code == ExitCode.NOPERM
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["error"]["type"] == "SecretDetectedError"
    assert payload["error"]["findings"] == [
        {"variable": "org_name", "rule": "github-pat"}
    ]
    assert token not in captured.out
    assert token not in captured.err


def test_human_error_names_variable_without_value(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    template = _template(tmp_path, "org_name")
    token = TOKENS["npm-access-token"]
    monkeypatch.setattr(
        "sys.argv",
        ["protostar", "init", "--from", str(template), "--var", f"org_name={token}"],
    )

    with pytest.raises(SystemExit):
        main()

    captured = capsys.readouterr()
    assert "org_name" in captured.out
    assert "npm-access-token" in captured.out
    assert token not in captured.out
    assert token not in captured.err


def test_cli_startup_does_not_load_the_rule_set(tmp_path):
    """The generated rules load only when a value is scanned."""
    probe = (
        "import sys, protostar.cli.main; "
        "print('protostar._secret_rules' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )

    assert result.stdout.strip() == "False"
