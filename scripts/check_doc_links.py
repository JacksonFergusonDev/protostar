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


def docs_path_to_file(docs_path: str) -> Path:
    """Converts a MkDocs-style URL path segment to its Markdown source file.

    Applies the MkDocs URL routing convention:
        usage/init/        →  docs/usage/init.md
        getting-started/   →  docs/getting-started.md
        usage/init         →  docs/usage/init.md  (trailing slash optional)

    Args:
        docs_path: The path segment after the base URL (e.g. 'usage/init/').

    Returns:
        The resolved absolute Path to the expected Markdown file.
    """
    # Normalize: strip leading/trailing slashes and any .html extensions
    normalized = docs_path.strip("/").removesuffix(".html")

    if not normalized:
        return DOCS_DIR / "index.md"

    return DOCS_DIR / f"{normalized}.md"


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

    broken: list[tuple[str, str, Path]] = []
    valid: list[tuple[str, str, Path]] = []

    for label, docs_path in sorted(all_paths.items()):
        resolved = docs_path_to_file(docs_path)
        if resolved.exists():
            valid.append((label, docs_path, resolved))
        else:
            broken.append((label, docs_path, resolved))

    for label, docs_path, resolved in valid:
        rel = resolved.relative_to(REPO_ROOT)
        print(f"  \u2713  {label:35s}  {docs_path!r:35s}  \u2192  {rel}")

    if broken:
        print(f"\n{'─' * 80}")
        print(f"BROKEN DOCUMENTATION REFERENCES ({len(broken)}):\n")
        for label, docs_path, resolved in broken:
            rel = resolved.relative_to(REPO_ROOT)
            print(
                f"  \u2717  {label:35s}  {docs_path!r:35s}  \u2192  {rel}  [NOT FOUND]"
            )
        print(
            f"\n{'─' * 80}\n"
            f"{len(broken)} broken reference(s) detected.\n"
            "Update the docs_path value in the corresponding error class, or create the missing file."
        )
        sys.exit(1)

    print(f"\nAll {len(valid)} documentation reference(s) are valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
