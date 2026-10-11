"""What every published metric shares: its history, its run's identity, and its badge.

The rollback, mutation, and benchmark reports each append runs to a history
file on gh-pages and write a shields.io endpoint. They run on bare runners, so
this module depends on the standard library alone.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_COMMIT = re.compile(r"[0-9a-f]{40}")

# The docs palette: the badge's value in its accent, on the site's ink.
BADGE_COLOR = "22d3ee"
BADGE_LABEL_COLOR = "0A0A0A"


class PublicationError(Exception):
    """A run's identity or history is invalid, so nothing is published."""


def read_history(path: Path) -> list[Any]:
    """Reads the recorded runs, treating a missing history as the first run.

    Raises:
        PublicationError: If the file holds anything but a list of runs.
    """
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise PublicationError(f"{path} is not a list of runs.")
    return entries


def check_commit(commit: str) -> None:
    """Requires a full commit hash, so a history entry names exactly one commit.

    Raises:
        PublicationError: If ``commit`` is not 40 lowercase hex digits.
    """
    if not _COMMIT.fullmatch(commit):
        raise PublicationError("The commit must be a full Git commit hash.")


def utc_date(date: str) -> datetime:
    """Parses a run's date, which must be a UTC timestamp.

    Raises:
        PublicationError: If the date has no offset or a non-zero one.
    """
    when = datetime.fromisoformat(date)
    offset = when.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise PublicationError("The date must be a UTC timestamp.")
    return when


def check_newest(history: list[Any], when: datetime) -> None:
    """Refuses a run older than the latest recorded one, so a retry can't rewind.

    Raises:
        PublicationError: If the history's last run is newer than ``when``.
    """
    if history and datetime.fromisoformat(history[-1]["date"]) > when:
        raise PublicationError(
            "Refusing to publish a run older than the latest recorded run."
        )


def badge(label: str, message: str) -> dict[str, object]:
    """Returns a shields.io endpoint payload in the docs palette."""
    return {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": BADGE_COLOR,
        "labelColor": BADGE_LABEL_COLOR,
    }


def write_json(path: Path, payload: object) -> None:
    """Writes a published file, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
