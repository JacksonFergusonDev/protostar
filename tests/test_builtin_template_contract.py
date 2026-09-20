"""Contract that every built-in template must satisfy.

Built-in templates share one identity: modules ship a sensible baseline for casual
projects, and templates state only the delta that defines their shape. These tests
enforce that identity statically, and are parametrized over discovery so a newly
added built-in is held to the contract automatically.
"""

import importlib.resources
import re
import tomllib
from collections.abc import Iterator
from typing import Any

import pytest

from protostar.config import UserConfig
from protostar.manifest import EnvironmentManifest
from protostar.modules import TOOLING_MODULES
from protostar.templates import TemplateType, discover_templates

BUILTIN_ALIASES = sorted(
    t.alias
    for t in discover_templates(config=UserConfig())
    if t.type == TemplateType.BUILT_IN
)

# Every built-in states each of these explicitly, as true or false, so a reader can
# always see the choice and never has to infer it from an omission.
QUALITY_FLAGS = ("ruff", "mypy", "pytest", "prek", "ci", "rumdl", "direnv", "just")

# Root-level booleans that are valid but are not tooling modules.
NON_MODULE_FLAGS = {"docker"}

# Tools whose config has no additive key, so a template must redefine the whole list.
# Redefining is only allowed when it keeps every baseline entry (a strict superset).
ATOMIC_LISTS_WITHOUT_ADDITIVE_KEY = {("tool", "ruff", "lint", "ignore")}

# Built-ins are trusted implicitly, so what they may execute is deliberately tiny.
ALLOWED_POST_INSTALL_TASKS = {("uv", "run", "nbdime", "config-git", "--enable")}

# Package-name prefixes that only make sense while a tool is enabled.
TOOL_PACKAGE_OWNERS = {
    "pytest": "pytest",
    "coverage": "pytest",
    "ruff": "ruff",
    "mypy": "mypy",
}

# `tool.<table>` names that belong to a tool but are not in that module's baseline.
EXTRA_TOOL_TABLES = {"coverage": "pytest"}

_MISSING = object()

# Payloads may use `<% VAR %>` as a bare key or value, which is only valid TOML after
# interpolation, so a neutral stand-in is substituted before parsing.
_PLACEHOLDER = re.compile(r"<%\s*[A-Z_]+\s*%>")


def _load(alias: str) -> dict[str, Any]:
    text = (
        importlib.resources.files("protostar.templates")
        .joinpath(f"{alias}.toml")
        .read_text(encoding="utf-8")
    )
    return tomllib.loads(text)


def _payloads(alias: str) -> dict[str, tuple[str, str | None]]:
    """Returns each [dev.pyproject] entry as (content, requires)."""
    entries = _load(alias).get("dev", {}).get("pyproject", {})
    return {
        identity: (
            (entry, None)
            if isinstance(entry, str)
            else (entry["content"], entry.get("requires"))
        )
        for identity, entry in entries.items()
    }


def _module_baselines() -> dict[str, dict[str, Any]]:
    """Returns each tooling module's pyproject.toml contribution, keyed by module."""
    baselines: dict[str, dict[str, Any]] = {}
    for module in TOOLING_MODULES:
        manifest = EnvironmentManifest()
        module.build(manifest)
        contributions = manifest.filesystem.structured.get("pyproject.toml", [])
        if contributions:
            baselines[module.config_key] = tomllib.loads(
                _PLACEHOLDER.sub(
                    "placeholder", "\n".join(c.content for c in contributions)
                )
            )
    return baselines


