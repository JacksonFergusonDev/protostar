"""Checks a template author runs before publishing a template."""

import subprocess
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from protostar.errors import NetworkFetchError, TemplateResolutionError
from protostar.template_check import (
    CheckRule,
    Severity,
    check_template,
    find_baseline_violations,
    find_unbound_tool_config,
    find_unbound_tool_packages,
)

GOOD = 'name = "Service"\ndescription = "A service"\n'


def write_template(root: Path, body: str, files: dict[str, bytes] | None = None) -> str:
    """Writes a template directory and returns it as a check target."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "protostar.toml").write_text(GOOD + body, encoding="utf-8")
    for path, content in (files or {}).items():
        target = root / "template" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return str(root)


def rules(target: str) -> list[tuple[CheckRule, str | None]]:
    return [(f.rule, f.key) for f in check_template(target).findings]


@pytest.fixture(autouse=True)
def no_subprocesses(mocker):
    """A check never runs anything, git included."""
    return mocker.patch.object(
        subprocess, "run", side_effect=AssertionError("check ran a subprocess")
    )


def test_a_clean_template_passes(tmp_path):
    target = write_template(
        tmp_path / "t",
        'ruff = true\n\n[variables.REGION]\ndescription = "Deployment region"\n\n'
        '[files]\n"src/<% PACKAGE_NAME %>/region.py" = "REGION = \\"<% REGION %>\\"\\n"\n',
    )
    check = check_template(target)
    assert check.findings == ()
    assert check.passed(strict=True)


def test_a_template_that_fails_to_render_is_an_error(tmp_path):
    target = write_template(tmp_path / "t", 'dependencies = "fastapi"\n')
    check = check_template(target)
    assert [f.rule for f in check.errors] == [CheckRule.INVALID_TEMPLATE]
    assert "dependencies" in check.errors[0].message
    assert check.errors[0].hint
    assert not check.passed()


def test_a_template_that_planning_rejects_is_an_error(tmp_path):
    """Appending to a YAML file Protostar merges is only caught by planning."""
    target = write_template(
        tmp_path / "t", '[appends.".pre-commit-config.yaml".extra]\ncontent = "x"\n'
    )
    check = check_template(target)
    assert [f.rule for f in check.errors] == [CheckRule.INVALID_TEMPLATE]
    assert "Append regions are unsupported" in check.errors[0].message


def test_an_unknown_tooling_flag_is_named(tmp_path):
    check = check_template(write_template(tmp_path / "t", "rufff = true\n"))
    assert check.errors[0].message == "The template sets unknown tooling flags: rufff."


def test_planning_ignores_the_checkout_it_runs_in(tmp_path, monkeypatch):
    """A template repository managed by Protostar is not the project being checked."""
    checkout = tmp_path / "checkout"
    target = write_template(checkout, "ruff = true\n")
    # Planning here would read this state and reject the template.
    (checkout / "protostar.lock").write_text("not state\n", encoding="utf-8")
    monkeypatch.chdir(checkout)
    before = sorted(p.name for p in checkout.iterdir())

    assert check_template(target).findings == ()
    assert sorted(p.name for p in checkout.iterdir()) == before
    assert Path.cwd() == checkout


def test_a_binary_template_file_is_a_finding(tmp_path):
    target = write_template(
        tmp_path / "t", "", files={"assets/logo.png": b"\x89PNG\r\n\x1a\n\xff\xfe"}
    )
    (finding,) = check_template(target).findings
    assert finding.rule is CheckRule.INVALID_TEMPLATE
    assert finding.file == "template/assets/logo.png"


def test_a_non_utf8_template_file_is_a_finding(tmp_path):
    root = tmp_path / "t"
    root.mkdir()
    (root / "backend.toml").write_bytes(b'name = "\xff"\n')
    (finding,) = check_template(str(root / "backend.toml")).findings
    assert finding.rule is CheckRule.INVALID_TEMPLATE
    assert finding.file == "backend.toml"
    assert finding.message == "backend.toml is not UTF-8 text."


def test_a_missing_template_is_not_a_finding(tmp_path):
    """Not finding the template raises, so it can't pass for a broken template."""
    with pytest.raises(TemplateResolutionError, match="not found"):
        check_template(str(tmp_path / "absent"))


