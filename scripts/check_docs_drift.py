"""Checks that hand-written documentation still agrees with the code.

Some documentation is prose around facts the code already decides: which errors
exist and what they exit with, which templates ship, which Python version is
supported, which files and tests a page names. Generating a fixture for each
would cost more than it saves, so this script derives the fact from the code and
fails when a page disagrees, naming the fix.

Run:
    uv run python scripts/check_docs_drift.py
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import (
    DOCS_DIR,
    REPO_ROOT,
    OutputStyle,
    fixture_environment,
    report,
)
from scripts.check_doc_links import docs_path_to_file, extract_anchors

FIRST_PROJECT = DOCS_DIR / "first-project.md"
CLI_REFERENCE = DOCS_DIR / "usage" / "cli-reference.md"
ERROR_HANDLING = DOCS_DIR / "mechanics" / "error_handling.md"
API_REFERENCE = DOCS_DIR / "developer" / "api-reference.md"
EXIT_CODE_TABLE = DOCS_DIR / "generated" / "table_exit_codes.md"
BUILT_IN_TEMPLATES = DOCS_DIR / "developer" / "built-in-templates.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
README = REPO_ROOT / "README.md"
AGENTS = REPO_ROOT / "AGENTS.md"
CONTRACT_TEST = REPO_ROOT / "tests" / "test_builtin_template_contract.py"

# Pages written for Protostar's own maintainers. Their file, test, and recipe
# names refer to this repository, unlike a user guide's scaffolded projects.
MAINTAINER_PAGES = (
    CONTRIBUTING,
    AGENTS,
    *sorted((DOCS_DIR / "developer").rglob("*.md")),
)

# Pages the site publishes from outside docs/, so no Markdown file backs them.
PUBLISHED_ELSEWHERE = {"metrics/": "metrics/index.html"}

# Paths a maintainer page shows as examples of the pattern, not as files.
PLACEHOLDER_PATHS = frozenset({"tests/path/to/test.py", "tests/test_foo.py"})


def _hand_written_pages() -> list[Path]:
    """Returns every Markdown page a person writes, excluding generated fixtures."""
    generated = DOCS_DIR / "generated"
    docs = [p for p in sorted(DOCS_DIR.rglob("*.md")) if generated not in p.parents]
    return [*docs, README, CONTRIBUTING, AGENTS]


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _error_classes() -> list[type]:
    """Returns ProtostarError and its subclasses, in definition order."""
    from protostar.errors import ProtostarError

    found: list[type] = [ProtostarError]

    def walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            if sub not in found:
                found.append(sub)
                walk(sub)

    walk(ProtostarError)
    return found


def _section(text: str, heading: str) -> str:
    """Returns the body of a ``##`` section, up to the next ``##`` heading."""
    match = re.search(
        rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE
    )
    return match.group(1) if match else ""


# ── Errors ───────────────────────────────────────────────────────────────────


def _render_error_tree() -> str:
    """Renders the exception hierarchy in the style ``error_handling.md`` shows."""
    from protostar.errors import ProtostarError

    lines = ["ProtostarError (Exception)"]

    def walk(cls: type, prefix: str) -> None:
        children = cls.__subclasses__()
        for index, child in enumerate(children):
            last = index == len(children) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{child.__name__}")
            walk(child, prefix + ("    " if last else "│   "))

    walk(ProtostarError, " ")
    return "\n".join(lines)


def check_error_tree() -> list[str]:
    """The exception tree in error_handling.md lists every error where it sits."""
    section = _section(
        ERROR_HANDLING.read_text(encoding="utf-8"), "The Exception Hierarchy"
    )
    block = re.search(r"```text\n(.*?)\n```", section, re.DOTALL)
    expected = _render_error_tree()
    if block is None:
        return [
            f"{_rel(ERROR_HANDLING)}: no ```text tree under 'The Exception Hierarchy'"
        ]
    actual = "\n".join(line.rstrip() for line in block.group(1).splitlines())
    if actual == expected:
        return []
    return [
        f"{_rel(ERROR_HANDLING)}: the exception tree is stale. Replace it with:\n"
        + "\n".join(f"      {line}" for line in expected.splitlines())
    ]


