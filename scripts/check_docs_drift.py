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
import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import DOCS_DIR, REPO_ROOT
from scripts.check_doc_links import docs_path_to_file, extract_anchors

FIRST_PROJECT = DOCS_DIR / "first-project.md"
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
    *sorted((DOCS_DIR / "developer").glob("*.md")),
)

# Pages the site publishes from outside docs/, so no Markdown file backs them.
PUBLISHED_ELSEWHERE = frozenset({"benchmarks/"})

# Written on purpose without a page in the navigation.
UNLISTED_PAGES = frozenset({"development/semantic-reconciliation.md"})

# Paths a maintainer page shows as examples of the pattern, not as files.
PLACEHOLDER_PATHS = frozenset({"tests/path/to/test.py", "tests/test_foo.py"})

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


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


def _number(token: str) -> int | None:
    return int(token) if token.isdigit() else NUMBER_WORDS.get(token.lower())


def check_built_in_templates() -> list[str]:
    """built-in-templates.md names exactly the templates that ship."""
    from protostar.templates.discovery import builtin_template_aliases

    shipped = set(builtin_template_aliases())
    text = BUILT_IN_TEMPLATES.read_text(encoding="utf-8")
    match = re.search(r"ships (\w+) built-in templates: ([^.]+)\.", text)
    if match is None:
        return [
            f"{_rel(BUILT_IN_TEMPLATES)}: no 'ships N built-in templates: ...' sentence"
        ]
    named = set(re.findall(r"`([\w-]+)`", match.group(2)))
    problems: list[str] = []
    if named != shipped:
        problems.append(
            f"{_rel(BUILT_IN_TEMPLATES)}: names {sorted(named)}, but {sorted(shipped)} ship"
        )
    if _number(match.group(1)) != len(shipped):
        problems.append(
            f"{_rel(BUILT_IN_TEMPLATES)}: says '{match.group(1)}' templates, but {len(shipped)} ship"
        )
    return problems


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
    """Pages that count or list the built-in quality flags agree with the contract test."""
    flags = _contract_quality_flags()
    problems: list[str] = []
    for page in (CONTRIBUTING, BUILT_IN_TEMPLATES):
        text = page.read_text(encoding="utf-8")
        for count in re.findall(r"\b(\w+) quality flags", text):
            if _number(count) != len(flags):
                problems.append(
                    f"{_rel(page)}: says '{count} quality flags', but the contract has {len(flags)}"
                )
    contributing = CONTRIBUTING.read_text(encoding="utf-8")
    listed = re.search(r"quality flags explicitly\*\* \(([^)]+)\)", contributing)
    if listed and tuple(re.findall(r"`(\w+)`", listed.group(1))) != flags:
        problems.append(
            f"{_rel(CONTRIBUTING)}: lists {re.findall(r'`(\w+)`', listed.group(1))}, "
            f"but the contract has {list(flags)}"
        )
    return problems


def check_python_version() -> list[str]:
    """The README badge and CONTRIBUTING name the minimum Python in pyproject.toml."""
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    minimum = re.sub(r"[^\d.]", "", pyproject["project"]["requires-python"])
    problems: list[str] = []
    claims = (
        (README, r"badge/python-([\d.]+)\+"),
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
        for page in sorted(on_disk - in_nav - UNLISTED_PAGES)
    ]
    problems += [
        f"zensical.toml: nav entry '{page}' has no file"
        for page in sorted(in_nav - on_disk)
    ]
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
            if target in PUBLISHED_ELSEWHERE:
                continue
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


def _walkthrough_steps() -> list[str]:
    """Returns the progress steps a run of Astro's workbench tier prints."""
    from protostar.intent import DependencyGroup

    with tempfile.TemporaryDirectory() as home:
        env = {
            **os.environ,
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


CHECKS: tuple[Callable[[], list[str]], ...] = (
    check_error_tree,
    check_error_sections,
    check_api_reference_errors,
    check_exit_code_table,
    check_built_in_templates,
    check_quality_flags,
    check_python_version,
    check_repository_paths,
    check_test_names,
    check_just_recipes,
    check_navigation,
    check_site_links,
    check_documented_commands,
    check_walkthrough_output,
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
            print(f"  ✗  {label}")
            for problem in problems:
                print(f"       {problem}")
        else:
            print(f"  ✓  {label}")
    if failed:
        print("\nDocumentation is out of date. Update the pages above.")
        return 1
    print("\nDocumentation agrees with the code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