def test_a_failed_download_is_not_a_finding(mocker):
    error = HTTPError("https://example.com/t.toml", 404, "Not Found", Message(), None)
    mocker.patch("protostar.network._get_opener").return_value.open.side_effect = error
    with pytest.raises(NetworkFetchError) as caught:
        check_template("https://example.com/t.toml")
    assert caught.value.hint is not None
    assert "HTTP 404" in caught.value.hint


def test_ignored_root_keys_are_warnings(tmp_path):
    target = write_template(
        tmp_path / "t", 'dependancies = ["x"]\nmypy = "yes"\ndocker = true\n'
    )
    findings = {f.key: f for f in check_template(target).findings}
    assert set(findings) == {"dependancies", "mypy"}
    assert all(f.rule is CheckRule.UNKNOWN_KEY for f in findings.values())
    assert "not true or false" in findings["mypy"].message


def test_missing_name_and_description_are_warnings(tmp_path):
    root = tmp_path / "t"
    root.mkdir()
    (root / "protostar.toml").write_text("ruff = true\n", encoding="utf-8")
    assert rules(str(root)) == [
        (CheckRule.MISSING_METADATA, "name"),
        (CheckRule.MISSING_METADATA, "description"),
    ]


def test_variables_need_a_description_and_a_non_credential_name(tmp_path):
    target = write_template(
        tmp_path / "t",
        '[variables.REGION]\ndescription = "Region"\n\n[files]\n'
        '"a.txt" = "<% REGION %> <% OWNER %> <% API_TOKEN %>"\n',
    )
    assert rules(target) == [
        (CheckRule.UNDESCRIBED_VARIABLE, "variables.API_TOKEN"),
        (CheckRule.UNDESCRIBED_VARIABLE, "variables.OWNER"),
        (CheckRule.CREDENTIAL_VARIABLE, "variables.API_TOKEN"),
    ]


def test_payload_and_package_rules_are_warnings(tmp_path):
    target = write_template(
        tmp_path / "t",
        '[dev]\ndev_dependencies = ["pytest-cov"]\n\n[dev.pyproject]\n'
        "lint = '''\n[tool.ruff.lint]\nselect = [\"E\"]\n'''\n",
    )
    check = check_template(target)
    assert check.errors == ()
    assert check.passed()
    assert not check.passed(strict=True)
    assert [(f.rule, f.key) for f in check.warnings] == [
        (CheckRule.RESTATED_BASELINE, "dev.pyproject.lint"),
        (CheckRule.UNBOUND_TOOL_CONFIG, "dev.pyproject.lint"),
        (CheckRule.UNBOUND_TOOL_PACKAGE, "dev.dev_dependencies"),
    ]
    assert "--no-pytest" in (check.warnings[2].hint or "")


def test_the_json_form_is_stable(tmp_path):
    root = tmp_path / "t"
    root.mkdir()
    (root / "protostar.toml").write_text('description = "d"\n', encoding="utf-8")
    assert check_template(str(root)).to_dict() == {
        "source": str(root),
        "errors": 0,
        "warnings": 1,
        "findings": [
            {
                "rule": "missing-metadata",
                "severity": "warning",
                "message": "The template declares no name.",
                "file": "protostar.toml",
                "key": "name",
                "hint": 'Set name = "..." at the top of the template; '
                "protostar init --list-templates and the wizard show it.",
            }
        ],
    }


def test_only_invalid_template_is_an_error() -> None:
    assert [r for r in CheckRule if r.severity is Severity.ERROR] == [
        CheckRule.INVALID_TEMPLATE
    ]


SYNTHETIC_BASELINES: dict[str, dict[str, Any]] = {
    "ruff": {"tool": {"ruff": {"lint": {"select": ["A", "B"], "ignore": ["E501"]}}}},
    "mypy": {"tool": {"mypy": {"pretty": True, "python_version": "3.13"}}},
}


