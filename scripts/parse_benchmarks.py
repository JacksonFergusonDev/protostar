"""Parses Hyperfine JSON output into the github-action-benchmark schema."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from protostar.fs import atomic_write_text
from scripts._common import REPO_ROOT


class BenchmarkOutput(TypedDict):
    """Schema for github-action-benchmark JSON format."""

    name: str
    unit: str
    value: float


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Populated namespace containing parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Convert Hyperfine JSON to github-action-benchmark format."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "benchmark.json",
        help="Input Hyperfine JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "benchmark-gh.json",
        help="Output JSON file.",
    )
    parser.add_argument(
        "--gate-mode",
        action="store_true",
        help="Extract only the first result under a generic name for regression testing.",
    )
    args = parser.parse_args()
    if (
        not args.input.is_absolute()
        and not args.input.exists()
        and (REPO_ROOT / args.input).exists()
    ):
        args.input = REPO_ROOT / args.input
    return args


def process_benchmarks(input_file: Path, gate_mode: bool) -> list[BenchmarkOutput]:
    """Process the Hyperfine benchmark results into the target schema.

    Args:
        input_file: Path to the Hyperfine JSON output file.
        gate_mode: If True, returns only the first result mapped to a generic name.

    Returns:
        A list of dictionaries conforming to the github-action-benchmark schema.
    """
    with input_file.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    results: list[dict[str, Any]] = data.get("results", [])
    converted: list[BenchmarkOutput] = []

    if not results:
        return converted

    if gate_mode:
        mean_ms: float = results[0].get("mean", 0.0) * 1000
        converted.append(
            {
                "name": "Protostar Initialization Latency",
                "unit": "ms",
                "value": round(mean_ms, 2),
            }
        )
        return converted

    for result in results:
        mean_ms = result.get("mean", 0.0) * 1000
        command: str = result.get("command", "")

        is_wizard = bool(
            re.search(r"\bPROTOSTAR_BENCHMARK_WIZARD\b", command)
            or re.search(r"\bwizard\b", command, re.IGNORECASE)
        )
        name: str = (
            "Protostar TUI Wizard Latency"
            if is_wizard
            else "Protostar Headless Latency"
        )

        converted.append(
            {
                "name": name,
                "unit": "ms",
                "value": round(mean_ms, 2),
            }
        )

    return converted


def main() -> None:
    """Execute the main script logic."""
    args = parse_args()

    if not args.input.exists():
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        converted_data = process_benchmarks(args.input, args.gate_mode)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    atomic_write_text(args.output, json.dumps(converted_data, indent=2) + "\n")


if __name__ == "__main__":
    main()
