"""Renovate configuration target and the locations Renovate reads it from."""

from .locations import DocumentLocations

TARGET = ".github/renovate.json"
# Renovate uses the first configuration file it finds. It parses every name but
# `.json5` as JSON with comments, which Protostar edits; JSON5 it cannot. On
# GitHub, Renovate ignores the `.gitlab/` locations.
LOCATIONS = DocumentLocations(
    TARGET,
    aliases=(
        "renovate.json",
        "renovate.jsonc",
        ".github/renovate.jsonc",
        ".renovaterc",
        ".renovaterc.json",
        ".renovaterc.jsonc",
    ),
    competitors=("renovate.json5", ".github/renovate.json5", ".renovaterc.json5"),
)
