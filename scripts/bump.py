import os
import re
import sys
import tempfile
from pathlib import Path

import tomlkit

SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def atomic_write(path: Path, content: str) -> None:
    """Write file contents atomically via temp file + os.replace."""
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def main() -> None:
    """Safely increments the SemVer project version in pyproject.toml."""
    if len(sys.argv) < 2 or sys.argv[1] not in {"major", "minor", "patch"}:
        print("Usage: bump.py [major|minor|patch]", file=sys.stderr)
        sys.exit(1)

    part = sys.argv[1]
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found.", file=sys.stderr)
        sys.exit(1)

    # 1. Parse structurally (preserves formatting/comments)
    try:
        raw_text = pyproject_path.read_text(encoding="utf-8")
        doc = tomlkit.parse(raw_text)
    except Exception as e:
        print(f"Error parsing pyproject.toml: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Extract and validate node path
    try:
        current_version = doc["project"]["version"]
    except KeyError:
        print(
            "Error: Key [project.version] missing in pyproject.toml",
            file=sys.stderr,
        )
        sys.exit(1)

    # 3. Compute new semantic version (regex handles pre-release/build metadata)
    match = SEMVER_RE.match(str(current_version))
    if not match:
        print(
            f"Error: Current version '{current_version}' is not valid SemVer.",
            file=sys.stderr,
        )
        sys.exit(1)

    major, minor, patch = (
        int(match["major"]),
        int(match["minor"]),
        int(match["patch"]),
    )

    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1

    new_version = f"{major}.{minor}.{patch}"

    # 4. Mutate node and write back atomically
    doc["project"]["version"] = new_version
    try:
        atomic_write(pyproject_path, tomlkit.dumps(doc))
    except Exception as e:
        print(f"Failed to write updated pyproject.toml: {e}", file=sys.stderr)
        sys.exit(1)

    # Output to stdout for pipeline/just capture
    print(new_version)


if __name__ == "__main__":
    main()
