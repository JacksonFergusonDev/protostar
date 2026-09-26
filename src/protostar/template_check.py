"""Read-only checks a template author runs before publishing a template.

``check_template`` answers two questions about one template. Would
``protostar init`` accept it? Those answers are errors. Does it follow the
authoring practices Protostar's own built-ins follow? Those are warnings.

Retrieving the template is not part of the check: a template that cannot be
fetched or found raises the usual domain error, so a caller can always tell a
broken template from one that never arrived. The one exception is a file
inside the template that is not UTF-8 text, which is the template's own defect
and so is reported as a finding.
"""

from __future__ import annotations

import contextlib
import re
import tempfile
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import PurePath, PurePosixPath
from typing import Any

from .config import TEMPLATE_STRUCTURAL_KEYS, TemplateBlueprint, TemplateSource
from .errors import ProtostarError, TemplateEncodingError, TemplateResolutionError
from .interpolation import VARIABLE_PATTERN
from .options import Condition
from .toml_lines import TomlLineIndex

__all__ = [
    "CheckRule",
    "Finding",
    "Severity",
    "TemplateCheck",
    "check_template",
    "find_baseline_violations",
    "find_unbound_tool_config",
    "find_unbound_tool_packages",
    "module_baselines",
]


class Severity(StrEnum):
    """How much a finding matters to the template's users."""

    ERROR = "error"
    WARNING = "warning"


class CheckRule(StrEnum):
    """Stable identifiers for everything ``check_template`` can report."""

    INVALID_TEMPLATE = "invalid-template"
    UNKNOWN_KEY = "unknown-key"
    MISSING_METADATA = "missing-metadata"
    UNDESCRIBED_VARIABLE = "undescribed-variable"
    CREDENTIAL_VARIABLE = "credential-variable"
    RESTATED_BASELINE = "restated-baseline"
    UNBOUND_TOOL_CONFIG = "unbound-tool-config"
    UNBOUND_TOOL_PACKAGE = "unbound-tool-package"
    INCONSISTENT_MIGRATION = "inconsistent-migration"

    @property
    def severity(self) -> Severity:
        """Errors are what ``init`` refuses; everything else is a warning."""
        if self is CheckRule.INVALID_TEMPLATE:
            return Severity.ERROR
        return Severity.WARNING


@dataclass(frozen=True)
class Finding:
    """One problem in a template.

    Attributes:
        rule: What was found.
        message: A one-line description of this occurrence.
        file: The template file it is in, as a POSIX path within the template.
        key: The dotted TOML key it concerns, when there is one.
        hint: How to fix it.
        line: The 1-based line in ``file`` it points at, when it has one.
    """

    rule: CheckRule
    message: str
    file: str
    key: str | None = None
    hint: str | None = None
    line: int | None = None

    @property
    def severity(self) -> Severity:
        """The rule's severity."""
        return self.rule.severity

    def to_dict(self) -> dict[str, Any]:
        """Serializes the finding to a JSON-safe dictionary."""
        return {
            "rule": self.rule.value,
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "key": self.key,
            "hint": self.hint,
        }


