"""Lightweight argument choices shared by parsing and command presentation."""

from enum import StrEnum


class OutputFormat(StrEnum):
    """How template findings are written for a human or a CI system."""

    TEXT = "text"
    GITHUB = "github"


class Operation(StrEnum):
    """An operation whose implementation is loaded only after dispatch."""

    REVIEW = "review"
    SYNC = "sync"
    GUIDE = "guide"
    EJECT = "eject"
    CHECK_TEMPLATE = "check-template"
