"""Summarizes mutmut results as a per-module mutation score.

A mutant is a small deliberate bug. The score is the share the test suite
caught (failed or timed out on) out of every mutant the suite had a chance to
catch. Mutants in code no test reaches are reported apart, since no test could
have caught them.

Run:
    uv run python scripts/mutation_report.py report [--json PATH] [--survivors PATH]
    uv run --group mutation python scripts/mutation_report.py diffs [--out PATH]
    uv run python scripts/mutation_report.py combine RESULT.json [RESULT.json ...]
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

# Runs without the project installed (the workflow's combine job), so it
# depends on the standard library alone.
REPO_ROOT = Path(__file__).resolve().parent.parent


class Status(StrEnum):
    """What the suite did with one mutant, from mutmut's worker exit code."""

    KILLED = "killed"
    TIMEOUT = "timeout"
    SURVIVED = "survived"
    SUSPICIOUS = "suspicious"
    NO_TESTS = "no tests"
    SKIPPED = "skipped"
    NOT_CHECKED = "not checked"


# Mirrors mutmut.stats.status_by_exit_code; any other code is suspicious.
_STATUS_BY_EXIT_CODE: dict[int | None, Status] = {
    None: Status.NOT_CHECKED,
    0: Status.SURVIVED,
    1: Status.KILLED,
    3: Status.KILLED,
    5: Status.NO_TESTS,
    33: Status.NO_TESTS,
    34: Status.SKIPPED,
    36: Status.TIMEOUT,
    24: Status.TIMEOUT,
    -24: Status.TIMEOUT,
    152: Status.TIMEOUT,
    255: Status.TIMEOUT,
}

_CAUGHT = (Status.KILLED, Status.TIMEOUT)
_DECIDED = (*_CAUGHT, Status.SURVIVED, Status.SUSPICIOUS)


@dataclass(frozen=True)
class ModuleResult:
    """Mutation outcome counts for one source module."""

    module: str
    killed: int = 0
    timeout: int = 0
    survived: int = 0
    suspicious: int = 0
    no_tests: int = 0

    @property
    def caught(self) -> int:
        """Mutants the suite detected."""
        return self.killed + self.timeout

    @property
    def decided(self) -> int:
        """Mutants the suite had a chance to detect."""
        return self.caught + self.survived + self.suspicious

    @property
    def score(self) -> float | None:
        """Share of decided mutants the suite caught, or None when none ran."""
        return self.caught / self.decided if self.decided else None


def load_module_results(
    mutants_dir: Path,
) -> tuple[list[ModuleResult], dict[str, list[str]]]:
    """Reads every ``.meta`` file mutmut wrote.

    Args:
        mutants_dir: The ``mutants`` directory of a finished run.

    Returns:
        The results of each module that had a mutant checked, and the names of
        its surviving mutants keyed by module.
    """
    results: list[ModuleResult] = []
    survivors: dict[str, list[str]] = {}
    for meta in sorted(mutants_dir.rglob("*.py.meta")):
        exit_codes: dict[str, int | None] = json.loads(
            meta.read_text(encoding="utf-8")
        )["exit_code_by_key"]
        counts: Counter[Status] = Counter()
        module = meta.name.removesuffix(".py.meta")
        for name, code in sorted(exit_codes.items()):
            status = _STATUS_BY_EXIT_CODE.get(code, Status.SUSPICIOUS)
            counts[status] += 1
            if status is Status.SURVIVED:
                survivors.setdefault(module, []).append(name)
        if sum(counts[status] for status in (*_DECIDED, Status.NO_TESTS)) == 0:
            continue
        results.append(
            ModuleResult(
                module=module,
                killed=counts[Status.KILLED],
                timeout=counts[Status.TIMEOUT],
                survived=counts[Status.SURVIVED],
                suspicious=counts[Status.SUSPICIOUS],
                no_tests=counts[Status.NO_TESTS],
            )
        )
    return results, survivors


# `protostar.journal.xǁMutationJournalǁrecord_mutation__mutmut_12` is a method;
# `protostar.merge.x_hold__mutmut_17` is a module-level function (one leading
# underscore is mutmut's own).
_MUTANT_NAME = re.compile(
    r"^[\w.]+?\.x(?:ǁ(?P<cls>\w+)ǁ(?P<method>\w+)|_(?P<func>\w+))__mutmut_\d+$"
)


def function_of(mutant: str) -> str:
    """Names the function a mutant was made in, as ``Class.method`` or ``func``.

    Args:
        mutant: A mutmut mutant name.

    Returns:
        The readable function name, or the mutant name if it has an unknown shape.
    """
    match = _MUTANT_NAME.match(mutant)
    if match is None:
        return mutant
    if match["cls"]:
        return f"{match['cls']}.{match['method']}"
    return str(match["func"])


def render_hotspots(survivors: dict[str, list[str]], limit: int = 8) -> str:
    """Renders the functions with the most surviving mutants.

    Args:
        survivors: Surviving mutant names keyed by module.
        limit: How many functions to list.

    Returns:
        A Markdown table, or an empty string when nothing survived.
    """
    counts = Counter(
        (module, function_of(name))
        for module, names in survivors.items()
        for name in names
    )
    if not counts:
        return ""
    lines = [
        "",
        "Where the survivors are (fix these first):",
        "",
        "| Module | Function | Survivors |",
        "| --- | --- | ---: |",
    ]
    lines += [
        f"| {module} | `{function}` | {count} |"
        for (module, function), count in counts.most_common(limit)
    ]
    return "\n".join(lines) + "\n"