@dataclass(frozen=True)
class TemplateCheck:
    """Everything one check found, errors first.

    Attributes:
        source: The template as the caller named it.
        findings: Every finding, errors before warnings.
    """

    source: str
    findings: tuple[Finding, ...]

    @property
    def errors(self) -> tuple[Finding, ...]:
        """Findings that stop ``protostar init`` from using the template."""
        return tuple(f for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        """Findings that break an authoring practice."""
        return tuple(f for f in self.findings if f.severity is Severity.WARNING)

    def passed(self, *, strict: bool = False) -> bool:
        """Whether the template passes; ``strict`` also fails on warnings."""
        return not (self.findings if strict else self.errors)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the check to a JSON-safe dictionary."""
        return {
            "source": self.source,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "findings": [finding.to_dict() for finding in self.findings],
        }


# Value substituted for every custom variable. It renders anywhere a value can
# appear, including a bare TOML key, and matches no credential rule.
_PLACEHOLDER_VALUE = "placeholder"

# Root booleans that are valid but belong to no tooling module.
_NON_MODULE_FLAGS = frozenset({"docker"})

# Tools whose config has no additive key, so a template must redefine the whole
# list. Redefining is only allowed when it keeps every baseline entry.
ATOMIC_LISTS_WITHOUT_ADDITIVE_KEY = frozenset({("tool", "ruff", "lint", "ignore")})

# Package-name prefixes that only make sense while a tool is enabled.
TOOL_PACKAGE_OWNERS: Mapping[str, str] = {
    "pytest": "pytest",
    "coverage": "pytest",
    "ruff": "ruff",
    "mypy": "mypy",
}

# `tool.<table>` names that belong to a tool but are not in that module's baseline.
EXTRA_TOOL_TABLES: Mapping[str, str] = {"coverage": "pytest"}

_MISSING = object()


def check_template(target: str) -> TemplateCheck:
    """Checks one template without writing to the project or running anything.

    The template is rendered with a placeholder for every custom variable and
    planned as a default ``protostar init`` into an empty scratch directory,
    using Protostar's built-in configuration rather than the caller's, so the
    result is the same on every machine.

    Args:
        target: A ``protostar.toml`` path, a template directory, or a URL.

    Returns:
        Every finding, errors first.

    Raises:
        NetworkFetchError: If a remote template cannot be downloaded.
        TemplateResolutionError: If the template cannot be found or unpacked.
        SecurityViolationError: If a template archive is unsafe to unpack.
        ConfigurationError: If the URL carries credentials or a query.
    """
    manifest_file = _manifest_file(target)
    try:
        source = TemplateSource.load(target)
    except TemplateEncodingError as e:
        return TemplateCheck(
            target,
            (Finding(CheckRule.INVALID_TEMPLATE, e.detail, e.path, hint=e.hint),),
        )

    text = source.template_bytes.decode("utf-8")
    # Indexed as parsed: a placeholder may stand where TOML needs a key, and
    # substituting one never changes a line.
    where = _Where(
        manifest_file,
        text,
        TomlLineIndex(VARIABLE_PATTERN.sub(_PLACEHOLDER_VALUE, text)),
    )
    errors: list[Finding] = []
    warnings: list[Finding] = []
    raw = _raw_data(text)
    if raw is not None:
        warnings.extend(_unknown_keys(raw, where))
        warnings.extend(_missing_metadata(raw, where))
    warnings.extend(_variable_findings(source, where))

    variables = dict.fromkeys(source.variables, _PLACEHOLDER_VALUE)
    try:
        blueprint = source.render(variables)
    except ProtostarError as e:
        errors.append(_error_finding(e, manifest_file))
    else:
        try:
            _plan_default_init(source, variables)
        except ProtostarError as e:
            errors.append(_error_finding(e, manifest_file))
        warnings.extend(_payload_findings(blueprint, where))
        warnings.extend(_migration_findings(source, blueprint, where))
    return TemplateCheck(target, (*errors, *warnings))


@dataclass(frozen=True)
class _Where:
    """The template's TOML file, for locating findings in it."""

    file: str
    text: str
    index: TomlLineIndex

    def payload_line(self, identity: str, inner: tuple[str, ...]) -> int | None:
        """Locates a key inside a [dev.pyproject] payload, in either form."""
        payload = ("dev", "pyproject", identity)
        for path in ((*payload, "content"), payload):
            if (line := self.index.line_in_string(path, inner)) is not None:
                return line
        return None


def _manifest_file(target: str) -> str:
    """Names the template's TOML file as its author sees it."""
    name = PurePosixPath(target.replace("\\", "/")).name
    return name if name.endswith(".toml") else "protostar.toml"


def _error_finding(error: ProtostarError, file: str) -> Finding:
    """Reports an error the engine raised as a finding.

    A TOML syntax error names its line; other errors concern the template as
    a whole, or a target no line of it spells out.
    """
    message = error.detail if isinstance(error, TemplateResolutionError) else str(error)
    line = None
    if isinstance(error.__cause__, tomllib.TOMLDecodeError):
        found = re.search(r"\bline (\d+)", str(error.__cause__))
        line = int(found.group(1)) if found else None
    return Finding(
        CheckRule.INVALID_TEMPLATE, message, file, hint=error.hint, line=line
    )


def _plan_default_init(source: TemplateSource, variables: dict[str, str]) -> None:
    """Plans a default ``protostar init`` of the template into an empty directory.

    Planning reads the working directory (for collisions and recorded state),
    so it runs in an empty scratch directory: the template is judged as a
    fresh project would receive it, never against whatever the author's
    checkout contains. Nothing is written there.
    """
    from .config import UserConfig
    from .init_draft import DraftTemplate, InitDraft, resolve_init
    from .orchestrator import Orchestrator

    config = UserConfig()
    draft = InitDraft(
        template=DraftTemplate(source, is_external=True),
        variables=tuple(sorted(variables.items())),
        # Explicit, so resolving metadata never asks git for the author.
        metadata=(),
    )
    with tempfile.TemporaryDirectory() as empty, contextlib.chdir(empty):
        modules, request = resolve_init(draft, config)
        # No execution follows, so the executables it needs are not checked.
        Orchestrator(modules, config, request=request).plan(check_executables=False)


def _raw_data(text: str) -> dict[str, Any] | None:
    """Parses the unrendered template, or None when it is not valid TOML.

    Placeholders are replaced first, since one may stand where TOML needs a
    key. Rendering reports a syntax error itself.
    """
    try:
        return tomllib.loads(VARIABLE_PATTERN.sub(_PLACEHOLDER_VALUE, text))
    except tomllib.TOMLDecodeError:
        return None


def _unknown_keys(raw: dict[str, Any], where: _Where) -> Iterator[Finding]:
    """Reports root keys Protostar silently ignores, such as a misspelled field.

    An unknown boolean is a tooling flag, which planning rejects outright.
    """
    from .recipe import Tool

    flags = {tool.value for tool in Tool} | _NON_MODULE_FLAGS
    for key, value in raw.items():
        if key in TEMPLATE_STRUCTURAL_KEYS or isinstance(value, bool):
            continue
        if key in flags:
            yield Finding(
                CheckRule.UNKNOWN_KEY,
                f"'{key}' is a tooling flag, but its value is not true or "
                "false, so Protostar ignores it.",
                where.file,
                key,
                hint=f"Set {key} = true or {key} = false.",
                line=where.index.line_of((key,)),
            )
        else:
            yield Finding(
                CheckRule.UNKNOWN_KEY,
                f"Protostar ignores the root key '{key}'.",
                where.file,
                key,
                hint="Check its spelling against the template schema "
                "(protostar export-schema).",
                line=where.index.line_of((key,)),
            )


def _missing_metadata(raw: dict[str, Any], where: _Where) -> Iterator[Finding]:
    """Reports a missing display name or description."""
    for key in ("name", "description"):
        if not raw.get(key):
            yield Finding(
                CheckRule.MISSING_METADATA,
                f"The template declares no {key}.",
                where.file,
                key,
                hint=f'Set {key} = "..." at the top of the template; '
                "protostar init --list-templates and the wizard show it.",
            )


def _variable_findings(source: TemplateSource, where: _Where) -> Iterator[Finding]:
    """Reports custom variables with no description or a credential-like name.

    An undescribed variable points at its first use, and a credential-like
    one at its declaration when it has one.
    """
    from .secret_guard import credential_named

    try:
        described: frozenset[str] = frozenset(source.descriptions)
    except ProtostarError:
        # A malformed [variables] table fails rendering, which reports it.
        described = source.variables
    for name in sorted(source.variables - described):
        file, line = _first_use(source, name, where)
        yield Finding(
            CheckRule.UNDESCRIBED_VARIABLE,
            f"The variable {name} has no description.",
            file,
            f"variables.{name}",
            hint=f'Add [variables.{name}] with description = "..." so the '
            "prompt can explain what the value is for.",
            line=line,
        )
    for name in credential_named(source.variables):
        declared = where.index.line_of(("variables", name))
        file, line = (
            (where.file, declared) if declared else _first_use(source, name, where)
        )
        yield Finding(
            CheckRule.CREDENTIAL_VARIABLE,
            f"The variable {name} is named like a credential.",
            file,
            f"variables.{name}",
            hint="Variable values are saved in pyproject.toml and committed. "
            "Have the generated code read secrets from the environment instead, "
            "and rename the variable.",
            line=line,
        )


def _first_use(
    source: TemplateSource, name: str, where: _Where
) -> tuple[str, int | None]:
    """Finds a variable's first placeholder: the TOML file, then template/."""
    placeholder = re.compile(rf"<%\s*{re.escape(name)}\s*%>")
    if found := placeholder.search(where.text):
        return where.file, where.text.count("\n", 0, found.start()) + 1
    for relative, content in sorted(source.files.items()):
        path = f"template/{PurePath(relative).as_posix()}"
        if found := placeholder.search(content):
            return path, content.count("\n", 0, found.start()) + 1
        if placeholder.search(relative):
            return path, None
    return where.file, None


def _migration_findings(
    source: TemplateSource, blueprint: TemplateBlueprint, where: _Where
) -> Iterator[Finding]:
    """Reports migrations that contradict what the template ships.

    A migration describes the step from an older version to this one, so
    what it removes or renames away must be gone, and what it renames to
    must be here.
    """
    shipped = set(blueprint.files)
    start = where.text.find("[[migrations]]")

    def finding(message: str, value: str, hint: str) -> Finding:
        found = where.text.find(f'"{value}"', max(start, 0))
        line = where.text.count("\n", 0, found) + 1 if found >= 0 else None
        return Finding(
            CheckRule.INCONSISTENT_MIGRATION,
            message,
            where.file,
            "migrations",
            hint=hint,
            line=line,
        )

    for migration in blueprint.migrations:
        for path in migration.remove:
            if path in shipped:
                yield finding(
                    f"Migration {migration.version} removes {path}, which the "
                    "template still ships.",
                    path,
                    "Stop shipping the file, or drop it from remove.",
                )
        for rename in migration.rename:
            if rename.source in shipped:
                yield finding(
                    f"Migration {migration.version} renames {rename.source}, "
                    "which the template still ships.",
                    rename.source,
                    "Ship the file only under its new name.",
                )
            if rename.target not in shipped:
                yield finding(
                    f"Migration {migration.version} renames a file to "
                    f"{rename.target}, which the template doesn't ship.",
                    rename.target,
                    "Ship the file under its new name in [files] or template/.",
                )
    for migration in source.migrations:
        for rename in migration.rename_variables:
            if rename.target not in source.variables:
                yield finding(
                    f"Migration {migration.version} renames variable "
                    f"{rename.source} to {rename.target}, which the template "
                    "doesn't use.",
                    rename.target,
                    "Use the variable under its new name, as <% NAME %>.",
                )
            if rename.source in source.variables:
                yield finding(
                    f"Migration {migration.version} renames variable "
                    f"{rename.source}, which the template still uses.",
                    rename.source,
                    "Use the variable only under its new name.",
                )


def _payload_findings(blueprint: TemplateBlueprint, where: _Where) -> Iterator[Finding]:
    """Reports payloads and packages that ignore the tool they belong to."""
    baselines = module_baselines()
    owners = {
        table: tool
        for tool, baseline in baselines.items()
        for table in baseline.get("tool", {})
    } | dict(EXTRA_TOOL_TABLES)
    payloads = {
        identity: (payload.content, payload.requires)
        for identity, payload in blueprint.pyproject_injections.items()
    }
    for identity, (content, requires) in payloads.items():
        for path, message in find_baseline_violations(content, baselines, requires):
            yield Finding(
                CheckRule.RESTATED_BASELINE,
                message,
                where.file,
                f"dev.pyproject.{identity}",
                hint="State only what differs from Protostar's baseline, and use "
                "additive keys such as extend-select for lists.",
                line=where.payload_line(identity, path),
            )
    for identity, path, message in find_unbound_tool_config(payloads, owners):
        yield Finding(
            CheckRule.UNBOUND_TOOL_CONFIG,
            message,
            where.file,
            f"dev.pyproject.{identity}",
            hint="Write the payload as a table with content and requires, so "
            "--no-<tool> leaves no configuration behind.",
            line=where.payload_line(identity, path),
        )
    for package, owner, message in find_unbound_tool_packages(
        blueprint.dev_dependencies
    ):
        yield Finding(
            CheckRule.UNBOUND_TOOL_PACKAGE,
            message,
            where.file,
            "dev.dev_dependencies",
            hint=f'Move it to [[optional]] with requires = "{owner}", so '
            f"--no-{owner} does not install it.",
            line=where.index.line_in_value(("dev", "dev_dependencies"), package),
        )


@cache
def module_baselines() -> dict[str, dict[str, Any]]:
    """Returns each tooling module's pyproject.toml contribution, by module."""
    from .manifest import EnvironmentManifest
    from .modules import TOOLING_MODULES

    baselines: dict[str, dict[str, Any]] = {}
    for module in TOOLING_MODULES:
        manifest = EnvironmentManifest()
        module.build(manifest)
        contributions = manifest.filesystem.structured.get("pyproject.toml", [])
        if contributions:
            baselines[module.config_key] = _parse_payload(
                "\n".join(c.content for c in contributions)
            )
    return baselines


def _parse_payload(content: str) -> dict[str, Any]:
    """Parses TOML whose placeholders may stand where a key belongs."""
    return tomllib.loads(VARIABLE_PATTERN.sub(_PLACEHOLDER_VALUE, content))


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
    payload: str,
    baselines: Mapping[str, dict[str, Any]],
    requires: Condition | None = None,
) -> list[tuple[tuple[str, ...], str]]:
    """Lists ways a template's TOML payload restates a module baseline.

    Overriding a baseline scalar with a different value is a legitimate delta.
    What is flagged is repeating a baseline value verbatim, and redefining a
    baseline list where an additive key (e.g. ``extend-select``) exists. A
    payload bound to tools is compared only with those tools' baselines; an
    unbound one with every baseline.

    Args:
        payload: The TOML payload.
        baselines: Each tool's baseline, keyed by tool.
        requires: When the payload is injected, if it is gated.

    Returns:
        (key path within the payload, message) for each violation.
    """
    bound = _bound_tools(requires)
    if bound:
        baselines = {tool: baselines.get(tool, {}) for tool in sorted(bound)}
    violations: list[tuple[tuple[str, ...], str]] = []
    for path, value in _leaves(_parse_payload(payload)):
        dotted = ".".join(path)
        for tool, baseline in baselines.items():
            base_value = _lookup(baseline, path)
            if base_value is _MISSING:
                continue
            if value == base_value:
                violations.append(
                    (path, f"{dotted} repeats the {tool} baseline verbatim.")
                )
            elif isinstance(value, list) and isinstance(base_value, list):
                if path not in ATOMIC_LISTS_WITHOUT_ADDITIVE_KEY:
                    violations.append(
                        (
                            path,
                            f"{dotted} redefines the {tool} baseline list "
                            "instead of adding to it.",
                        )
                    )
                elif not all(item in value for item in base_value):
                    violations.append(
                        (path, f"{dotted} drops entries from the {tool} baseline list.")
                    )
    return violations


