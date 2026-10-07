"""Summaries of benchmark samples, and comparisons between two versions.

A comparison runs both versions in alternating rounds on the same machine, so
whatever slows the machine during a round slows both. Each round gives one
ratio (candidate over baseline), and the comparison is the median ratio with a
95% bootstrap interval over rounds. Only an interval that excludes 1 reads as
faster or slower; anything else is no detectable change, however the medians
differ.
"""

from __future__ import annotations

import enum
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# Resamples for the bootstrap interval; enough that its bounds settle to
# about a tenth of a percent.
RESAMPLES = 2000


class Verdict(enum.StrEnum):
    """What a comparison can say about the candidate."""

    FASTER = "faster"
    SLOWER = "slower"
    UNCHANGED = "no detectable change"


@dataclass(frozen=True)
class Summary:
    """The middle and spread of one version's samples.

    Attributes:
        median: The median sample.
        low: The first quartile.
        high: The third quartile.
        count: How many samples there were.
    """

    median: float
    low: float
    high: float
    count: int


@dataclass(frozen=True)
class Comparison:
    """How a candidate's samples compare with a baseline's, round by round.

    Attributes:
        ratio: The median of candidate over baseline across rounds.
        low: The lower bound of the ratio's 95% interval.
        high: The upper bound of the ratio's 95% interval.
        verdict: Faster or slower only when the interval excludes 1.
    """

    ratio: float
    low: float
    high: float
    verdict: Verdict


def summarize(samples: Sequence[float]) -> Summary:
    """Summarizes one version's samples.

    Args:
        samples: At least one measurement.

    Returns:
        The median and quartiles.
    """
    if len(samples) == 1:
        return Summary(samples[0], samples[0], samples[0], 1)
    low, median, high = statistics.quantiles(samples, n=4, method="inclusive")
    return Summary(median, low, high, len(samples))


def compare(
    baseline: Sequence[float], candidate: Sequence[float], *, seed: int = 0
) -> Comparison:
    """Compares two versions measured in the same alternating rounds.

    Args:
        baseline: One measurement per round of the version compared against.
        candidate: One measurement per round of the version under review,
            in the same order.
        seed: Seeds the bootstrap, so the same samples give the same interval.

    Returns:
        The median ratio, its interval, and what it shows.

    Raises:
        ValueError: If the rounds differ in number, or a baseline is not positive.
    """
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("A comparison needs the same rounds for both versions.")
    if min(baseline) <= 0:
        raise ValueError("A baseline measurement must be positive.")
    ratios = [after / before for before, after in zip(baseline, candidate, strict=True)]
    generator = random.Random(seed)
    medians = sorted(
        statistics.median(generator.choices(ratios, k=len(ratios)))
        for _ in range(RESAMPLES)
    )
    low = medians[int(0.025 * RESAMPLES)]
    high = medians[int(0.975 * RESAMPLES) - 1]
    if low > 1:
        verdict = Verdict.SLOWER
    elif high < 1:
        verdict = Verdict.FASTER
    else:
        verdict = Verdict.UNCHANGED
    return Comparison(statistics.median(ratios), low, high, verdict)