def render_markdown(results: list[ModuleResult]) -> str:
    """Renders results as a Markdown table with a total row.

    Args:
        results: Per-module results.

    Returns:
        The table, ending in a newline.
    """
    total = ModuleResult(
        module="**total**",
        killed=sum(r.killed for r in results),
        timeout=sum(r.timeout for r in results),
        survived=sum(r.survived for r in results),
        suspicious=sum(r.suspicious for r in results),
        no_tests=sum(r.no_tests for r in results),
    )
    lines = [
        "| Module | Score | Caught | Survived | Suspicious | Not reached by tests |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in (*results, total):
        score = "n/a" if row.score is None else f"{row.score:.1%}"
        lines.append(
            f"| {row.module} | {score} | {row.caught} / {row.decided} | "
            f"{row.survived} | {row.suspicious} | {row.no_tests} |"
        )
    return "\n".join(lines) + "\n"


def _report(args: argparse.Namespace) -> None:
    results, survivors = load_module_results(args.mutants)
    if not results:
        raise SystemExit(f"No mutation results found under {args.mutants}.")
    sys.stdout.write(render_markdown(results))
    sys.stdout.write(render_hotspots(survivors))
    if args.json:
        args.json.write_text(
            json.dumps([asdict(result) for result in results], indent=2) + "\n",
            encoding="utf-8",
        )
    if args.survivors:
        args.survivors.write_text(
            "".join(f"{name}\n" for names in survivors.values() for name in names),
            encoding="utf-8",
        )


def render_diffs(mutants_dir: Path) -> str:
    """Renders every surviving mutant's change, grouped by function.

    Needs mutmut installed and the working directory to be the repository root
    the run happened in, because mutmut reads its generated copy from there.

    Args:
        mutants_dir: The ``mutants`` directory of a finished run.

    Returns:
        A Markdown report, ending in a newline.
    """
    diff_apply = importlib.import_module("mutmut.mutation.diff_apply")
    by_function: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for meta in sorted(mutants_dir.rglob("*.py.meta")):
        source = meta.relative_to(mutants_dir).with_suffix("")
        exit_codes: dict[str, int | None] = json.loads(
            meta.read_text(encoding="utf-8")
        )["exit_code_by_key"]
        for name, code in sorted(exit_codes.items()):
            if _STATUS_BY_EXIT_CODE.get(code) is Status.SURVIVED:
                diff = diff_apply.get_diff_for_mutant(name, path=source)
                key = (source.stem, function_of(name))
                by_function.setdefault(key, []).append((name, diff))
    total = sum(len(mutants) for mutants in by_function.values())
    lines = [
        f"# Surviving mutants ({total})",
        "",
        "Each one is a deliberate bug the tests did not catch. Read the change,",
        "then write a test that fails when it is made. If no test could tell the",
        "two apart (an equivalent mutant), leave it.",
        "",
    ]
    for (module, function), mutants in sorted(
        by_function.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        lines += [f"## `{module}`: `{function}` ({len(mutants)})", ""]
        for name, diff in mutants:
            body = "\n".join(
                line
                for line in diff.splitlines()
                if not line.startswith(("---", "+++"))
            )
            lines += [f"`{name.rpartition('.')[2]}`", "", "```diff", body, "```", ""]
    return "\n".join(lines)


def _diffs(args: argparse.Namespace) -> None:
    report = render_diffs(args.mutants)
    args.out.write_text(report, encoding="utf-8")
    sys.stdout.write(f"Wrote {args.out}\n")


def combine_results(paths: list[Path]) -> list[ModuleResult]:
    """Merges several ``--json`` results into one row per module.

    A module split across runners writes one file per shard, each counting only
    the mutants that shard ran, so the counts add up.

    Args:
        paths: JSON files written by ``report --json``.

    Returns:
        One result per module, sorted by module name.
    """
    totals: dict[str, ModuleResult] = {}
    for path in paths:
        for row in json.loads(path.read_text(encoding="utf-8")):
            result = ModuleResult(**row)
            seen = totals.get(result.module)
            totals[result.module] = (
                result
                if seen is None
                else ModuleResult(
                    module=result.module,
                    killed=seen.killed + result.killed,
                    timeout=seen.timeout + result.timeout,
                    survived=seen.survived + result.survived,
                    suspicious=seen.suspicious + result.suspicious,
                    no_tests=seen.no_tests + result.no_tests,
                )
            )
    return sorted(totals.values(), key=lambda r: r.module)


def _combine(args: argparse.Namespace) -> None:
    sys.stdout.write(render_markdown(combine_results(args.results)))


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments.

    Returns:
        The populated namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    report = commands.add_parser("report", help="Summarize a finished mutmut run.")
    report.add_argument("--mutants", type=Path, default=REPO_ROOT / "mutants")
    report.add_argument("--json", type=Path, help="Write the results as JSON.")
    report.add_argument(
        "--survivors", type=Path, help="Write each surviving mutant's name."
    )
    report.set_defaults(func=_report)

    diffs = commands.add_parser(
        "diffs", help="Write each surviving mutant's change (needs mutmut)."
    )
    diffs.add_argument("--mutants", type=Path, default=REPO_ROOT / "mutants")
    diffs.add_argument("--out", type=Path, default=REPO_ROOT / "mutants/survivors.md")
    diffs.set_defaults(func=_diffs)

    combine = commands.add_parser("combine", help="Merge several --json results.")
    combine.add_argument("results", type=Path, nargs="+")
    combine.set_defaults(func=_combine)
    return parser.parse_args()


def main() -> None:
    """Runs the selected command."""
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