def _leaves(
    node: Any, path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    """Yields (path, value) for every non-table value; lists are atomic leaves."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaves(value, (*path, key))
    else:
        yield path, node


def _lookup(node: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return _MISSING
        node = node[key]
    return node


def find_baseline_violations(
    payload: str, baselines: dict[str, dict[str, Any]], requires: str | None = None
) -> list[str]:
    """Lists ways a template's TOML payload restates a module baseline.

    Overriding a baseline scalar with a different value is a legitimate delta. What is
    flagged is repeating a baseline value verbatim, and redefining a baseline list
    where an additive key (e.g. `extend-select`) exists. A payload bound to a tool is
    compared only with that tool's baseline; an unbound one with every baseline.
    """
    if requires is not None:
        baselines = {requires: baselines.get(requires, {})}
    violations: list[str] = []
    parsed = tomllib.loads(_PLACEHOLDER.sub("placeholder", payload))
    for path, value in _leaves(parsed):
        dotted = ".".join(path)
        for tool, baseline in baselines.items():
            base_value = _lookup(baseline, path)
            if base_value is _MISSING:
                continue
            if value == base_value:
                violations.append(f"{dotted}: repeats the {tool} baseline verbatim")
            elif isinstance(value, list) and isinstance(base_value, list):
                if path not in ATOMIC_LISTS_WITHOUT_ADDITIVE_KEY:
                    violations.append(
                        f"{dotted}: redefines the {tool} baseline list; "
                        "use an additive key such as extend-select"
                    )
                elif not all(item in value for item in base_value):
                    violations.append(
                        f"{dotted}: drops entries from the {tool} baseline list"
                    )
    return violations


@pytest.fixture(scope="module")
def baselines() -> dict[str, dict[str, Any]]:
    return _module_baselines()


def test_builtin_templates_are_discovered() -> None:
    """Guards against the parametrized contract silently covering nothing."""
    assert {"api", "astro", "cli", "dsp", "embedded", "lib", "ml"} <= set(
        BUILTIN_ALIASES
    )


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
def test_root_flags_name_real_tools(alias: str) -> None:
    """A misspelled flag is otherwise a silent no-op."""
    valid = {m.config_key for m in TOOLING_MODULES} | NON_MODULE_FLAGS
    unknown = [
        key
        for key, value in _load(alias).items()
        if isinstance(value, bool) and key not in valid
    ]
    assert not unknown, f"{alias}.toml declares unknown tooling flags: {unknown}"


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_declares_name_and_description(alias: str) -> None:
    data = _load(alias)
    assert data.get("name"), f"{alias}.toml is missing a display name."
    assert data.get("description"), f"{alias}.toml is missing a description."


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_dependencies_carry_no_version_pins(alias: str) -> None:
    """Templates pass requirements to uv so environments resolve at scaffold time."""
    data = _load(alias)
    declared = [
        *data.get("dependencies", []),
        *data.get("dev", {}).get("dev_dependencies", []),
        *(
            package
            for packages in data.get("dev", {}).get("tool_dependencies", {}).values()
            for package in packages
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
def test_pyproject_payloads_state_only_the_delta(
    alias: str, baselines: dict[str, dict[str, Any]]
) -> None:
    violations = [
        f"[dev.pyproject].{identity} -> {violation}"
        for identity, (content, requires) in _payloads(alias).items()
        for violation in find_baseline_violations(content, baselines, requires)
    ]
    assert not violations, f"{alias}.toml restates module baselines:\n" + "\n".join(
        violations
    )


def find_unbound_tool_config(
    payloads: dict[str, tuple[str, str | None]], owners: dict[str, str]
) -> list[str]:
    """Lists payloads that configure a tool without declaring `requires` for it."""
    problems: list[str] = []
    for identity, (content, requires) in payloads.items():
        parsed = tomllib.loads(_PLACEHOLDER.sub("placeholder", content))
        for table in parsed.get("tool", {}):
            owner = owners.get(table)
            if owner and requires != owner:
                problems.append(
                    f"[dev.pyproject].{identity} configures tool.{table} but "
                    f'declares requires = {requires!r}; expected "{owner}"'
                )
    return problems


@pytest.fixture(scope="module")
def tool_table_owners(baselines: dict[str, dict[str, Any]]) -> dict[str, str]:
    owners = {
        table: tool
        for tool, baseline in baselines.items()
        for table in baseline.get("tool", {})
    }
    return owners | EXTRA_TOOL_TABLES


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_tool_configuration_declares_the_tool_it_needs(
    alias: str, tool_table_owners: dict[str, str]
) -> None:
    """`--no-<tool>` must not leave that tool's configuration behind."""
    problems = find_unbound_tool_config(_payloads(alias), tool_table_owners)
    assert not problems, f"{alias}.toml:\n" + "\n".join(problems)


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
        assert len(violations) == 1
        assert "repeats the mypy baseline" in violations[0]

    def test_flags_a_redefined_baseline_list(self) -> None:
        violations = find_baseline_violations(
            '[tool.ruff.lint]\nselect = ["A", "B", "D"]\n', SYNTHETIC_BASELINES
        )
        assert len(violations) == 1
        assert "extend-select" in violations[0]

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


SYNTHETIC_OWNERS = {"mypy": "mypy", "ruff": "ruff", "coverage": "pytest"}


class TestUnboundToolConfigDetector:
    """Proves the requires ratchet bites, so it cannot pass vacuously."""

    def test_flags_tool_config_with_no_requires(self) -> None:
        problems = find_unbound_tool_config(
            {"typing": ("[tool.mypy]\nstrict = true\n", None)}, SYNTHETIC_OWNERS
        )
        assert len(problems) == 1
        assert 'expected "mypy"' in problems[0]

    def test_flags_tool_config_bound_to_the_wrong_tool(self) -> None:
        problems = find_unbound_tool_config(
            {"cov": ("[tool.coverage.run]\nbranch = true\n", "ruff")}, SYNTHETIC_OWNERS
        )
        assert len(problems) == 1
        assert 'expected "pytest"' in problems[0]

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


def find_unbound_tool_packages(dev_dependencies: list[str]) -> list[str]:
    """Lists always-installed dev packages that belong to a tool's toolchain."""
    problems: list[str] = []
    for dependency in dev_dependencies:
        name = re.split(r"[\[<>=!~; ]", dependency, maxsplit=1)[0].lower()
        for prefix, owner in TOOL_PACKAGE_OWNERS.items():
            if name == prefix or name.startswith(f"{prefix}-"):
                problems.append(
                    f"'{dependency}' is installed unconditionally but belongs to "
                    f"{owner}; declare it under [dev.tool_dependencies] {owner} = [...]"
                )
    return problems


@pytest.mark.parametrize("alias", BUILTIN_ALIASES)
def test_tool_packages_are_installed_only_with_their_tool(alias: str) -> None:
    """`--no-<tool>` must not install that tool's plugins."""
    problems = find_unbound_tool_packages(
        _load(alias).get("dev", {}).get("dev_dependencies", [])
    )
    assert not problems, f"{alias}.toml:\n" + "\n".join(problems)


class TestUnboundToolPackageDetector:
    """Proves the tool-package ratchet bites, so it cannot pass vacuously."""

    def test_flags_a_pytest_plugin_installed_unconditionally(self) -> None:
        problems = find_unbound_tool_packages(["pytest-cov", "rich"])
        assert len(problems) == 1
        assert "pytest-cov" in problems[0]

    def test_flags_the_tool_itself_and_extras(self) -> None:
        assert len(find_unbound_tool_packages(["mypy>=1", "ruff[dev]"])) == 2

    def test_ignores_packages_that_only_share_a_prefix(self) -> None:
        assert find_unbound_tool_packages(["pytestish", "rufflib", "mypyish"]) == []
