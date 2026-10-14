"""Find the packages a scaffold built from source instead of installing a wheel.

A package whose release has no wheel for the platform builds from its source
distribution, which can make ``protostar init`` take minutes. The template
smoke test runs this after each scaffold. A wheel built locally carries tags
that no wheel ``uv.lock`` records for the package does, so comparing the two
finds every build, whether or not uv's cache already held it. A wheel's own
tags can disagree with its filename (NVIDIA's ``aarch64`` wheels call
themselves ``sbsa``), so a package with no source distribution to build from
is never reported.

Usage: ``python -m scripts.source_builds PROJECT --template NAME`` prints one
JSON line naming the template, the platform, and the packages built, and
prints nothing when there are none. Nightly Report files them as an issue.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote

from scripts.pytest_results import system_name

# Runs under whichever interpreter uv finds, before the project's environment
# exists, so it depends on the standard library alone.

# The project itself, and other local sources, are always built.
LOCAL_SOURCES = frozenset({"editable", "virtual", "directory", "path"})


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _wheel_tags(filename: str) -> set[str]:
    """The tags a wheel's filename covers, with compressed tag sets expanded."""
    python, abi, platform = filename.removesuffix(".whl").split("-")[-3:]
    return {
        "-".join(tag)
        for tag in itertools.product(
            python.split("."), abi.split("."), platform.split(".")
        )
    }


def published_tags(lock: Path) -> dict[tuple[str, str], set[str]]:
    """The tags of every wheel the lockfile records, by package and version.

    Args:
        lock: The project's ``uv.lock``.

    Returns:
        Each package's published tags, keyed by normalized name and version.
        Packages from a local source, and registry packages with no source
        distribution, which can't have been built, are left out.
    """
    packages = tomllib.loads(lock.read_text(encoding="utf-8")).get("package", [])
    return {
        (_normalize(package["name"]), package.get("version", "")): {
            tag
            for wheel in package.get("wheels", [])
            for tag in _wheel_tags(unquote(wheel["url"].rsplit("/", 1)[-1]))
        }
        for package in packages
        if not LOCAL_SOURCES & set(package.get("source", {}))
        and ("sdist" in package or "registry" not in package.get("source", {}))
    }


def source_builds(project: Path) -> list[str]:
    """The packages installed in a project's environment from a local build.

    Args:
        project: A project uv has locked and synced.

    Returns:
        Each package built from source, as ``name==version``, sorted.
    """
    published = published_tags(project / "uv.lock")
    built = []
    for dist_info in sorted((project / ".venv").glob("**/site-packages/*.dist-info")):
        name, _, version = dist_info.name.removesuffix(".dist-info").rpartition("-")
        key = (_normalize(name), version)
        wheel = dist_info / "WHEEL"
        if key not in published or not wheel.is_file():
            continue
        tags = {
            line.removeprefix("Tag:").strip()
            for line in wheel.read_text(encoding="utf-8").splitlines()
            if line.startswith("Tag:")
        }
        if not tags & published[key]:
            built.append(f"{key[0]}=={version}")
    return built


def python_version(project: Path) -> str:
    """The major and minor Python version of the project's environment."""
    for line in (project / ".venv/pyvenv.cfg").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "version_info":
            return ".".join(value.strip().split(".")[:2])
    return "unknown"


def main() -> None:
    """Prints the packages the named scaffold built from source."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path)
    parser.add_argument("--template", required=True)
    args = parser.parse_args()
    built = source_builds(args.project)
    if built:
        platform = f"{system_name()}-py{python_version(args.project)}"
        record = {"template": args.template, "platform": platform, "packages": built}
        print(json.dumps(record))


if __name__ == "__main__":
    main()
