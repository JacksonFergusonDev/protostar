"""Contract that every built-in template must satisfy.

Built-in templates share one identity: modules ship a sensible baseline for casual
projects, and templates state only the delta that defines their shape. Every
built-in passes `protostar check-template --strict`, the rules any template author
is held to; the tests here add the policy that only built-ins follow. They are
parametrized over discovery so a newly added built-in is held to the contract
automatically.
"""

import importlib.resources
import tomllib
from typing import Any

import pytest

from protostar.config import UserConfig
from protostar.template_check import check_template
from protostar.templates import TemplateType, discover_templates

BUILTIN_ALIASES = sorted(
    t.alias
    for t in discover_templates(config=UserConfig())
    if t.type == TemplateType.BUILT_IN
)

# Every built-in states each of these explicitly, as true or false, so a reader can
# always see the choice and never has to infer it from an omission.
QUALITY_FLAGS = ("ruff", "mypy", "pytest", "prek", "ci", "rumdl", "direnv", "just")

# Built-ins are trusted implicitly, so what they may execute is deliberately tiny.
ALLOWED_POST_INSTALL_TASKS = {("uv", "run", "nbdime", "config-git", "--enable")}


def _path(alias: str) -> str:
    return str(
        importlib.resources.files("protostar.templates").joinpath(f"{alias}.toml")
    )


def _load(alias: str) -> dict[str, Any]:
    with open(_path(alias), "rb") as file:
        return tomllib.load(file)


def test_builtin_templates_are_discovered() -> None:
    """Guards against the parametrized contract silently covering nothing."""
    assert {"api", "astro", "cli", "lib", "ml"} <= set(BUILTIN_ALIASES)


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_declares_every_quality_flag_explicitly(alias: str) -> None:
    data = _load(alias)
    not_explicit = [
        flag for flag in QUALITY_FLAGS if not isinstance(data.get(flag), bool)
    ]
    assert not not_explicit, (
        f"{alias}.toml must declare {not_explicit} explicitly as true or false."
    )


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_dependencies_carry_no_version_pins(alias: str) -> None:
    """Templates pass requirements to uv so environments resolve at scaffold time."""
    data = _load(alias)
    declared = [
        *data.get("dependencies", []),
        *data.get("dev", {}).get("dev_dependencies", []),
        *(
            package
            for block in data.get("optional", [])
            for group in ("dependencies", "dev_dependencies", "docs_dependencies")
            for package in block.get(group, [])
        ),
        *data.get("docs_dependencies", []),
    ]
    pinned = [dep for dep in declared if any(ch in dep for ch in "<>=!~@;")]
    assert not pinned, f"{alias}.toml pins or constrains versions: {pinned}"


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_docs_group_is_left_to_the_docs_tooling(alias: str) -> None:
    """Only the Zensical module puts packages in the docs group.

    `uv sync` installs the dev group by default but not docs, so anything else
    placed there (notebook tooling, for example) is removed by the first `just sync`.
    """
    assert not _load(alias).get("docs_dependencies"), (
        f"{alias}.toml declares docs_dependencies; use [dev].dev_dependencies."
    )


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_tasks_stay_within_the_trusted_allowlist(alias: str) -> None:
    data = _load(alias)
    assert not data.get("system_tasks"), (
        f"{alias}.toml declares system_tasks; built-ins are trusted implicitly."
    )
    unlisted = [
        task
        for task in data.get("post_install_tasks", [])
        if tuple(task) not in ALLOWED_POST_INSTALL_TASKS
    ]
    assert not unlisted, (
        f"{alias}.toml runs post-install tasks outside the allowlist: {unlisted}"
    )


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_passes_the_template_check_strictly(alias: str) -> None:
    """Built-ins meet every rule template authors are held to, warnings included."""
    check = check_template(_path(alias))
    assert check.passed(strict=True), f"{alias}.toml:\n" + "\n".join(
        f"{f.rule} {f.key}: {f.message}" for f in check.findings
    )
