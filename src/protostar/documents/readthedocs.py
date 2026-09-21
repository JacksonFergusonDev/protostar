""".readthedocs.yaml policy: one generated build, never grafted onto another build.

Protostar's build jobs replace the steps Read the Docs would otherwise run: each
of ``create_environment``, ``install``, and ``build.html`` skips the default step
that the ``sphinx``, ``mkdocs``, ``python``, and ``conda`` settings configure.
Read the Docs also rejects ``build.jobs`` next to ``build.commands``. A
configuration that already builds either way keeps its build.
"""

from ..merge import (
    ConflictReason,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Value,
    lookup,
    semantic_equal,
)
from ..yaml_ast import NO_GUARD, YamlDocumentSpec, YamlGuard

TARGET = ".readthedocs.yaml"
SPEC = YamlDocumentSpec(
    "Read the Docs",
    # The configuration is the module's complete output, so a setting it stops
    # generating is retracted instead of lingering to override the build.
    policy=MergePolicy(complete=True),
    # Read the Docs reads the first file matching `^\.?readthedocs.ya?ml$` in
    # directory-listing order, so a sibling would compete with the managed file.
    displaces=(".readthedocs.yml", "readthedocs.yaml", "readthedocs.yml"),
)
JOBS = ("build", "jobs")
# Top-level settings that configure the default steps Protostar's jobs replace.
_DEFAULT_STEP_SETTINGS = ("sphinx", "mkdocs", "python", "conda")


def guard_build(desired: Value, local: Value, base: Value) -> YamlGuard:
    """Holds ``build.jobs`` when the local configuration builds another way.

    A configuration builds another way when a non-empty ``build.commands``
    replaces every step, or when a ``sphinx``, ``mkdocs``, ``python``, or
    ``conda`` setting configures the default steps. The hold applies under
    explicit overwrite too. It is reported as ``unowned`` only when it withholds
    a change, so a user who took over the build after Protostar wrote its jobs is
    not warned until Protostar's jobs change.

    Args:
        desired: Decoded generated configuration.
        local: Decoded workspace configuration, empty when the file is absent.
        base: Previously owned baseline, or ``MISSING``.

    Returns:
        The hold on ``build.jobs`` and its conflict, or no guard.
    """
    commands = lookup(local, ("build", "commands"))
    replaced = isinstance(commands, list) and bool(commands)
    configured = isinstance(local, dict) and any(
        setting in local for setting in _DEFAULT_STEP_SETTINGS
    )
    if not (replaced or configured):
        return NO_GUARD
    wanted = lookup(desired, JOBS)
    withheld = not semantic_equal(wanted, lookup(base, JOBS)) and not semantic_equal(
        wanted, lookup(local, JOBS)
    )
    conflict = MergeConflict(MergeLocation(TARGET, JOBS), ConflictReason.UNOWNED)
    return YamlGuard((JOBS,), (conflict,) if withheld else ())
