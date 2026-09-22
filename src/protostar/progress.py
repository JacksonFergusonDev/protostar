"""Headless progress boundary between execution and its presenter."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

__all__ = ["ProgressStep", "no_progress"]

type ProgressStep = Callable[[str], AbstractContextManager[None]]
"""Brackets one presentable unit of execution work.

The engine enters the returned context around the work and names it with a
present-progressive label (``"Installing 12 development dependencies"``). Only a
fatal failure, one that aborts execution and triggers rollback, raises through the
context; non-fatal outcomes are reported as diagnostics and complete the step. A
presenter may mark a raising step failed but must re-raise.
"""


def no_progress(label: str) -> AbstractContextManager[None]:
    """Ignores execution steps; the default for headless callers.

    Args:
        label: The step's name, unused.

    Returns:
        A context that does nothing.
    """
    return nullcontext()