def check_error_sections() -> list[str]:
    """error_handling.md has one ``### `Name` `` section per error, and no others."""
    text = ERROR_HANDLING.read_text(encoding="utf-8")
    documented = set(re.findall(r"^### `(\w+Error)`$", text, re.MULTILINE))
    actual = {cls.__name__ for cls in _error_classes()}
    problems = [
        f"{_rel(ERROR_HANDLING)}: no '### `{name}`' section"
        for name in sorted(actual - documented)
    ]
    problems += [
        f"{_rel(ERROR_HANDLING)}: '### `{name}`' documents an error that does not exist"
        for name in sorted(documented - actual)
    ]
    return problems


def check_error_names() -> list[str]:
    """Every error a page names is a Protostar error or a Python built-in."""
    import builtins

    known = {cls.__name__ for cls in _error_classes()} | set(dir(builtins))
    problems: list[str] = []
    for page in _hand_written_pages():
        names = set(re.findall(r"`([A-Z]\w*Error)\b", page.read_text(encoding="utf-8")))
        problems.extend(
            f"{_rel(page)}: '{name}' is not an error Protostar raises"
            for name in sorted(names - known)
        )
    return problems


def check_api_reference_errors() -> list[str]:
    """api-reference.md renders every error, or the whole errors module."""
    text = API_REFERENCE.read_text(encoding="utf-8")
    if re.search(r"^\s*::: protostar\.errors\s*$", text, re.MULTILINE):
        return []
    rendered = set(re.findall(r"::: protostar\.errors\.(\w+)", text))
    return [
        f"{_rel(API_REFERENCE)}: '::: protostar.errors.{cls.__name__}' is missing"
        for cls in _error_classes()
        if cls.__name__ not in rendered
    ]


def check_exit_code_table() -> list[str]:
    """The exit-code table matches ``exit_code_for`` for every error."""
    from protostar.errors import ExitCode, ProtostarError, exit_code_for

    by_name = {cls.__name__: cls for cls in _error_classes()}
    problems: list[str] = []
    documented: dict[int, list[type[ProtostarError]]] = {}
    for line in EXIT_CODE_TABLE.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not re.fullmatch(r"`\d+`", cells[0]):
            continue
        code = int(cells[0].strip("`"))
        for name in re.findall(r"`(\w+Error)`", cells[2]):
            cls = by_name.get(name)
            if cls is None:
                problems.append(f"exit-code table: `{name}` is not an error")
                continue
            documented.setdefault(code, []).append(cls)
            if exit_code_for(cls) != code:
                problems.append(
                    f"exit-code table: `{name}` is listed under {code}, "
                    f"but the CLI exits {int(exit_code_for(cls))}"
                )
    for cls in _error_classes():
        code = int(exit_code_for(cls))
        if code == ExitCode.FAILURE:
            continue
        if not any(issubclass(cls, listed) for listed in documented.get(code, [])):
            problems.append(
                f"exit-code table: nothing under {code} covers `{cls.__name__}`"
            )
    listed_codes = set(documented) | {int(ExitCode.OK), int(ExitCode.SOFTWARE)}
    problems += [
        f"exit-code table: ExitCode.{member.name} ({int(member)}) has no row"
        for member in ExitCode
        if int(member) not in listed_codes and member != ExitCode.FAILURE
    ]
    return problems


# ── Project facts ────────────────────────────────────────────────────────────


def check_built_in_templates() -> list[str]:
    """built-in-templates.md names exactly the templates that ship."""
    from protostar.templates.discovery import builtin_template_aliases

    shipped = set(builtin_template_aliases())
    text = BUILT_IN_TEMPLATES.read_text(encoding="utf-8")
    match = re.search(r"ships these built-in templates: ([^.]+)\.", text)
    if match is None:
        return [
            f"{_rel(BUILT_IN_TEMPLATES)}: no 'ships these built-in templates: ...' sentence"
        ]
    named = set(re.findall(r"`([\w-]+)`", match.group(1)))
    if named == shipped:
        return []
    return [
        f"{_rel(BUILT_IN_TEMPLATES)}: names {sorted(named)}, but {sorted(shipped)} ship"
    ]


