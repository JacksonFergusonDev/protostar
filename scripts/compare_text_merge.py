"""Compares protostar.text_merge with `git merge-file` on randomized edits.

A development oracle, not a test: tests never run git. Rerun it after changing
the alignment or diff3 code. Expect clean merges to match git byte for byte,
and a fraction of a percent of clean/conflict verdicts to differ where edits sit
among repeated lines, which patience and Myers alignments place differently.

Run:
    uv run python scripts/compare_text_merge.py [--cases N] [--seed S]
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import SNAPSHOTS_DIR, SRC_DIR

sys.path.insert(0, str(SRC_DIR))
from protostar.text_merge import merge_text

REPETITIVE = [f"line {c}\n" for c in "abcdefghij"] + ["\n", "}\n", "    pass\n"]
JUSTFILE = (SNAPSHOTS_DIR / "cli" / "justfile").read_text().splitlines(keepends=True)
# The user's git configuration must not change the oracle's answers.
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def mutate(rng: random.Random, lines: list[str], vocabulary: list[str]) -> list[str]:
    """Applies a few random insertions, replacements, and deletions."""
    out = list(lines)
    for _ in range(rng.randint(0, 4)):
        at = rng.randint(0, len(out))
        operation = rng.choice("iird")
        if operation == "i":
            out[at:at] = [rng.choice(vocabulary).replace("line", "new")]
        elif at < len(out):
            if operation == "r":
                out[at] = rng.choice(vocabulary).replace("line", "changed")
            else:
                del out[at : at + rng.randint(1, 3)]
    return out


def git_merge(directory: Path, base: str, local: str, remote: str) -> str | None:
    """Returns git's merged text, or None when git reports a conflict."""
    paths = [directory / name for name in ("local", "base", "remote")]
    for path, text in zip(paths, (local, base, remote), strict=True):
        path.write_text(text)
    result = subprocess.run(
        ["git", "merge-file", "-p", *map(str, paths)],
        capture_output=True,
        text=True,
        env=GIT_ENV,
        check=False,
    )
    if result.returncode < 0:
        raise SystemExit(f"git merge-file failed: {result.stderr}")
    return result.stdout if result.returncode == 0 else None


def compare(
    name: str,
    cases: int,
    seed: int,
    make_base: Callable[[random.Random], list[str]],
    vocabulary: list[str],
) -> None:
    """Prints how often both engines agree on one corpus."""
    rng = random.Random(seed)
    counts: Counter[str] = Counter()
    with tempfile.TemporaryDirectory() as directory:
        for _ in range(cases):
            base = make_base(rng)
            local, remote = mutate(rng, base, vocabulary), mutate(rng, base, vocabulary)
            texts = ("".join(base), "".join(local), "".join(remote))
            ours = merge_text(*texts).content
            theirs = git_merge(Path(directory), *texts)
            if ours is not None and theirs is not None:
                counts["both clean"] += 1
                counts["both clean, different text"] += ours != theirs
            elif ours is None and theirs is None:
                counts["both conflict"] += 1
            else:
                counts[
                    "only git clean" if ours is None else "only protostar clean"
                ] += 1
    agreed = counts["both clean"] + counts["both conflict"]
    print(f"{name}: {agreed / cases:.2%} same verdict  {dict(counts)}")


def main() -> None:
    """Runs the comparison over short, realistic, and long repetitive texts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    compare(
        "short repetitive",
        args.cases,
        args.seed,
        lambda rng: [rng.choice(REPETITIVE) for _ in range(rng.randint(0, 12))],
        REPETITIVE,
    )
    compare(
        "generated justfile",
        args.cases,
        args.seed,
        lambda _: list(JUSTFILE),
        JUSTFILE + REPETITIVE,
    )
    compare(
        "long repetitive",
        args.cases // 5,
        args.seed,
        lambda rng: [rng.choice(REPETITIVE) for _ in range(rng.randint(50, 300))],
        REPETITIVE,
    )


if __name__ == "__main__":
    main()
