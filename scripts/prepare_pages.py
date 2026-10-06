"""Assemble GitHub Pages: the latest release at the bare URLs, each under its version."""

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

METRICS_DIR = _repo_root / "metrics"
METRICS_ASSETS = (
    "index.html",
    "style.css",
    "dashboard.js",
    "metrics.mjs",
    "charts.mjs",
    "mutations.mjs",
    "mutation-dashboard.js",
)
HOUSE_DIR = _repo_root / "docs" / "house"
HEADER_CSS = _repo_root / "docs" / "stylesheets" / "site-header.css"
FOOTER_CSS = _repo_root / "docs" / "stylesheets" / "site-footer.css"
FOOTER_HTML = _repo_root / "overrides" / "partials" / "site-footer.html"
# jacksonferguson.me's policy: search and AI search agents read the docs,
# AI training crawlers don't.
ROBOTS = """\
User-agent: *
Allow: /

User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: Claude-SearchBot
User-agent: Claude-User
User-agent: PerplexityBot
User-agent: Perplexity-User
Allow: /

User-agent: GPTBot
User-agent: ClaudeBot
User-agent: anthropic-ai
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: CCBot
User-agent: meta-externalagent
User-agent: Bytespider
User-agent: cohere-training-data-crawler
Disallow: /

Sitemap: {sitemap}
"""


def render_metrics_index() -> str:
    """Render the dashboard with the docs landing page's shared footer."""
    return (
        (METRICS_DIR / "index.html")
        .read_text(encoding="utf-8")
        .replace("<!-- site-footer -->", FOOTER_HTML.read_text(encoding="utf-8"))
    )


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
    names: set[str] = {"benchmarks", "metrics", "assets"}
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


def redirect_html(target: str, name: str = "Protostar documentation") -> str:
    """Render a redirect preserving the query and fragment, with a fallback link."""
    escaped = html.escape(target, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Redirecting to {name}</title>
  <link rel="canonical" href="{escaped}">
  <noscript><meta http-equiv="refresh" content="0; url={escaped}"></noscript>
  <script>window.location.replace({json.dumps(target)} + window.location.search + window.location.hash);</script>
</head>
<body>Redirecting to <a href="{escaped}">{name}</a>.</body>
</html>
"""


def _route(relative: Path) -> str:
    """The URL path of a published page, relative to its tree."""
    return quote(relative.as_posix().removesuffix("index.html"), safe="/")


def _write_redirects(source: Path, destination: Path, target_base: str) -> None:
    for page in sorted(source.rglob("*.html")):
        relative = page.relative_to(source)
        if relative == Path("404.html"):
            continue
        target = target_base + _route(relative)
        output = destination / relative
        if output.exists():
            raise ConfigurationError(
                f"Documentation redirect collides with {relative.as_posix()}."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(redirect_html(target), encoding="utf-8")


def _point_at_bare_urls(
    tree: Path, version_url: str, site_url: str, latest: Path
) -> None:
    """Make the bare URL canonical for each page the latest release still has.

    A release is built for its versioned URL, so its canonical link, og:url,
    and structured data name that address. Each page the latest release
    still has names its bare URL instead, so search engines rank one address
    across releases; each page it dropped is kept out of search results.
    """
    for page in sorted(tree.rglob("*.html")):
        relative = page.relative_to(tree)
        if relative == Path("404.html"):
            continue
        text = page.read_text(encoding="utf-8")
        if (latest / relative).is_file():
            route = _route(relative)
            text = text.replace(f'"{version_url}{route}"', f'"{site_url}{route}"')
        else:
            text = text.replace(
                "<head>", '<head>\n<meta name="robots" content="noindex">', 1
            )
        page.write_text(text, encoding="utf-8")


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
    """Build a fresh artifact using only registered releases and metrics data."""
    versions = read_versions(source)
    latest = latest_version(versions)
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ConfigurationError(
            "The Pages output must be a new directory outside its source."
        )
    with config_path.open("rb") as stream:
        site_url = tomllib.load(stream)["project"]["site_url"].rstrip("/") + "/"
    current = source / latest
    reserved = {
        *(name for version in versions for name in (version.name, *version.aliases)),
        "benchmarks",
        "metrics",
        "versions.json",
        "robots.txt",
        "CNAME",
        ".nojekyll",
    }
    if collisions := sorted(
        path.name for path in current.iterdir() if path.name in reserved
    ):
        raise ConfigurationError(
            f"The latest documentation collides with {', '.join(collisions)}."
        )
    for version in versions:
        tree = source / version.name
        if any(path.is_symlink() for path in (tree, *tree.rglob("*"))):
            raise ConfigurationError(
                "Published documentation must not contain symbolic links."
            )
    # The latest release is served at the bare URLs; every release keeps its
    # versioned copy, and its aliases redirect to wherever it is served.
    shutil.copytree(current, output)
    _point_at_bare_urls(output, f"{site_url}{latest}/", site_url, current)
    for version in versions:
        tree = source / version.name
        shutil.copytree(tree, output / version.name)
        _point_at_bare_urls(
            output / version.name, f"{site_url}{version.name}/", site_url, current
        )
        target = site_url if version.name == latest else f"{site_url}{version.name}/"
        for alias in version.aliases:
            _write_redirects(tree, output / alias, target)
    metrics_files = [
        source / "metrics" / filename
        for filename in ("data.js", "mutation-history.json", "mutation-latest.json")
        if (source / "metrics" / filename).is_file()
    ]
    if metrics_files:
        metrics_output = output / "metrics"
        metrics_output.mkdir()
        for data in metrics_files:
            shutil.copyfile(data, metrics_output / data.name)
        for filename in METRICS_ASSETS:
            shutil.copyfile(METRICS_DIR / filename, metrics_output / filename)
        (metrics_output / "index.html").write_text(
            render_metrics_index(), encoding="utf-8"
        )
        shutil.copytree(HOUSE_DIR, metrics_output / "house")
        shutil.copyfile(HEADER_CSS, metrics_output / "site-header.css")
        shutil.copyfile(FOOTER_CSS, metrics_output / "site-footer.css")
        # The dashboard's old address, which links outside the repository keep.
        (output / "benchmarks").mkdir()
        (output / "benchmarks" / "index.html").write_text(
            redirect_html(f"{site_url}metrics/", "the Protostar metrics"),
            encoding="utf-8",
        )
        for filename in ("favicon.svg", "favicon.png"):
            shutil.copyfile(
                _repo_root / "docs" / "assets" / filename,
                metrics_output / filename,
            )
    shutil.copyfile(source / "versions.json", output / "versions.json")
    _generate_llms(output, config_path, site_url)
    sitemap = output / "sitemap.xml"
    if sitemap.is_file():
        sitemap.write_text(
            sitemap.read_text(encoding="utf-8").replace(
                f"<loc>{site_url}{latest}/", f"<loc>{site_url}"
            ),
            encoding="utf-8",
        )
    (output / ".nojekyll").touch()
    (output / "robots.txt").write_text(
        ROBOTS.format(sitemap=f"{site_url}sitemap.xml"), encoding="utf-8"
    )
    (output / "CNAME").write_text(f"{urlsplit(site_url).hostname}\n", encoding="utf-8")
    # The theme's 404 page links its assets relative to the root, which breaks
    # at the nested paths GitHub Pages serves it from.
    (output / "404.html").write_text(
        '<!DOCTYPE html><html lang="en"><meta charset="utf-8">'
        "<title>Page not found</title><h1>Page not found</h1>"
        f'<p><a href="{html.escape(site_url, quote=True)}">'
        "Browse the Protostar documentation</a>.</p></html>\n",
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