def _bound_tools(requires: Condition | None) -> frozenset[str]:
    """Returns the tools a condition requires, which gated content belongs to."""
    from .recipe import Tool

    names = requires.names if requires is not None else frozenset()
    return names & {tool.value for tool in Tool}


def find_unbound_tool_config(
    payloads: Mapping[str, tuple[str, Condition | None]], owners: Mapping[str, str]
) -> list[tuple[str, tuple[str, ...], str]]:
    """Lists payloads that configure a tool without declaring ``requires`` for it.

    Args:
        payloads: Each payload's (content, requires), keyed by identity.
        owners: The tool owning each ``tool.<table>`` name.

    Returns:
        (identity, key path within the payload, message) for each problem.
    """
    problems: list[tuple[str, tuple[str, ...], str]] = []
    for identity, (content, requires) in payloads.items():
        for table in _parse_payload(content).get("tool", {}):
            owner = owners.get(table)
            if owner and owner not in _bound_tools(requires):
                declared = repr(str(requires)) if requires is not None else "None"
                problems.append(
                    (
                        identity,
                        ("tool", table),
                        f"The payload configures tool.{table} but declares "
                        f'requires = {declared}; expected "{owner}".',
                    )
                )
    return problems


def find_unbound_tool_packages(
    dev_dependencies: list[str],
) -> list[tuple[str, str, str]]:
    """Lists always-installed dev packages that belong to a tool's toolchain.

    Args:
        dev_dependencies: The template's unconditional dev packages.

    Returns:
        (package, owning tool, message) for each problem.
    """
    problems: list[tuple[str, str, str]] = []
    for dependency in dev_dependencies:
        name = re.split(r"[\[<>=!~; ]", dependency, maxsplit=1)[0].lower()
        for prefix, owner in TOOL_PACKAGE_OWNERS.items():
            if name == prefix or name.startswith(f"{prefix}-"):
                problems.append(
                    (
                        dependency,
                        owner,
                        f"'{dependency}' is installed unconditionally but "
                        f"belongs to {owner}.",
                    )
                )
    return problems
