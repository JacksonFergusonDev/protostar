"""Renovate configuration target and the sibling locations that shadow it."""

TARGET = ".github/renovate.json"
# Renovate uses the first configuration it finds, so a sibling location would
# compete with (or shadow) the managed file.
ALTERNATIVES = (
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".renovaterc.json5",
    ".github/renovate.json5",
    ".gitlab/renovate.json",
    ".gitlab/renovate.json5",
)
