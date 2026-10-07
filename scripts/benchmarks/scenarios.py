"""The commands whose cost is budgeted and benchmarked.

A scenario is one ``protostar`` command line and the project it starts from.
The budgets run each one with commands faked; the benchmarks run the same
command lines for real.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Start(enum.StrEnum):
    """The project a scenario's command runs in."""

    # An empty directory, as a new project starts.
    EMPTY = "empty"
    # A project the ``lib`` template initialized, with nothing left to update.
    INITIALIZED = "initialized"


@dataclass(frozen=True)
class Scenario:
    """One command line and the project it runs in.

    Attributes:
        name: Names its budget file and its benchmark series.
        argv: The arguments after ``protostar``.
        start: The project the command runs in.
    """

    name: str
    argv: tuple[str, ...]
    start: Start = Start.EMPTY


# The built-in templates, each initialized once: each writes different documents.
TEMPLATES = ("api", "astro", "cli", "lib", "ml")

SCENARIOS: tuple[Scenario, ...] = (
    Scenario("version", ("--version",)),
    Scenario("help-init", ("help", "init")),
    *(
        Scenario(f"init-{template}", ("init", "--json", "--no-config", "-t", template))
        for template in TEMPLATES
    ),
    Scenario(
        "init-dry-run", ("init", "--dry-run", "--json", "--no-config", "-t", "lib")
    ),
    Scenario("sync", ("sync", "--json", "--no-config"), Start.INITIALIZED),
    Scenario(
        "sync-check", ("sync", "--check", "--json", "--no-config"), Start.INITIALIZED
    ),
    Scenario("status", ("status", "--json", "--no-config"), Start.INITIALIZED),
    # Human output loads what the JSON payload never needs, such as Rich's renderers.
    Scenario("status-human", ("status", "--no-config"), Start.INITIALIZED),
    Scenario("diff", ("diff", "--json", "--no-config"), Start.INITIALIZED),
)

BY_NAME = {scenario.name: scenario for scenario in SCENARIOS}
