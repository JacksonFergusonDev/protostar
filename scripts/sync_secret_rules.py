#!/usr/bin/env python3
"""Regenerates src/protostar/_secret_rules.py from gitleaks' default rule set.

The rules come from the gitleaks tag already pinned for the scaffolded
pre-commit hook in src/protostar/_fallbacks.py, so Protostar's secret guard and
that hook agree. Patterns are translated from Go's regexp syntax to Python's
here, at build time, and every translated pattern must compile without a
warning. Anything the translator cannot express stops the script unless the
rule is listed in EXCLUDE with a reason; no rule is dropped silently.

Usage:
    python scripts/sync_secret_rules.py          # regenerate the module
    python scripts/sync_secret_rules.py --check  # exit 1 if it is out of date
    python scripts/sync_secret_rules.py --dump   # print the rules as JSON
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
import warnings
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Self-sufficient under a bare interpreter (the release workflow runs one):
# everything imported below needs only the standard library.
_repo_root = Path(__file__).resolve().parent.parent
for _path in (str(_repo_root), str(_repo_root / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from protostar._fallbacks import DEFAULT_REVISIONS
from protostar.fs import atomic_write_text
from protostar.secret_guard import (
    Allowlist,
    AllowlistCondition,
    AllowlistTarget,
    Rule,
    RuleSet,
    decode_rules,
    encode_rules,
)

GITLEAKS_REPO = "https://github.com/gitleaks/gitleaks"
RAW_URL = "https://raw.githubusercontent.com/gitleaks/gitleaks/{tag}/{path}"
RULES_FILE = _repo_root / "src" / "protostar" / "_secret_rules.py"

# Rules the translator cannot express faithfully, mapped to the reason. They
# are recorded in the generated module's OMITTED table rather than lost.
EXCLUDE: dict[str, str] = {}

# RE2's POSIX classes, as ASCII ranges valid inside a Python character class.
POSIX_CLASSES: dict[str, str] = {
    "alnum": "0-9A-Za-z",
    "alpha": "A-Za-z",
    "ascii": "\\x00-\\x7f",
    "blank": "\\t ",
    "cntrl": "\\x00-\\x1f\\x7f",
    "digit": "0-9",
    "graph": "!-~",
    "lower": "a-z",
    "print": " -~",
    "punct": "!-/:-@\\[-`{-~",
    "space": "\\t\\n\\v\\f\\r ",
    "upper": "A-Z",
    "word": "0-9A-Za-z_",
    "xdigit": "0-9A-Fa-f",
}

_FLAG_GROUP = re.compile(r"\(\?([a-zA-Z-]+)\)")
_RULE_KEYS = frozenset(
    {
        "id",
        "description",
        "regex",
        "path",
        "secretGroup",
        "entropy",
        "keywords",
        "tags",
        "allowlists",
    }
)
_ALLOWLIST_KEYS = frozenset(
    {
        "description",
        "condition",
        "commits",
        "paths",
        "regexTarget",
        "regexes",
        "stopwords",
    }
)
_CONFIG_KEYS = frozenset({"title", "description", "minVersion", "allowlists", "rules"})


class TranslationError(Exception):
    """Raised when a gitleaks pattern or config cannot be carried over faithfully."""


@dataclass(frozen=True)
class Translation:
    """The translated contents of one gitleaks configuration."""

    rules: tuple[Rule, ...]
    global_allowlists: tuple[Allowlist, ...]
    omitted: tuple[tuple[str, str], ...]

    @property
    def rule_set(self) -> RuleSet:
        """The rules and allowlists the guard evaluates."""
        return RuleSet(self.rules, self.global_allowlists)


def translate(pattern: str) -> str:
    """Translates a Go (RE2) regular expression into an equivalent Python one.

    Handles the constructs gitleaks uses that Python reads differently:
    ``\\z`` becomes ``\\Z``, POSIX classes such as ``[[:alnum:]]`` become ASCII
    ranges, a bare ``[`` inside a character class is escaped, ``(?<name>``
    becomes ``(?P<name>``, and an inline flag group such as ``(?i)`` anywhere
    but the start of the pattern becomes scoped groups. In Go that flag covers
    the rest of its branch and every later branch of the same group, so
    ``(A(?i)B|C)`` becomes ``(A(?i:B)|(?i:C))``.

    Args:
        pattern: A Go regular expression.

    Returns:
        The equivalent Python pattern.

    Raises:
        TranslationError: If the pattern uses a construct Python cannot express.
    """
    out: list[str] = []
    # Per open group: the flag sets declared so far, and how many scoped
    # groups the current branch has opened.
    flags: list[list[str]] = [[]]
    opened: list[int] = [0]
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\":
            escape = pattern[i : i + 2]
            if escape == "\\z":
                out.append("\\Z")
            elif escape in ("\\Q", "\\p", "\\P", "\\C"):
                raise TranslationError(f"unsupported escape {escape}")
            else:
                out.append(escape)
            i += 2
        elif char == "[":
            i = _translate_class(pattern, i, out)
        elif char == "(":
            flag_group = _FLAG_GROUP.match(pattern, i)
            if flag_group:
                declared = flag_group.group(1)
                if "U" in declared:
                    raise TranslationError(
                        "ungreedy flag (?U) has no Python equivalent"
                    )
                if i == 0:
                    # Leading flags are global in both engines.
                    out.append(flag_group.group(0))
                else:
                    out.append(f"(?{declared}:")
                    flags[-1].append(declared)
                    opened[-1] += 1
                i = flag_group.end()
                continue
            if pattern.startswith("(?<", i) and pattern[i + 3 : i + 4] not in (
                "=",
                "!",
            ):
                out.append("(?P<")
                i += 3
            else:
                out.append("(")
                i += 1
            flags.append([])
            opened.append(0)
        elif char == "|":
            out.append(")" * opened[-1])
            out.append("|")
            out.extend(f"(?{declared}:" for declared in flags[-1])
            opened[-1] = len(flags[-1])
            i += 1
        elif char == ")":
            if len(flags) == 1:
                raise TranslationError("unbalanced ')'")
            out.append(")" * opened.pop())
            flags.pop()
            out.append(")")
            i += 1
        else:
            out.append(char)
            i += 1
    if len(flags) != 1:
        raise TranslationError("unbalanced '('")
    out.append(")" * opened.pop())
    return "".join(out)


def _translate_class(pattern: str, start: int, out: list[str]) -> int:
    i = start + 1
    out.append("[")
    if pattern[i : i + 1] == "^":
        out.append("^")
        i += 1
    if pattern[i : i + 1] == "]":
        # A leading ']' is a literal in RE2.
        out.append("\\]")
        i += 1
    while i < len(pattern):
        char = pattern[i]
        if char == "\\":
            escape = pattern[i : i + 2]
            if escape in ("\\Q", "\\p", "\\P"):
                raise TranslationError(f"unsupported escape {escape} in a class")
            out.append(escape)
            i += 2
        elif pattern.startswith("[:", i):
            end = pattern.find(":]", i + 2)
            name = pattern[i + 2 : end] if end != -1 else ""
            if name not in POSIX_CLASSES:
                raise TranslationError(f"unsupported POSIX class [:{name}:]")
            out.append(POSIX_CLASSES[name])
            i = end + 2
        elif char == "[":
            # RE2 reads a bare '[' in a class literally; Python warns about it.
            out.append("\\[")
            i += 1
        elif char == "]":
            out.append("]")
            return i + 1
        else:
            out.append(char)
            i += 1
    raise TranslationError("unterminated character class")


def compile_strict(pattern: str) -> None:
    """Compiles a translated pattern the way the guard does, warnings as errors.

    Args:
        pattern: A Python pattern produced by ``translate``.

    Raises:
        TranslationError: If Python rejects the pattern or warns about it.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # A cached pattern is not re-parsed, so it would not warn again.
        re.purge()
        try:
            re.compile(pattern, re.ASCII)
        except (re.error, FutureWarning, DeprecationWarning) as error:
            raise TranslationError(f"does not compile in Python: {error}") from error


def convert_allowlist(raw: dict[str, Any]) -> Allowlist | None:
    """Converts one gitleaks allowlist, keeping only the checks a value can meet.

    A variable value has no file path or commit. An OR allowlist's path and
    commit checks never apply to it, so only its regexes and stopwords are kept.
    An AND allowlist with a path or commit check can never pass, so it is
    dropped entirely.

    Args:
        raw: The allowlist table from the gitleaks configuration.

    Returns:
        The allowlist, or None if it can never apply to a variable value.

    Raises:
        TranslationError: If the allowlist uses a field or value this script
            does not understand.
    """
    unknown = set(raw) - _ALLOWLIST_KEYS
    if unknown:
        raise TranslationError(f"unknown allowlist fields: {sorted(unknown)}")
    condition_name = str(raw.get("condition", "")).upper()
    if condition_name in ("", "OR", "||"):
        condition = AllowlistCondition.OR
    elif condition_name in ("AND", "&&"):
        condition = AllowlistCondition.AND
    else:
        raise TranslationError(f"unknown allowlist condition {raw['condition']!r}")
    try:
        target = AllowlistTarget(raw.get("regexTarget") or "secret")
    except ValueError as error:
        raise TranslationError(
            f"unknown allowlist target {raw['regexTarget']!r}"
        ) from error

    if condition is AllowlistCondition.AND and (raw.get("paths") or raw.get("commits")):
        return None
    regexes = tuple(translate(regex) for regex in raw.get("regexes", []))
    for regex in regexes:
        compile_strict(regex)
    stopwords = tuple(sorted({word.lower() for word in raw.get("stopwords", [])}))
    if not regexes and not stopwords:
        return None
    return Allowlist(condition, target, regexes, stopwords)


def convert(config: dict[str, Any]) -> Translation:
    """Converts a parsed gitleaks configuration into guard rules.

    Args:
        config: The parsed ``gitleaks.toml``.

    Returns:
        The rules sorted by id, the global allowlists, and every omitted rule
        with the reason.

    Raises:
        TranslationError: If the configuration uses a field this script does
            not understand, or a rule outside EXCLUDE cannot be translated.
    """
    raw_config = dict(config)
    if "allowlist" in raw_config:
        # The deprecated single-table form of [[allowlists]].
        raw_config.setdefault("allowlists", []).append(raw_config.pop("allowlist"))
    unknown = set(raw_config) - _CONFIG_KEYS
    if unknown:
        raise TranslationError(f"unknown configuration fields: {sorted(unknown)}")

    global_allowlists: list[Allowlist] = []
    targeted: dict[str, list[Allowlist]] = {}
    for raw in raw_config.get("allowlists", []):
        raw = dict(raw)
        target_rules = raw.pop("targetRules", [])
        allowlist = convert_allowlist(raw)
        if allowlist is None:
            continue
        if target_rules:
            for rule_id in target_rules:
                targeted.setdefault(rule_id, []).append(allowlist)
        else:
            global_allowlists.append(allowlist)

    rules: list[Rule] = []
    omitted: list[tuple[str, str]] = []
    for raw in raw_config["rules"]:
        raw = dict(raw)
        rule_id = raw["id"]
        if "allowlist" in raw:
            raw.setdefault("allowlists", []).append(raw.pop("allowlist"))
        unknown = set(raw) - _RULE_KEYS
        if unknown:
            raise TranslationError(f"{rule_id}: unknown rule fields: {sorted(unknown)}")
        if "path" in raw:
            omitted.append((rule_id, "applies only to files matching a path"))
            continue
        if rule_id in EXCLUDE:
            omitted.append((rule_id, EXCLUDE[rule_id]))
            continue
        try:
            pattern = translate(raw["regex"])
            compile_strict(pattern)
            allowlists = [
                allowlist
                for entry in raw.get("allowlists", [])
                if (allowlist := convert_allowlist(entry)) is not None
            ]
        except TranslationError as error:
            raise TranslationError(f"{rule_id}: {error}") from error
        entropy = float(raw.get("entropy", 0.0))
        rules.append(
            Rule(
                rule_id=rule_id,
                pattern=pattern,
                keywords=tuple(keyword.lower() for keyword in raw.get("keywords", [])),
                entropy=entropy or None,
                secret_group=int(raw.get("secretGroup", 0)),
                allowlists=(*allowlists, *targeted.pop(rule_id, [])),
            )
        )
    if targeted:
        raise TranslationError(f"allowlists target unknown rules: {sorted(targeted)}")
    return Translation(
        rules=tuple(sorted(rules, key=lambda rule: rule.rule_id)),
        global_allowlists=tuple(global_allowlists),
        omitted=tuple(sorted(omitted)),
    )


def generate(
    tag: str, source: bytes, license_text: str, committed: str | None = None
) -> str:
    """Generates the rules module for one gitleaks tag.

    zlib output can differ between builds of the same Python version, so the
    committed payload is kept whenever it already decodes to the same rules.
    That keeps regeneration, and ``--check``, stable across machines.

    Args:
        tag: The gitleaks tag the rules come from.
        source: The raw bytes of that tag's ``config/gitleaks.toml``.
        license_text: That tag's LICENSE file.
        committed: The current module text, if one exists.

    Returns:
        The complete module source.
    """
    translation = convert(tomllib.loads(source.decode("utf-8")))
    payload = encode_rules(translation.rule_set)
    previous = read_payload(committed) if committed is not None else None
    if previous is not None:
        try:
            if decode_rules(previous) == translation.rule_set:
                payload = previous
        except (ValueError, KeyError, TypeError, zlib.error):
            pass  # Unreadable: replace it with a fresh payload.
    return render(tag, source, license_text, translation, payload)


def render(
    tag: str,
    source: bytes,
    license_text: str,
    translation: Translation,
    payload: bytes,
) -> str:
    """Renders the module around an encoded rule set.

    Args:
        tag: The gitleaks tag the rules come from.
        source: The raw bytes of that tag's ``config/gitleaks.toml``.
        license_text: That tag's LICENSE file.
        translation: The translated configuration, for the omitted-rule table.
        payload: The rule set as ``encode_rules`` stores it.

    Returns:
        The complete module source.
    """
    lines = [
        '"""Secret-detection rules translated from gitleaks\' default configuration.',
        "",
        "Auto-generated by scripts/sync_secret_rules.py. Do not edit manually;",
        "run `just sync-secret-rules` instead.",
        "",
        f"Source: {RAW_URL.format(tag=tag, path='config/gitleaks.toml')}",
        f"SHA-256: {hashlib.sha256(source).hexdigest()}",
        "",
        "The rules are stored compressed rather than as text, so that secret",
        "scanners do not mistake their patterns, or the publicly known keys some",
        "allowlists name, for leaked credentials. `python scripts/sync_secret_rules.py",
        "--dump` prints them.",
        "",
        "Patterns are translated from Go's regexp syntax to Python's. gitleaks is",
        "distributed under the following license:",
        "",
        *(f"    {line}".rstrip() for line in license_text.strip().splitlines()),
        '"""',
        "",
        f"GITLEAKS_VERSION = {json.dumps(tag)}",
        "",
        "# gitleaks rules not carried over, with the reason.",
        "OMITTED: tuple[tuple[str, str], ...] = (",
        *(
            f"    ({json.dumps(rule_id)}, {json.dumps(reason)}),"
            for rule_id, reason in translation.omitted
        ),
        ")",
        "",
        "# Base64 of the zlib-compressed JSON rule set; see protostar.secret_guard.",
        "PAYLOAD = (",
        *(
            f'    b"{payload[i : i + 76].decode("ascii")}"'
            for i in range(0, len(payload), 76)
        ),
        ")",
        "",
    ]
    return "\n".join(lines)


def read_payload(module_text: str) -> bytes | None:
    """Reads the PAYLOAD literal from generated module text without running it.

    Args:
        module_text: The source of a generated rules module.

    Returns:
        The payload bytes, or None if the text has no valid PAYLOAD.
    """
    try:
        tree = ast.parse(module_text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PAYLOAD"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return value if isinstance(value, bytes) else None
    return None


def _fetch(tag: str, path: str) -> bytes:
    url = RAW_URL.format(tag=tag, path=path)
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return bytes(response.read(10 * 1024 * 1024))
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Failed to fetch {url}: {error}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Regenerates the rules module, checks that it is current, or prints it."""
    parser = argparse.ArgumentParser(
        description="Regenerate the secret-detection rules from gitleaks."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the committed module differs from a fresh generation.",
    )
    modes.add_argument(
        "--dump",
        action="store_true",
        help="Print the committed rules as readable JSON and exit.",
    )
    args = parser.parse_args()

    current = RULES_FILE.read_text(encoding="utf-8") if RULES_FILE.exists() else None
    if args.dump:
        payload = read_payload(current) if current is not None else None
        if payload is None:
            print(f"No rules payload in {RULES_FILE.relative_to(_repo_root)}.")
            sys.exit(1)
        print(json.dumps(dataclasses.asdict(decode_rules(payload)), indent=2))
        return

    tag = DEFAULT_REVISIONS[GITLEAKS_REPO]
    print(f"Fetching gitleaks {tag} rules...")
    source = _fetch(tag, "config/gitleaks.toml")
    license_text = _fetch(tag, "LICENSE").decode("utf-8")
    try:
        content = generate(tag, source, license_text, current)
    except TranslationError as error:
        print(f"Cannot translate gitleaks {tag}: {error}", file=sys.stderr)
        print("Extend the translator, or add the rule to EXCLUDE with a reason.")
        sys.exit(1)

    if args.check:
        if content != current:
            print(
                f"{RULES_FILE.relative_to(_repo_root)} is out of date with gitleaks "
                f"{tag}. Run `just sync-secret-rules` and commit the result."
            )
            sys.exit(1)
        print(f"Secret rules match gitleaks {tag}.")
        return
    if content == current:
        print(f"Secret rules already match gitleaks {tag}.")
        return
    atomic_write_text(RULES_FILE, content)
    print(f"Wrote {RULES_FILE.relative_to(_repo_root)} from gitleaks {tag}.")


if __name__ == "__main__":
    main()
