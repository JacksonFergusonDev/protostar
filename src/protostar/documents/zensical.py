"""zensical.toml policy: which settings Protostar manages and when it stays out.

Zensical reads everything under ``[project]``; the rest of the document is the
user's site. Protostar manages only what its module depends on or can extend
without changing the site's behavior. Identity, navigation, look, and the Markdown
extension list are seeded once. The extension list in particular is all or
nothing: a document that lists extensions replaces Zensical's defaults, so adding
entries to a document without the table would disable every other default.
"""

from ..merge import MergePolicy
from ..toml_ast import TomlDocumentSpec
from .locations import DocumentLocations

TARGET = "zensical.toml"
SPEC = TomlDocumentSpec(
    policy=MergePolicy(frozenset({("project", "theme", "features")})),
    seed_paths=frozenset(
        {
            ("project", "site_name"),
            ("project", "site_description"),
            ("project", "nav"),
            ("project", "theme", "palette"),
            ("project", "theme", "font"),
            ("project", "markdown_extensions"),
            ("project", "extra"),
        }
    ),
    # Zensical also accepts settings at the top level, and reads only [project]
    # once that table exists.
    root_table="project",
)
# Zensical also reads an MkDocs configuration, which Protostar does not edit.
LOCATIONS = DocumentLocations(TARGET, competitors=("mkdocs.yml", "mkdocs.yaml"))