class TestBaselineViolationDetector:
    """Proves the delta check bites, so it cannot pass vacuously."""

    def test_flags_a_verbatim_scalar_repeat(self) -> None:
        violations = find_baseline_violations(
            "[tool.mypy]\npretty = true\n", SYNTHETIC_BASELINES
        )
        assert violations == ["tool.mypy.pretty repeats the mypy baseline verbatim."]

    def test_flags_a_redefined_baseline_list(self) -> None:
        violations = find_baseline_violations(
            '[tool.ruff.lint]\nselect = ["A", "B", "D"]\n', SYNTHETIC_BASELINES
        )
        assert len(violations) == 1
        assert "instead of adding to it" in violations[0]

    def test_allows_an_additive_key(self) -> None:
        assert not find_baseline_violations(
            '[tool.ruff.lint]\nextend-select = ["D"]\n', SYNTHETIC_BASELINES
        )

    def test_allows_a_different_scalar_override(self) -> None:
        assert not find_baseline_violations(
            '[tool.mypy]\npython_version = "3.12"\n', SYNTHETIC_BASELINES
        )

    def test_allows_a_superset_of_an_atomic_list(self) -> None:
        assert not find_baseline_violations(
            '[tool.ruff.lint]\nignore = ["D100", "E501"]\n', SYNTHETIC_BASELINES
        )

    def test_flags_an_atomic_list_that_drops_baseline_entries(self) -> None:
        violations = find_baseline_violations(
            '[tool.ruff.lint]\nignore = ["D100"]\n', SYNTHETIC_BASELINES
        )
        assert len(violations) == 1
        assert "drops entries" in violations[0]

    def test_a_tool_bound_payload_is_compared_only_with_its_own_baseline(self) -> None:
        # `pretty = true` repeats the mypy baseline, but a ruff-bound payload is
        # only measured against ruff, so it is not flagged.
        payload = "[tool.mypy]\npretty = true\n"
        assert find_baseline_violations(payload, SYNTHETIC_BASELINES, "ruff") == []
        assert len(find_baseline_violations(payload, SYNTHETIC_BASELINES, "mypy")) == 1

    def test_a_placeholder_key_parses(self) -> None:
        payload = '[tool.hatch.build.targets.wheel]\n<% PACKAGE_NAME %> = "x"\n'
        assert find_baseline_violations(payload, SYNTHETIC_BASELINES) == []


SYNTHETIC_OWNERS = {"mypy": "mypy", "ruff": "ruff", "coverage": "pytest"}


class TestUnboundToolConfigDetector:
    """Proves the requires ratchet bites, so it cannot pass vacuously."""

    def test_flags_tool_config_with_no_requires(self) -> None:
        ((identity, message),) = find_unbound_tool_config(
            {"typing": ("[tool.mypy]\nstrict = true\n", None)}, SYNTHETIC_OWNERS
        )
        assert identity == "typing"
        assert 'expected "mypy"' in message

    def test_flags_tool_config_bound_to_the_wrong_tool(self) -> None:
        ((_, message),) = find_unbound_tool_config(
            {"cov": ("[tool.coverage.run]\nbranch = true\n", "ruff")}, SYNTHETIC_OWNERS
        )
        assert 'expected "pytest"' in message

    def test_accepts_correctly_bound_config(self) -> None:
        assert not find_unbound_tool_config(
            {"typing": ("[tool.mypy]\nstrict = true\n", "mypy")}, SYNTHETIC_OWNERS
        )

    def test_ignores_config_no_module_owns(self) -> None:
        assert not find_unbound_tool_config(
            {
                "build": (
                    '[tool.hatch.build.targets.wheel]\npackages = ["src/x"]\n',
                    None,
                )
            },
            SYNTHETIC_OWNERS,
        )


class TestUnboundToolPackageDetector:
    """Proves the tool-package ratchet bites, so it cannot pass vacuously."""

    def test_flags_a_pytest_plugin_installed_unconditionally(self) -> None:
        ((owner, message),) = find_unbound_tool_packages(["pytest-cov", "rich"])
        assert owner == "pytest"
        assert "pytest-cov" in message

    def test_flags_the_tool_itself_and_extras(self) -> None:
        assert len(find_unbound_tool_packages(["mypy>=1", "ruff[dev]"])) == 2

    def test_ignores_packages_that_only_share_a_prefix(self) -> None:
        assert find_unbound_tool_packages(["pytestish", "rufflib", "mypyish"]) == []