def _contract_quality_flags() -> tuple[str, ...]:
    """Reads QUALITY_FLAGS from the contract test without importing the tests."""
    tree = ast.parse(CONTRACT_TEST.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "QUALITY_FLAGS" for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            return tuple(str(item) for item in value)
    raise LookupError(f"QUALITY_FLAGS not found in {_rel(CONTRACT_TEST)}")


def check_quality_flags() -> list[str]:
    """The quality flags CONTRIBUTING.md and AGENTS.md list match the contract test."""
    flags = _contract_quality_flags()
    problems: list[str] = []
    for page in (CONTRIBUTING, AGENTS):
        text = page.read_text(encoding="utf-8")
        listed = re.search(r"quality flag explicitly(?:\*\*)? \(([^)]+)\)", text)
        if listed is None:
            problems.append(f"{_rel(page)}: no 'quality flag explicitly (...)' list")
        elif tuple(re.findall(r"`(\w+)`", listed.group(1))) != flags:
            problems.append(
                f"{_rel(page)}: lists {re.findall(r'`(\w+)`', listed.group(1))}, "
                f"but the contract has {list(flags)}"
            )
    return problems


def check_python_version() -> list[str]:
    """The README and CONTRIBUTING name the minimum Python in pyproject.toml."""
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    minimum = re.sub(r"[^\d.]", "", pyproject["project"]["requires-python"])
    problems: list[str] = []
    claims = (
        (README, r"Python ([\d.]+)\+"),
        (CONTRIBUTING, r"\*\*Python ([\d.]+)\+\*\*"),
    )
    for page, pattern in claims:
        match = re.search(pattern, page.read_text(encoding="utf-8"))
        if match is None:
            problems.append(f"{_rel(page)}: no minimum Python version found")
        elif match.group(1) != minimum:
            problems.append(
                f"{_rel(page)}: says Python {match.group(1)}+, but pyproject.toml requires {minimum}+"
            )
    return problems


def check_release_pins() -> list[str]:
    """No page pins a Protostar release, which would go stale with the next one."""
    pin = re.compile(r"protostar@\d[\w.]*")
    problems: list[str] = []
    for page in _hand_written_pages():
        for number, line in enumerate(
            page.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for match in pin.finditer(line):
                problems.append(
                    f"{_rel(page)}:{number}: pins {match.group(0)}; read the "
                    "release from protostar.lock's producer_version instead"
                )
    return problems


# ── References ───────────────────────────────────────────────────────────────


def _outside_fences_of_other_projects(text: str) -> str:
    """Drops text that shows a scaffolded project rather than this repository."""
    return re.sub(
        r"<!-- BEGIN_[A-Z_]+ -->.*?<!-- END_[A-Z_]+ -->", "", text, flags=re.DOTALL
    )


def check_repository_paths() -> list[str]:
    """Source, script, and test paths a page names still exist."""
    problems: list[str] = []
    for page in _hand_written_pages():
        text = page.read_text(encoding="utf-8")
        roots = "src/protostar|scripts"
        if page in MAINTAINER_PAGES:
            roots += "|tests"
        found: set[str] = set()
        for match in re.finditer(rf"\b(?:{roots})/[\w./-]*[\w-]", text):
            # A glob such as tests/test_*.py names no single file.
            if text[match.end() : match.end() + 1] not in {"*", "<", "{"}:
                found.add(match.group(0))
        for path in sorted(found - PLACEHOLDER_PATHS):
            if not (REPO_ROOT / path).exists():
                problems.append(f"{_rel(page)}: '{path}' does not exist")
    return problems


def _test_names() -> set[str]:
    names: set[str] = set()
    for test_file in (REPO_ROOT / "tests").rglob("test_*.py"):
        names.add(test_file.stem)
        names.update(
            re.findall(
                r"^\s*(?:async )?def (test_\w+)",
                test_file.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
    return names


def check_test_names() -> list[str]:
    """Tests a maintainer page cites by name still exist."""
    known = _test_names()
    problems: list[str] = []
    for page in MAINTAINER_PAGES:
        text = page.read_text(encoding="utf-8")
        for name in sorted(set(re.findall(r"`(test_\w+)`", text))):
            if name not in known:
                problems.append(f"{_rel(page)}: test '{name}' does not exist")
    return problems


def _just_recipes() -> set[str]:
    recipes: set[str] = set()
    for line in (REPO_ROOT / "justfile").read_text(encoding="utf-8").splitlines():
        if line.startswith("set ") or re.match(r"^\w+\s*:=", line):
            continue
        match = re.match(r"^([a-z][\w-]*)\b[^\n]*?:(?!=)", line)
        if match:
            recipes.add(match.group(1))
    return recipes


def check_just_recipes() -> list[str]:
    """``just <recipe>`` commands a maintainer page names are in the justfile."""
    recipes = _just_recipes()
    problems: list[str] = []
    for page in MAINTAINER_PAGES:
        text = _outside_fences_of_other_projects(page.read_text(encoding="utf-8"))
        for name in sorted(set(re.findall(r"`just ([a-z][\w-]*)", text))):
            if name not in recipes:
                problems.append(f"{_rel(page)}: 'just {name}' is not a justfile recipe")
    return problems


def _nav_pages(nav: object) -> Iterator[str]:
    if isinstance(nav, str):
        yield nav
    elif isinstance(nav, list):
        for item in nav:
            yield from _nav_pages(item)
    elif isinstance(nav, dict):
        for value in nav.values():
            yield from _nav_pages(value)


def check_navigation() -> list[str]:
    """Every documentation page is in the site navigation, and every entry exists."""
    config = tomllib.loads((REPO_ROOT / "zensical.toml").read_text(encoding="utf-8"))
    in_nav = set(
        _nav_pages(config["project"]["nav"] if "project" in config else config["nav"])
    )
    on_disk = {
        p.relative_to(DOCS_DIR).as_posix()
        for p in DOCS_DIR.rglob("*.md")
        if "generated" not in p.relative_to(DOCS_DIR).parts
    }
    problems = [
        f"docs/{page}: not in the zensical.toml nav"
        for page in sorted(on_disk - in_nav)
    ]
    problems += [
        f"zensical.toml: nav entry '{page}' has no file"
        for page in sorted(in_nav - on_disk)
    ]
    return problems


def _top_level_pages(nav: list[Any]) -> set[str]:
    """Pages listed directly in the navigation, outside any section."""
    return {
        value
        for entry in nav
        for value in (entry.values() if isinstance(entry, dict) else [entry])
        if isinstance(value, str)
    }


def _front_matter(page: Path) -> str:
    match = re.match(r"---\n(.*?)\n---\n", page.read_text(encoding="utf-8"), re.DOTALL)
    return match.group(1) if match else ""


def check_page_front_matter() -> list[str]:
    """Every page has a description, and only top-level pages have a nav icon (house-style)."""
    config = tomllib.loads((REPO_ROOT / "zensical.toml").read_text(encoding="utf-8"))
    top_level = _top_level_pages(config["project"]["nav"])
    problems: list[str] = []
    icons: dict[str, str] = {}
    for page in _hand_written_pages():
        if DOCS_DIR not in page.parents:
            continue
        name = page.relative_to(DOCS_DIR).as_posix()
        meta = _front_matter(page)
        if not re.search(r"^description: \S", meta, re.MULTILINE):
            problems.append(
                f"docs/{name}: front matter needs a one-sentence description"
            )
        icon = re.search(r"^icon: (\S+)", meta, re.MULTILINE)
        if name in top_level and not icon:
            problems.append(
                f"docs/{name}: a top-level page needs an icon in its front matter"
            )
        elif icon and name not in top_level:
            problems.append(
                f"docs/{name}: only top-level pages carry a nav icon; remove it"
            )
        elif icon:
            if icon.group(1) in icons:
                problems.append(
                    f"docs/{name}: shares the icon {icon.group(1)} with docs/{icons[icon.group(1)]}"
                )
            icons[icon.group(1)] = name
    return problems


def check_card_grids() -> list[str]:
    """Every card grid has two, four, or six cards (house-style)."""
    problems: list[str] = []
    for page in _hand_written_pages():
        text = page.read_text(encoding="utf-8")
        for grid in re.finditer(
            r'<div class="grid cards" markdown>(.*?)</div>', text, re.DOTALL
        ):
            cards = len(re.findall(r"^- ", grid.group(1), re.MULTILINE))
            if cards not in (2, 4, 6):
                line = text.count("\n", 0, grid.start()) + 1
                problems.append(
                    f"{_rel(page)}:{line}: a card grid has {cards} cards. Use 2, 4, or 6, keeping only the ones that earn their place"
                )
    return problems


# A list item that is a link and a colon in bold, then its description: the
# "Next Steps" shape. A link that only starts a sentence doesn't match.
_LINK_ITEM = re.compile(
    r"^\s*[-*] (?:\*\*|__)\[([^\]]+)\]\([^)]+\):(?:\*\*|__)", re.MULTILINE
)


def check_link_icons() -> list[str]:
    """Every standalone link in a list carries a house-style icon (house-style)."""
    problems: list[str] = []
    for page in _hand_written_pages():
        if DOCS_DIR not in page.parents:
            continue
        text = page.read_text(encoding="utf-8")
        for item in _LINK_ITEM.finditer(text):
            if "hs-icon" not in item.group(1):
                line = text.count("\n", 0, item.start()) + 1
                problems.append(
                    f"{_rel(page)}:{line}: the link to {item.group(1)!r} needs an icon "
                    'saying where it goes, such as <span class="hs-icon hs-icon-arrow-right" '
                    'aria-hidden="true"></span> after its label'
                )
    return problems


# Words house-style's voice rules name as selling or softening a step, and the
# exit-code label Protostar once used: its codes come from BSD's sysexits.h.
_UNWANTED_WORDS = re.compile(
    r"\b(?:simply|seamless(?:ly)?|effortless(?:ly)?|powerful|leverag(?:e|es|ed|ing)"
    r"|blazing|robust|POSIX[- ](?:exit|status|routing|compliant)\w*)\b",
    re.IGNORECASE,
)


def check_writing_voice() -> list[str]:
    """Prose avoids hype words and em dashes (house-style's voice)."""
    problems: list[str] = []
    for page in _hand_written_pages():
        prose = _prose(page.read_text(encoding="utf-8"))
        for line in prose.splitlines():
            # A table cell holding only a dash marks "not applicable".
            if line.lstrip().startswith("|"):
                line = re.sub(r"\|\s*—\s*(?=\|)", "|", line)
            if "—" in line:
                problems.append(
                    f"{_rel(page)}: an em dash in {line.strip()[:60]!r}. "
                    "Use a comma, a colon, or a new sentence"
                )
            for word in _UNWANTED_WORDS.findall(line):
                problems.append(
                    f"{_rel(page)}: {word!r} in {line.strip()[:60]!r}. "
                    "Say what actually happens instead"
                )
    return problems


def check_site_links() -> list[str]:
    """Links to the published site resolve to a page, and an anchor that exists."""
    config = tomllib.loads((REPO_ROOT / "zensical.toml").read_text(encoding="utf-8"))
    site_url = (config.get("project", config))["site_url"].rstrip("/")
    problems: list[str] = []
    for page in [README, CONTRIBUTING, AGENTS]:
        text = page.read_text(encoding="utf-8")
        for target in sorted(
            set(re.findall(re.escape(site_url) + r"/([^\s)>\"']*)", text))
        ):
            path, _, fragment = target.partition("#")
            if path in PUBLISHED_ELSEWHERE:
                file_path = REPO_ROOT / PUBLISHED_ELSEWHERE[path]
                anchor = fragment or None
            else:
                file_path, anchor = docs_path_to_file(target)
            if not file_path.is_file():
                problems.append(f"{_rel(page)}: {site_url}/{target} has no page")
            elif anchor and anchor not in extract_anchors(file_path):
                problems.append(
                    f"{_rel(page)}: {site_url}/{target} has no such heading"
                )
    return problems


# ── Commands and sample output ───────────────────────────────────────────────

_SHELL_BREAKS = {">", ">>", "2>", "2>&1", "|", "||", "&&", ";"}

# A fixed CLI entry, so the check needs no installed `protostar` on PATH.
_RUN_CLI = (
    "import sys; from protostar.cli import main; sys.argv[0] = 'protostar'; main()"
)


def _documented_commands(text: str) -> Iterator[list[str]]:
    """Yields the arguments of each runnable ``protostar`` command in bash blocks."""
    for block in re.findall(
        r"^[ \t]*```(?:bash|sh|shell|console)\n(.*?)^[ \t]*```",
        text,
        re.DOTALL | re.MULTILINE,
    ):
        for line in re.sub(r"\\\n\s*", " ", block).splitlines():
            try:
                tokens = shlex.split(line.strip().removeprefix("$ "), comments=True)
            except ValueError:
                continue
            if tokens[:2] == ["uv", "run"]:
                tokens = tokens[2:]
            if not tokens or tokens[0] != "protostar":
                continue
            for index, token in enumerate(tokens):
                if token in _SHELL_BREAKS or token.startswith(">"):
                    tokens = tokens[:index]
                    break
            args = tokens[1:]
            # Synopses such as `protostar init [OPTIONS]` show a shape, not a command.
            if args and not any(re.search(r"[\[\]<>{}$]|\.\.\.", arg) for arg in args):
                yield args


def check_execution_order() -> list[str]:
    """The execution-order page names every preparation phase."""
    from protostar.preparation import PreparationPhase

    page = DOCS_DIR / "developer" / "reconciliation" / "execution.md"
    section = _section(page.read_text(encoding="utf-8"), "Execution Order")
    return [
        f"{_rel(page)}: Execution Order doesn't name `{phase.name}`"
        for phase in PreparationPhase
        if f"`{phase.name}`" not in section
    ]


def check_cli_reference_sections() -> list[str]:
    """cli-reference.md has one section per command, each showing its generated options."""
    from protostar.cli.parser import build_parser
    from scripts.generate_docs_assets.cli_tables import command_fixture, subcommands

    text = CLI_REFERENCE.read_text(encoding="utf-8")
    sections = re.findall(
        r"^### ([^\n]*)\n(.*?)(?=^#{2,3} |\Z)", text, re.DOTALL | re.MULTILINE
    )
    commands = subcommands(build_parser())
    problems: list[str] = []
    found: dict[str, str] = {}
    for heading, body in sections:
        for command in re.findall(r"`protostar ([\w-]+)`", heading):
            if command not in commands:
                problems.append(f"{_rel(CLI_REFERENCE)}: '{heading}' names no command")
            elif command in found:
                problems.append(
                    f"{_rel(CLI_REFERENCE)}: 'protostar {command}' has two sections"
                )
            found[command] = body
    for command in commands:
        if command not in found:
            problems.append(
                f"{_rel(CLI_REFERENCE)}: 'protostar {command}' has no section"
            )
        elif f'--8<-- "{command_fixture(command)}"' not in found[command]:
            problems.append(
                f"{_rel(CLI_REFERENCE)}: the 'protostar {command}' section doesn't"
                f" include {command_fixture(command)}"
            )
    return problems


def check_documented_commands() -> list[str]:
    """Every ``protostar`` command a page shows still parses."""
    from protostar.cli.parser import build_parser
    from protostar.errors import InvalidUsageError

    parser = build_parser()
    problems: list[str] = []
    for page in _hand_written_pages():
        seen: set[tuple[str, ...]] = set()
        for args in _documented_commands(page.read_text(encoding="utf-8")):
            if tuple(args) in seen:
                continue
            seen.add(tuple(args))
            error = io.StringIO()
            try:
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(error),
                ):
                    parser.parse_args(args)
            except SystemExit as exit_:
                if exit_.code not in (0, None):
                    reason = error.getvalue().strip().splitlines()
                    problems.append(
                        f"{_rel(page)}: 'protostar {shlex.join(args)}': "
                        f"{reason[-1] if reason else f'exit {exit_.code}'}"
                    )
            except InvalidUsageError as usage:
                problems.append(
                    f"{_rel(page)}: 'protostar {shlex.join(args)}': {usage}"
                )
    return problems


def _option_strings() -> set[str]:
    """Every option any command accepts, such as ``--tier`` and ``--no-ruff``."""
    from protostar.cli.parser import build_parser
    from scripts.generate_docs_assets.cli_tables import subcommands

    parser = build_parser()
    parsers = [parser, *subcommands(parser).values()]
    return {
        flag for each in parsers for a in each._actions for flag in a.option_strings
    }


def _prose(text: str) -> str:
    """Drops fenced blocks, leaving the text a reader reads as prose."""
    return re.sub(r"^[ \t]*```.*?^[ \t]*```", "", text, flags=re.DOTALL | re.MULTILINE)


def check_inline_commands() -> list[str]:
    """Every ``protostar`` command and option a sentence names still exists."""
    from protostar.cli.parser import build_parser
    from protostar.errors import InvalidUsageError

    parser = build_parser()
    options = _option_strings()
    problems: list[str] = []
    for page in _hand_written_pages():
        if page in MAINTAINER_PAGES:
            continue
        prose = _prose(page.read_text(encoding="utf-8"))
        for span in sorted(set(re.findall(r"`([^`\n]+)`", prose))):
            if span.startswith("--"):
                flag = re.split(r"[ =]", span, maxsplit=1)[0]
                if "<" not in flag and flag not in options:
                    problems.append(f"{_rel(page)}: '{span}' is not an option")
                continue
            if not span.startswith("protostar ") or re.search(
                r"[\[\]<>{}$]|\.\.\.", span
            ):
                continue
            args = shlex.split(span)[1:]
            try:
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    parser.parse_args(args)
            except SystemExit as exit_:
                if exit_.code not in (0, None):
                    problems.append(f"{_rel(page)}: '{span}' doesn't parse")
            except InvalidUsageError as usage:
                problems.append(f"{_rel(page)}: '{span}': {usage}")
    return problems


def check_tui_keys() -> list[str]:
    """Every key a page tells the reader to press is one a screen lists under ``?``."""
    from scripts.generate_docs_assets.key_tables import key_tokens, screen_keys

    keys = {
        token
        for rows in screen_keys().values()
        for row_keys, _ in rows
        for token in key_tokens(row_keys)
    }
    problems: list[str] = []
    for page in _hand_written_pages():
        prose = _prose(page.read_text(encoding="utf-8"))
        named = re.findall(r"\(`([A-Za-z])`\)|[Pp]ress `([A-Za-z])`", prose)
        for key in sorted({a or b for a, b in named}):
            if key not in keys:
                problems.append(
                    f"{_rel(page)}: no screen has the key '{key}' (keys are case-sensitive)"
                )
    return problems


def _template_examples() -> Iterator[tuple[Path, str]]:
    """Yields every complete template a page shows: a TOML block with a root ``name``."""
    yield (
        DOCS_DIR / "generated" / "template_schema.toml",
        (DOCS_DIR / "generated" / "template_schema.toml").read_text(encoding="utf-8"),
    )
    for page in _hand_written_pages():
        for block in re.findall(
            r"^([ \t]*)```toml\n(.*?)^\1```",
            page.read_text(encoding="utf-8"),
            re.DOTALL | re.MULTILINE,
        ):
            body = textwrap.dedent(block[1])
            root = re.split(r"^\[", body, maxsplit=1, flags=re.MULTILINE)[0]
            if re.search(r"^name = ", root, re.MULTILINE) and "--8<--" not in body:
                yield page, body


def check_template_examples() -> list[str]:
    """Every complete template a page shows passes ``check-template --strict``."""
    from protostar.template_check import check_template

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        for page, body in _template_examples():
            target = Path(scratch) / "protostar.toml"
            target.write_text(body, encoding="utf-8")
            for finding in check_template(scratch).findings:
                problems.append(f"{_rel(page)}: {finding.rule}: {finding.message}")
    return problems


def check_payload_versions() -> list[str]:
    """JSON a page writes by hand carries the current ``api_version``."""
    from protostar.cli.schema import CLI_API_VERSION

    problems: list[str] = []
    for page in _hand_written_pages():
        text = page.read_text(encoding="utf-8")
        for version in re.findall(r'"api_version":\s*(\d+)', text):
            if int(version) != CLI_API_VERSION:
                problems.append(
                    f"{_rel(page)}: api_version {version}, but the CLI writes {CLI_API_VERSION}"
                )
    return problems


def _walkthrough_steps() -> list[str]:
    """Returns the progress steps a run of Astro's workbench tier prints."""
    from protostar.intent import DependencyGroup

    with tempfile.TemporaryDirectory() as home:
        env = {
            **fixture_environment(),
            "HOME": home,
            "USERPROFILE": home,
            "XDG_CONFIG_HOME": home,
            "PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1",
        }
        result = subprocess.run(
            [
                *(sys.executable, "-c", _RUN_CLI),
                *("init", "--template", "astro", "--tier", "workbench"),
                *("--dry-run", "--json"),
            ],
            cwd=home,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    manifest = json.loads(result.stdout)["manifest"]

    def label(task: dict[str, Any]) -> str:
        return str(task["description"] or f"Running {shlex.join(task['command'])}")

    packages = manifest["dependencies"]
    steps = ["Writing project files"]
    steps += [label(task) for task in manifest["tasks"]["system_tasks"]]
    for group, key in (
        (DependencyGroup.MAIN, "dependencies"),
        (DependencyGroup.DEV, "dev_dependencies"),
        (DependencyGroup.DOCS, "docs_dependencies"),
    ):
        count = len(packages[key])
        if count:
            noun = "dependency" if count == 1 else "dependencies"
            steps.append(f"Installing {count} {group.label} {noun}")
    steps += [label(task) for task in manifest["tasks"]["post_install_tasks"]]
    return steps


# Sample output the walkthrough types by hand: each line must sit in the page,
# and every fragment beside it in the code that prints it.
_WALKTHROUGH_OUTPUT = (
    ("SUCCESS: Project ready.", ("SUCCESS:", "Project ready.")),
    (
        "protostar guide shows how to test, check, and document it.",
        ("shows how to test, check, and document it.",),
    ),
)


def check_walkthrough_output() -> list[str]:
    """first-project.md shows the steps and messages a real run prints."""
    check = "\N{HEAVY CHECK MARK}"
    text = FIRST_PROJECT.read_text(encoding="utf-8")
    problems: list[str] = []

    block = next(
        (
            b
            for b in re.findall(r"```text\n(.*?)```", text, re.DOTALL)
            if "Writing project files" in b
        ),
        None,
    )
    if block is None:
        problems.append(
            f"{_rel(FIRST_PROJECT)}: no step list starting at 'Writing project files'"
        )
    else:
        shown = [
            line.strip().removeprefix(check).strip()
            for line in block.splitlines()
            if check in line
        ]
        expected = _walkthrough_steps()
        if shown != expected:
            problems.append(
                f"{_rel(FIRST_PROJECT)}: the steps differ from a real run "
                "(`init --template astro --tier workbench`). Expected:\n"
                + "\n".join(f"      {check} {step}" for step in expected)
            )

    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "src" / "protostar").rglob("*.py")
    )
    for line, fragments in _WALKTHROUGH_OUTPUT:
        if line not in text:
            problems.append(f"{_rel(FIRST_PROJECT)}: no longer shows '{line}'")
        problems += [
            f"{_rel(FIRST_PROJECT)}: shows '{line}', but no source prints '{fragment}'"
            for fragment in fragments
            if fragment not in sources
        ]
    return problems


def check_project_description() -> list[str]:
    """Public descriptions agree with pyproject.toml's project description."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    description: str = project["project"]["description"]
    site_path = REPO_ROOT / "zensical.toml"
    site = tomllib.loads(site_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if site["project"].get("site_description") != description:
        problems.append(
            f"{_rel(site_path)}: site_description must match "
            "pyproject.toml's project.description"
        )

    expected = {
        README: (f"### {description.removesuffix('.')}",),
        DOCS_DIR / "index.md": (
            f'description: "{description}"',
            re.compile(rf"<h1( [^>]*)?>{re.escape(description)}</h1>"),
        ),
        REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml": (
            f"Protostar is {description[0].lower()}{description[1:]}",
        ),
    }
    for path, fragments in expected.items():
        lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
        for fragment in fragments:
            if isinstance(fragment, re.Pattern):
                found = any(fragment.fullmatch(line) for line in lines)
                shown = fragment.pattern
            else:
                found = fragment in lines
                shown = fragment
            if not found:
                problems.append(
                    f"{_rel(path)}: expected {shown!r} to agree with "
                    "pyproject.toml's project.description"
                )
    return problems


def check_generated_fixtures_are_used() -> list[str]:
    """Every generated fixture and terminal image is used by a page."""
    text = "\n".join(page.read_text(encoding="utf-8") for page in _hand_written_pages())
    problems: list[str] = []
    for folder in (DOCS_DIR / "generated", DOCS_DIR / "assets" / "terminals"):
        for fixture in sorted(folder.iterdir()):
            if fixture.is_file() and fixture.name not in text:
                problems.append(
                    f"{_rel(fixture)}: no page uses it. Stop generating it, or embed it"
                )
    return problems


CHECKS: tuple[Callable[[], list[str]], ...] = (
    check_project_description,
    check_error_tree,
    check_error_sections,
    check_api_reference_errors,
    check_error_names,
    check_exit_code_table,
    check_built_in_templates,
    check_quality_flags,
    check_python_version,
    check_release_pins,
    check_repository_paths,
    check_test_names,
    check_just_recipes,
    check_navigation,
    check_page_front_matter,
    check_card_grids,
    check_link_icons,
    check_writing_voice,
    check_site_links,
    check_cli_reference_sections,
    check_execution_order,
    check_documented_commands,
    check_inline_commands,
    check_tui_keys,
    check_template_examples,
    check_payload_versions,
    check_walkthrough_output,
    check_generated_fixtures_are_used,
)


def main() -> int:
    """Runs every check and prints what each found.

    Returns:
        ``0`` when every page agrees with the code, ``1`` otherwise.
    """
    failed = False
    for check in CHECKS:
        label = (check.__doc__ or check.__name__).splitlines()[0]
        problems = check()
        if problems:
            failed = True
            report(f"  FAIL  {label}", style=OutputStyle.ERROR)
            for problem in problems:
                report(f"       {problem}", style=OutputStyle.DETAIL)
        else:
            report(f"  OK  {label}", style=OutputStyle.DETAIL)
    if failed:
        report(
            "\nDocumentation is out of date. Update the pages above.",
            style=OutputStyle.ERROR,
        )
        return 1
    report("\nDocumentation agrees with the code.", style=OutputStyle.SUCCESS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
