"""Validates that all documentation paths embedded in Protostar errors resolve to real files.

Collects docs_path values from the ProtostarError subclass hierarchy and the CLI module
via introspection, maps each path to its corresponding Markdown source file under docs/,
and reports any broken references.

MkDocs URL mapping convention:
    /en/stable/usage/init/  →  docs/usage/init.md
    /en/stable/getting-started/  →  docs/getting-started.md

Run:
    uv run python scripts/check_doc_links.py
"""

import inspect
import re
import sys
from pathlib import Path

# Resolve the docs/ directory relative to this script's location
REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"


def collect_error_doc_paths() -> dict[str, str]:
    """Introspects the ProtostarError hierarchy to collect all registered docs_path values.

    Reads the docs_path attribute from a sentinel-instantiated instance of each
    concrete subclass, and maps the class name to the path string.

    Returns:
        A dictionary mapping class names to their docs_path values (excluding None).
    """
    from protostar import errors as errors_module
    from protostar.errors import ProtostarError

    results: dict[str, str] = {}

    for name, obj in inspect.getmembers(errors_module, inspect.isclass):
        if not issubclass(obj, ProtostarError) or obj is ProtostarError:
            continue

        try:
            instance = _instantiate_with_sentinels(obj)
        except Exception as exc:
            print(f"  [skip] {name}: could not instantiate for inspection ({exc})")
            continue

        docs_path = getattr(instance, "docs_path", None)
        if docs_path:
            results[name] = docs_path

    return results


def _instantiate_with_sentinels(cls: type) -> object:
    """Attempts to instantiate a ProtostarError subclass using sentinel argument values.

    Inspects the constructor signature and fills required positional parameters
    with typed sentinel values to produce a valid (if meaningless) instance.

    Args:
        cls: The ProtostarError subclass to instantiate.

    Returns:
        A constructed instance of the class.

    Raises:
        TypeError: If the constructor cannot be satisfied with sentinel values.
    """
    sig = inspect.signature(cls.__init__)  # type: ignore[misc]
    kwargs: dict[str, object] = {}

    sentinel_map: dict[type, object] = {
        str: "_sentinel_",
        int: 0,
        float: 0.0,
        bool: False,
        list: [],
        dict: {},
        set: set(),
    }

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        if param.default is not inspect.Parameter.empty:
            continue  # Optional — skip it

        annotation = param.annotation

        # Handle union types (e.g., str | None, Exception | None)
        import types as types_module

        if isinstance(annotation, types_module.UnionType):
            args = [a for a in annotation.__args__ if a is not type(None)]
            annotation = args[0] if args else str

        sentinel = sentinel_map.get(annotation, "_sentinel_")
        kwargs[param_name] = sentinel

    return cls(**kwargs)


def collect_cli_doc_paths() -> dict[str, str]:
    """Collects any standalone docs_path constants declared in the CLI module.

    This is a forward-compatible hook for module-level path constants that may
    accompany argparse error overrides (e.g., ProtostarArgumentParser). Currently
    collects any module-level strings named with an _DOC_PATH suffix.

    Returns:
        A dictionary mapping a human-readable label to the docs_path value.
    """
    try:
        from protostar import cli as cli_module
    except ImportError:
        return {}

    results: dict[str, str] = {}
    for name, value in inspect.getmembers(cli_module):
        if isinstance(value, str) and name.endswith("_DOC_PATH") and value:
            results[f"cli.{name}"] = value

    return results


def slugify(text: str) -> str:
    """Generates a Markdown header slug matching Python-Markdown/MkDocs conventions."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def extract_anchors(file_path: Path) -> set[str]:
    """Extracts all header slugs and HTML anchor IDs from a markdown file."""
    if not file_path.is_file():
        return set()

    content = file_path.read_text(encoding="utf-8")
    anchors: set[str] = set()

    for match in re.finditer(r"^#{1,6}\s+(.+)$", content, re.MULTILINE):
        heading_text = match.group(1).strip()
        heading_clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", heading_text)
        heading_clean = re.sub(r"[`*_~]", "", heading_clean)
        anchors.add(slugify(heading_clean))

    for match in re.finditer(r"""(?:id|name)=["']([^"']+)["']""", content):
        anchors.add(match.group(1))

    return anchors


def docs_path_to_file(docs_path: str) -> tuple[Path, str | None]:
    """Converts a MkDocs-style URL path segment to its Markdown source file and anchor.

    Applies the MkDocs URL routing convention:
        usage/init/                                     →  docs/usage/init.md (no anchor)
        getting-started/                                →  docs/getting-started.md (no anchor)
        usage/troubleshooting/#workspace-collisions     →  docs/usage/troubleshooting.md (anchor: 'workspace-collisions')

    Args:
        docs_path: The path segment after the base URL (e.g. 'usage/init/').

    Returns:
        A tuple of (resolved absolute Path to expected Markdown file, optional anchor).
    """
    path_part, _, anchor = docs_path.partition("#")
    normalized = path_part.strip("/").removesuffix(".html")

    file_path = (
        (DOCS_DIR / "index.md") if not normalized else (DOCS_DIR / f"{normalized}.md")
    )
    return file_path, (anchor if anchor else None)


def main() -> None:
    """Collects all embedded documentation paths and validates each against the filesystem."""
    print("Collecting documentation paths from error hierarchy...")

    all_paths: dict[str, str] = {}
    all_paths.update(collect_error_doc_paths())
    all_paths.update(collect_cli_doc_paths())

    if not all_paths:
        print("No docs_path values found. Nothing to validate.")
        sys.exit(0)

    print(f"Found {len(all_paths)} documentation reference(s):\n")

    broken: list[tuple[str, str, Path, str]] = []
    valid: list[tuple[str, str, Path]] = []

    for label, docs_path in sorted(all_paths.items()):
        resolved_file, anchor = docs_path_to_file(docs_path)
        if not resolved_file.exists():
            broken.append((label, docs_path, resolved_file, "FILE NOT FOUND"))
        elif anchor:
            anchors = extract_anchors(resolved_file)
            if anchor not in anchors:
                broken.append(
                    (label, docs_path, resolved_file, f"ANCHOR '#{anchor}' NOT FOUND")
                )
            else:
                valid.append((label, docs_path, resolved_file))
        else:
            valid.append((label, docs_path, resolved_file))

    for label, docs_path, resolved in valid:
        rel = resolved.relative_to(REPO_ROOT)
        print(f"  \u2713  {label:35s}  {docs_path!r:35s}  \u2192  {rel}")

    if broken:
        print(f"\n{'─' * 80}")
        print(f"BROKEN DOCUMENTATION REFERENCES ({len(broken)}):\n")
        for label, docs_path, resolved, reason in broken:
            rel = resolved.relative_to(REPO_ROOT)
            print(
                f"  \u2717  {label:35s}  {docs_path!r:35s}  \u2192  {rel}  [{reason}]"
            )
        print(
            f"\n{'─' * 80}\n"
            f"{len(broken)} broken reference(s) detected.\n"
            "Update the docs_path value in the corresponding error class, or create the missing file/anchor."
        )
        sys.exit(1)

    print(f"\nAll {len(valid)} documentation reference(s) are valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
