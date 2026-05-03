#!/usr/bin/env python3
"""Synchronizes a Homebrew formula with a newly published PyPI release.

This script polls PyPI for visibility of a specific version, extracts the
sdist URL and SHA256 hash, updates the Homebrew formula file, dynamically
generates Python dependency resources using `poet`, and splices those
resources into the formula using specified sentinels.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def get_pypi_metadata(
    package_name: str, version: str, max_retries: int = 60, delay: int = 2
) -> dict[str, Any]:
    """Poll PyPI until the specified package version metadata becomes available.

    Args:
        package_name: The name of the PyPI package.
        version: The exact version string to search for (e.g., '0.7.0').
        max_retries: Maximum number of polling attempts.
        delay: Seconds to wait between polling attempts.

    Raises:
        TimeoutError: If the version does not become visible within the retries.

    Returns:
        The JSON metadata dictionary from PyPI.
    """
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    print(f"Polling {url} for release visibility...")

    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url) as response:
                if response.status == 200:
                    data = response.read().decode("utf-8")
                    return json.loads(data)  # type: ignore[no-any-return]
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"HTTP Error querying PyPI: {e.code}", file=sys.stderr)

        time.sleep(delay)

    raise TimeoutError(f"Timed out waiting for {package_name} {version} on PyPI.")


def extract_sdist_info(metadata: dict[str, Any]) -> tuple[str, str]:
    """Parse the PyPI metadata payload for the source distribution details.

    Args:
        metadata: The JSON response payload from PyPI.

    Raises:
        ValueError: If no sdist package type is found in the distribution URLs.

    Returns:
        A tuple containing the (download_url, sha256_hash).
    """
    for url_info in metadata.get("urls", []):
        if url_info.get("packagetype") == "sdist":
            return str(url_info["url"]), str(url_info["digests"]["sha256"])

    raise ValueError("sdist information not found in PyPI metadata.")


def update_formula_url_sha(formula_path: Path, new_url: str, new_sha: str) -> None:
    """Update the root `url` and `sha256` directives in the Ruby formula.

    Args:
        formula_path: Path to the Homebrew formula file.
        new_url: The new sdist download URL.
        new_sha: The new sdist SHA256 checksum.
    """
    content = formula_path.read_text(encoding="utf-8")

    # Replace root url definition
    content = re.sub(
        r'^\s*url\s+".*"', f'  url "{new_url}"', content, flags=re.MULTILINE
    )
    # Replace root sha256 definition
    content = re.sub(
        r'^\s*sha256\s+".*"', f'  sha256 "{new_sha}"', content, flags=re.MULTILINE
    )

    formula_path.write_text(content, encoding="utf-8")
    print("Updated formula root properties: url and sha256.")


def generate_poet_resources(package_name: str, version: str) -> str:
    """Generate Homebrew resource blocks using an ephemeral `uv` environment.

    Args:
        package_name: The PyPI package name.
        version: The exact version string to generate dependencies for.

    Raises:
        subprocess.CalledProcessError: If the uv run command fails.

    Returns:
        The raw stdout string containing the generated Ruby resource blocks.
    """
    cmd = [
        "uv",
        "run",
        "--with",
        "setuptools<70",
        "--with",
        "homebrew-pypi-poet",
        "--with",
        f"{package_name}=={version}",
        "poet",
        package_name,
    ]

    print("Executing dependency resolution via poet...")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def clean_poet_resources(raw_resources: str, package_name: str) -> str:
    """Filter and reformat the raw poet output for splicing.

    Homebrew audits fail if a dependency resource shares the same name as the
    parent formula. `poet` includes the root package, so it must be excised.

    Args:
        raw_resources: The raw stdout from the `poet` command.
        package_name: The root package name to filter out.

    Returns:
        The cleaned, correctly indented Ruby block string.
    """
    pattern = rf'resource "{package_name}" do.*?end\n*'
    cleaned = re.sub(pattern, "", raw_resources, flags=re.DOTALL)
    cleaned = cleaned.strip()

    if not cleaned:
        return ""

    # Poet outputs flush left; indent by 2 spaces to match Ruby class scope
    return (
        "\n".join(f"  {line}" if line else line for line in cleaned.split("\n")) + "\n"
    )


def splice_resources(formula_path: Path, resources: str) -> None:
    """Inject the generated resource blocks between predefined sentinels.

    Args:
        formula_path: Path to the Homebrew formula file.
        resources: The cleaned Ruby resource block string.

    Raises:
        ValueError: If the necessary sentinels are missing or misordered.
    """
    lines = formula_path.read_text(encoding="utf-8").splitlines()

    start_idx, end_idx = -1, -1
    for i, line in enumerate(lines):
        if line.strip() == "# RESOURCE_BLOCK_START":
            start_idx = i
        elif line.strip() == "# RESOURCE_BLOCK_END":
            end_idx = i

    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        raise ValueError("Could not find valid RESOURCE_BLOCK_START and END sentinels.")

    # Reconstruct lines array, preserving the sentinels themselves
    new_lines = lines[: start_idx + 1]
    if resources:
        new_lines.append(resources.rstrip("\n"))
    new_lines.extend(lines[end_idx:])

    formula_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("Successfully spliced dependency resources into formula.")


def main() -> None:
    """Execute the Homebrew formula synchronization pipeline."""
    parser = argparse.ArgumentParser(
        description="Update Homebrew formula with newly published PyPI releases."
    )
    parser.add_argument("--version", required=True, help="Version tag (e.g., 0.7.0).")
    parser.add_argument(
        "--formula-path",
        type=Path,
        required=True,
        help="Path to the Ruby formula file.",
    )
    parser.add_argument(
        "--package",
        default="protostar",
        help="Target PyPI package name.",
    )
    args = parser.parse_args()

    formula: Path = args.formula_path
    if not formula.exists():
        print(f"Error: Formula file not found at {formula}", file=sys.stderr)
        sys.exit(1)

    try:
        # 1. Wait for registry sync
        metadata = get_pypi_metadata(args.package, args.version)

        # 2. Extract distribution vectors
        new_url, new_sha = extract_sdist_info(metadata)
        print(f"Resolved sdist:\n  URL: {new_url}\n  SHA: {new_sha}")

        # 3. Apply root URL and hash updates
        update_formula_url_sha(formula, new_url, new_sha)

        # 4. Synthesize Python dependency tree via poet
        raw_resources = generate_poet_resources(args.package, args.version)

        # 5. Filter the root package and format ruby blocks
        cleaned_resources = clean_poet_resources(raw_resources, args.package)

        # 6. Splice the resources into the local formula checkout
        splice_resources(formula, cleaned_resources)

    except subprocess.CalledProcessError as e:
        print(f"Error executing subprocess: {e}", file=sys.stderr)
        print(f"Subprocess stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
