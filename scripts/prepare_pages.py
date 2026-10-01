"""Assemble versioned documentation and root redirects for GitHub Pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "src"))

from protostar.errors import ConfigurationError


@dataclass(frozen=True)
class Version:
    """A published release and its URL aliases."""

    name: str
    aliases: tuple[str, ...]


def read_versions(source: Path) -> tuple[Version, ...]:
    """Read and validate the release registry before assembling any files."""
    try:
        entries = json.loads((source / "versions.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(
            "Cannot read the documentation version registry."
        ) from error
    if not isinstance(entries, list) or not entries:
        raise ConfigurationError(
            "The documentation version registry is empty or invalid."
        )
    versions = []
    names: set[str] = {"benchmarks", "assets"}
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("version"), str)
            or not isinstance(entry.get("aliases"), list)
            or not all(isinstance(alias, str) for alias in entry["aliases"])
        ):
            raise ConfigurationError(
                "Invalid entry in the documentation version registry."
            )
        version = Version(entry["version"], tuple(entry["aliases"]))
        for name in (version.name, *version.aliases):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name in names:
                raise ConfigurationError(
                    f"Invalid or duplicate documentation URL: {name}"
                )
            names.add(name)
        if not (source / version.name / "index.html").is_file():
            raise ConfigurationError(f"Documentation is missing for {version.name}.")
        versions.append(version)
    latest_version(tuple(versions))
    return tuple(versions)


def latest_version(versions: tuple[Version, ...]) -> str:
    """Require exactly one release with the latest alias."""
    latest = [version.name for version in versions if "latest" in version.aliases]
    if len(latest) != 1:
        raise ConfigurationError("Exactly one documentation release must carry latest.")
    return latest[0]


def redirect_html(target: str) -> str:
    """Render a redirect preserving the query and fragment, with a fallback link."""
    escaped = html.escape(target, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Redirecting to Protostar documentation</title>
  <link rel="canonical" href="{escaped}">
  <noscript><meta http-equiv="refresh" content="0; url={escaped}"></noscript>
  <script>window.location.replace({json.dumps(target)} + window.location.search + window.location.hash);</script>
</head>
<body>Redirecting to <a href="{escaped}">Protostar documentation</a>.</body>
</html>
"""


def _write_redirects(source: Path, destination: Path, target_base: str) -> None:
    for page in sorted(source.rglob("*.html")):
        relative = page.relative_to(source)
        if relative == Path("404.html"):
            continue
        route = relative.as_posix()
        if route.endswith("index.html"):
            route = route.removesuffix("index.html")
        target = target_base + quote(route, safe="/")
        output = destination / relative
        if output.exists():
            raise ConfigurationError(
                f"Documentation redirect collides with {relative.as_posix()}."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(redirect_html(target), encoding="utf-8")


def _generate_llms(source: Path, config_path: Path, site_url: str) -> None:
    # Keep this docs-only dependency out of ordinary script imports.
    from llmstxt_standalone.config import Config
    from llmstxt_standalone.config.derive import nav_to_sections
    from llmstxt_standalone.generate import generate_llms_txt

    with config_path.open("rb") as stream:
        project = tomllib.load(stream)["project"]
    nav = project["nav"]
    config = Config(
        site_name=project["site_name"],
        site_description=project["site_description"],
        site_url=site_url.rstrip("/"),
        markdown_description="",
        full_output="llms-full.txt",
        content_selector=None,
        sections=nav_to_sections(nav),
        nav=nav,
    )
    result = generate_llms_txt(config, source)
    if result.skipped or result.warnings:
        raise ConfigurationError(
            "Could not generate all documentation Markdown.",
            hint="Check the latest release's navigation against its published HTML.",
        )
    (source / "llms.txt").write_text(result.llms_txt, encoding="utf-8")
    (source / "llms-full.txt").write_text(result.llms_full_txt, encoding="utf-8")


def assemble_pages(source: Path, output: Path, config_path: Path) -> str:
    """Build a fresh artifact using only registered releases and benchmark data."""
    versions = read_versions(source)
    latest = latest_version(versions)
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ConfigurationError(
            "The Pages output must be a new directory outside its source."
        )
    with config_path.open("rb") as stream:
        site_url = tomllib.load(stream)["project"]["site_url"].rstrip("/") + "/"
    output.mkdir(parents=True)
    for version in versions:
        tree = source / version.name
        if any(path.is_symlink() for path in (tree, *tree.rglob("*"))):
            raise ConfigurationError(
                "Published documentation must not contain symbolic links."
            )
        shutil.copytree(tree, output / version.name)
        for alias in version.aliases:
            _write_redirects(tree, output / alias, f"{site_url}{version.name}/")
    if (source / "benchmarks").is_dir():
        shutil.copytree(source / "benchmarks", output / "benchmarks")
    shutil.copyfile(source / "versions.json", output / "versions.json")
    current = output / latest
    _generate_llms(current, config_path, f"{site_url}{latest}/")
    for filename in ("llms.txt", "llms-full.txt", "sitemap.xml"):
        shutil.copyfile(current / filename, output / filename)
    # The benchmark dashboard links to this root asset.
    favicon = current / "assets" / "favicon.png"
    if favicon.is_file():
        (output / "assets").mkdir(exist_ok=True)
        shutil.copyfile(favicon, output / "assets" / "favicon.png")
    _write_redirects(current, output, f"{site_url}{latest}/")
    (output / ".nojekyll").touch()
    (output / "CNAME").write_text(f"{urlsplit(site_url).hostname}\n", encoding="utf-8")
    (output / "404.html").write_text(
        '<!DOCTYPE html><html lang="en"><meta charset="utf-8">'
        "<title>Page not found</title><h1>Page not found</h1>"
        f'<p><a href="{html.escape(site_url + latest + "/", quote=True)}">'
        "Browse the latest Protostar documentation</a>.</p></html>\n",
        encoding="utf-8",
    )
    return latest


def main() -> None:
    """Print the latest release or assemble a Pages artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--print-latest", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.print_latest:
        print(latest_version(read_versions(args.source)))
    else:
        if args.output is None or args.config is None:
            parser.error("--output and --config are required when assembling Pages")
        latest = assemble_pages(args.source, args.output, args.config)
        print(f"Prepared Pages with {latest} as latest.")


if __name__ == "__main__":
    main()
