"""Blocks credential-shaped template variables before they reach a project.

Template variables are non-secret by definition: their values render into
generated files that get committed. This guard backs that rule up. It checks
each variable name against a short list of names that read as credentials, and
each value against gitleaks' default rule set, translated from Go to Python at
build time into ``protostar._secret_rules`` by ``scripts/sync_secret_rules.py``.

The generated module stores the rules compressed rather than as text, so that
secret scanners, in this repository or in an installed wheel, do not mistake
their patterns, or the publicly known keys some allowlists name, for leaked
credentials. ``load_rules`` decodes them the first time a value is scanned.

A block has no override, so the value check ports gitleaks' own detector
(``detect/detect.go`` at the pinned tag) instead of adding heuristics: a rule
runs only when one of its keywords appears, and secret groups, entropy
thresholds, and allowlists apply exactly as gitleaks applies them. Two gitleaks
behaviors are deliberately absent. A ``gitleaks:allow`` marker in a value is
ignored, since honoring it would be an override. Encoded segments are not
decoded, so a base64-wrapped token is checked as given.
"""

from __future__ import annotations

import base64
import dataclasses
import functools
import json
import math
import re
import zlib
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .docs_registry import DocsPage
from .errors import ConfigurationError, SecretDetectedError, TemplateResolutionError

# Bounds scan time: matching cost grows with length, reaching about half a
# second across all rules for a 2,000-character value.
MAX_VALUE_LENGTH = 1024

# Names that read as credentials. Matched against the lowercased name; widen
# only on evidence, since every hit blocks a template from loading.
_CREDENTIAL_NAME = re.compile(
    r"(?:^|_)(?:password|passwd|secret|secret_?key|token|api_?key|access_?key"
    r"|private_?key|credentials?)$"
)


class AllowlistCondition(StrEnum):
    """How an allowlist combines its checks."""

    OR = "or"
    AND = "and"


class AllowlistTarget(StrEnum):
    """Which text an allowlist's regexes are matched against."""

    SECRET = "secret"  # noqa: S105 - names what an allowlist matches, not a credential
    MATCH = "match"
    LINE = "line"


