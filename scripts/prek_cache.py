"""Keep only the hook environments a smoke run used, and name the cache after them.

The template smoke test caches prek's cloned hook repositories and the
environments built from them, which take most of a smoke job's time to build:
gitleaks and actionlint compile with Go. A run restores the newest cache for its
platform even when a hook has since released, so before saving, this removes
every repository and environment whose revision no scaffold's configuration
names. Without that, each release would add an environment the cache carries
forever.

Usage: ``python -m scripts.prek_cache PREK_HOME CONFIG...`` prunes ``PREK_HOME``
to the remote hooks the configurations name and prints a digest of them, which
keys the saved cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
from collections.abc import Callable
from pathlib import Path

# Protostar writes block-style configurations, each `rev:` under its `repo:`.
_REPO = re.compile(r"^\s*-\s+repo:\s*(\S+)\s*$")
_REV = re.compile(r"^\s*rev:\s*(\S+)\s*$")

Revision = tuple[str, str]


def revisions(config: str) -> set[Revision]:
    """Returns the remote repository and revision of each hook in a configuration.

    Args:
        config: The text of a ``.pre-commit-config.yaml`` Protostar wrote.

    Returns:
        Each ``(url, rev)`` pair the configuration names. ``local`` and
        ``builtin`` repositories have no revision, so they are left out.
    """
    found: set[Revision] = set()
    repo: str | None = None
    for line in config.splitlines():
        if match := _REPO.match(line):
            repo = match[1].strip("\"'")
        elif (match := _REV.match(line)) and repo is not None:
            found.add((repo, match[1].strip("\"'")))
            repo = None
    return found


def _recorded(metadata: Path) -> Revision | None:
    # A clone records {"repo": url, "rev": ...}, an environment
    # {"repo": {"url": ..., "rev": ...}, ...}.
    try:
        recorded = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    repo = recorded.get("repo")
    if isinstance(repo, dict):
        recorded, repo = repo, repo.get("url")
    rev = recorded.get("rev")
    if isinstance(repo, str) and isinstance(rev, str):
        return repo, rev
    return None


def prune(prek_home: Path, wanted: set[Revision]) -> list[Path]:
    """Removes cloned repositories and hook environments no wanted revision uses.

    Args:
        prek_home: prek's home directory.
        wanted: The ``(url, rev)`` pairs to keep.

    Returns:
        The directories removed. One whose metadata can't be read is kept, so
        prek decides about it.
    """
    removed: list[Path] = []
    for directory, metadata in (
        ("repos", ".prek-repo.json"),
        ("hooks", ".prek-hook.json"),
    ):
        root = prek_home / directory
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            revision = _recorded(entry / metadata)
            if revision is not None and revision not in wanted:
                shutil.rmtree(entry, onexc=_writable_retry)
                removed.append(entry)
    return removed


def _writable_retry(
    function: Callable[[str], object], path: str, error: BaseException
) -> None:
    """Clears a read-only bit and retries, which Windows needs to delete it.

    Git writes its pack files read-only, and Windows refuses to delete a
    read-only file.
    """
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def digest(wanted: set[Revision]) -> str:
    """Returns a short, stable digest of a set of revisions.

    Args:
        wanted: The ``(url, rev)`` pairs to name.

    Returns:
        The first 16 hex digits of their sorted list's SHA-256.
    """
    text = "\n".join(f"{repo} {rev}" for repo, rev in sorted(wanted))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def main() -> None:
    """Prunes prek's home to the configurations' hooks and prints their digest."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prek_home", type=Path)
    parser.add_argument("configs", type=Path, nargs="+")
    args = parser.parse_args()
    wanted: set[Revision] = set()
    for config in args.configs:
        wanted |= revisions(config.read_text(encoding="utf-8"))
    prune(args.prek_home, wanted)
    print(digest(wanted))


if __name__ == "__main__":
    main()