@dataclass(frozen=True, slots=True)
class Allowlist:
    """Exceptions that suppress a finding, as gitleaks defines them.

    Attributes:
        condition: Whether the regex and stopword checks must both pass (AND)
            or either one suffices (OR).
        target: The text the regexes are matched against.
        regexes: Python patterns; any match allows the finding.
        stopwords: Lowercase words; any one inside the secret allows it.
    """

    condition: AllowlistCondition = AllowlistCondition.OR
    target: AllowlistTarget = AllowlistTarget.SECRET
    regexes: tuple[str, ...] = ()
    stopwords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Rule:
    """One gitleaks detection rule, translated to Python regex syntax.

    Attributes:
        rule_id: The gitleaks rule id, reported in findings.
        pattern: The detection pattern, compiled with ``re.ASCII``.
        keywords: Lowercase words, one of which must appear for the rule to run.
        entropy: Minimum Shannon entropy a secret must exceed, if any.
        secret_group: The capture group holding the secret; 0 picks the first
            non-empty group.
        allowlists: Rule-specific exceptions, checked after the global ones.
    """

    rule_id: str
    pattern: str
    keywords: tuple[str, ...]
    entropy: float | None = None
    secret_group: int = 0
    allowlists: tuple[Allowlist, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Every detection rule, plus the allowlists that apply to all of them.

    Attributes:
        rules: The detection rules, sorted by id.
        global_allowlists: Exceptions checked before each rule's own.
    """

    rules: tuple[Rule, ...]
    global_allowlists: tuple[Allowlist, ...] = ()


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """A variable whose value matched a rule. Never carries the value itself.

    Attributes:
        variable: The template variable name.
        rule: The id of the gitleaks rule that matched.
    """

    variable: str
    rule: str


def check_variable_names(target: str, names: Iterable[str]) -> None:
    """Rejects template variables whose names read as credentials.

    Args:
        target: The template being loaded, named in the error.
        names: The template's custom variable names.

    Raises:
        TemplateResolutionError: If any name reads as a credential.
    """
    flagged = sorted(name for name in names if _CREDENTIAL_NAME.search(name.lower()))
    if flagged:
        raise TemplateResolutionError(
            target,
            f"Template variables are named like credentials: {', '.join(flagged)}.",
            hint=(
                "Template variables are rendered into project files, so they "
                "must not hold secrets. Have the project read secrets from the "
                "environment at runtime, and ship a .env.example that names them."
            ),
            docs_path=DocsPage.TEMPLATE_VARIABLES,
        )


def check_variable_values(values: Mapping[str, str]) -> None:
    """Rejects template variable values that are too long or look like credentials.

    Args:
        values: Custom template variable names mapped to their values.

    Raises:
        ConfigurationError: If any value exceeds ``MAX_VALUE_LENGTH``.
        SecretDetectedError: If any value matches a secret-detection rule.
    """
    too_long = sorted(
        name for name, value in values.items() if len(value) > MAX_VALUE_LENGTH
    )
    if too_long:
        raise ConfigurationError(
            f"Template variable values exceed {MAX_VALUE_LENGTH:,} characters: "
            f"{', '.join(too_long)}.",
            hint="Shorten the values; template variables hold short, non-secret settings.",
        )

    findings = tuple(
        finding
        for name in sorted(values)
        if (finding := scan_value(name, values[name])) is not None
    )
    if findings:
        raise SecretDetectedError(findings)


def scan_value(name: str, value: str) -> SecretFinding | None:
    """Checks one variable value against the secret-detection rules.

    The value is scanned inside the assignment ``name = "value"``, the shape
    gitleaks' rules are tuned for: several rules only fire when the name
    supplies their context.

    Args:
        name: The variable name.
        value: The value to check.

    Returns:
        A finding for the first matching rule, preferring a specific rule over
        a generic one, or None if no rule matches.
    """
    rule_set = load_rules()
    line = f'{name} = "{value}"'
    lowered = line.lower()
    generic: SecretFinding | None = None
    for rule in rule_set.rules:
        if rule.keywords and not any(keyword in lowered for keyword in rule.keywords):
            continue
        if _matches(rule, line, rule_set.global_allowlists):
            finding = SecretFinding(name, rule.rule_id)
            # Like gitleaks, report a specific rule over a generic one.
            if "generic" not in rule.rule_id:
                return finding
            generic = generic or finding
    return generic


@functools.cache
def load_rules() -> RuleSet:
    """Decodes the generated rule set, once per process.

    Returns:
        The rules stored in ``protostar._secret_rules``.
    """
    from ._secret_rules import PAYLOAD

    return decode_rules(PAYLOAD)


def encode_rules(rule_set: RuleSet) -> bytes:
    """Serializes a rule set into the form the generated module stores.

    Args:
        rule_set: The rules to store.

    Returns:
        Base64 of the zlib-compressed JSON rule set.
    """
    document = json.dumps(
        dataclasses.asdict(rule_set), sort_keys=True, separators=(",", ":")
    )
    return base64.b64encode(zlib.compress(document.encode(), 9))


def decode_rules(payload: bytes) -> RuleSet:
    """Reads a rule set stored by ``encode_rules``.

    Args:
        payload: Base64 of the zlib-compressed JSON rule set.

    Returns:
        The decoded rules.
    """
    document = json.loads(zlib.decompress(base64.b64decode(payload)))
    return RuleSet(
        rules=tuple(
            Rule(
                rule_id=rule["rule_id"],
                pattern=rule["pattern"],
                keywords=tuple(rule["keywords"]),
                entropy=rule["entropy"],
                secret_group=rule["secret_group"],
                allowlists=tuple(_decode_allowlist(a) for a in rule["allowlists"]),
            )
            for rule in document["rules"]
        ),
        global_allowlists=tuple(
            _decode_allowlist(a) for a in document["global_allowlists"]
        ),
    )


def _decode_allowlist(document: dict[str, Any]) -> Allowlist:
    return Allowlist(
        condition=AllowlistCondition(document["condition"]),
        target=AllowlistTarget(document["target"]),
        regexes=tuple(document["regexes"]),
        stopwords=tuple(document["stopwords"]),
    )


def shannon_entropy(data: str) -> float:
    """Computes Shannon entropy exactly as gitleaks does.

    gitleaks counts characters but divides by the UTF-8 byte length, so
    non-ASCII text scores lower than a character-based measure would.

    Args:
        data: The text to measure.

    Returns:
        The entropy in bits.
    """
    if not data:
        return 0.0
    inverse_length = 1.0 / len(data.encode())
    entropy = 0.0
    for count in Counter(data).values():
        frequency = count * inverse_length
        entropy -= frequency * math.log2(frequency)
    return entropy


@functools.cache
def _compiled(pattern: str) -> re.Pattern[str]:
    # Go's \w, \d, \s, and \b are ASCII-only; re.ASCII matches that.
    return re.compile(pattern, re.ASCII)


def _matches(rule: Rule, line: str, global_allowlists: tuple[Allowlist, ...]) -> bool:
    pattern = _compiled(rule.pattern)
    for found in pattern.finditer(line):
        match = found.group(0).strip("\n")
        secret = match
        # gitleaks re-runs the rule on the matched text to pick the secret group.
        groups = pattern.search(match)
        if groups is not None and pattern.groups >= 1:
            if rule.secret_group > 0:
                if pattern.groups < rule.secret_group:
                    continue
                secret = groups.group(rule.secret_group) or ""
            else:
                secret = next((group for group in groups.groups() if group), secret)
        if rule.entropy is not None and shannon_entropy(secret) <= rule.entropy:
            continue
        if _allowed(global_allowlists, secret, match, line):
            continue
        if _allowed(rule.allowlists, secret, match, line):
            continue
        return True
    return False


def _allowed(
    allowlists: tuple[Allowlist, ...], secret: str, match: str, line: str
) -> bool:
    for allowlist in allowlists:
        target = {
            AllowlistTarget.SECRET: secret,
            AllowlistTarget.MATCH: match,
            AllowlistTarget.LINE: line,
        }[allowlist.target]
        regex_allowed = bool(target) and any(
            _compiled(regex).search(target) for regex in allowlist.regexes
        )
        lowered = secret.lower()
        stopword_allowed = bool(secret) and any(
            word in lowered for word in allowlist.stopwords
        )
        if allowlist.condition is AllowlistCondition.AND:
            checks = [regex_allowed] if allowlist.regexes else []
            checks += [stopword_allowed] if allowlist.stopwords else []
            allowed = all(checks)
        else:
            allowed = regex_allowed or stopword_allowed
        if allowed:
            return True
    return False
