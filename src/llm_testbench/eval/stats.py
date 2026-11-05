"""Bootstrap confidence intervals: how much of a score is the luck of the query sample.

A benchmark score is a mean over a few hundred queries (SciFact: 300). Another sample of
300 queries from the same population would give another mean; the bootstrap estimates by
how much, without any assumption on the distribution: draw the queries again **with
replacement**, recompute the mean, repeat, and read the spread of those means.

Two uses, and the second is the one that matters from phase 3 on:

- :func:`bootstrap_mean`: the interval around one system's score;
- :func:`paired_bootstrap`: the interval around the **difference** between two systems
  measured on the same queries. Resampling the per-query differences keeps the pairing: a
  hard query is hard for both systems, and that shared difficulty cancels out. Comparing two
  separate intervals instead throws the pairing away and hides real gains.

The generator of random numbers is seeded: the same scores give the same interval, in CI as
on a laptop.
"""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

DEFAULT_RESAMPLES = 10_000
_BLOCK = 1_000  # resamples drawn at once: bounds the memory on large query sets


class Interval(BaseModel):
    model_config = ConfigDict(frozen=True)

    mean: float
    low: float
    high: float
    confidence: float
    resamples: int


class PairedDifference(BaseModel):
    """Candidate minus baseline, per query, averaged."""

    model_config = ConfigDict(frozen=True)

    mean: float
    low: float
    high: float
    confidence: float
    resamples: int
    share_positive: float
    """Share of the resamples where the candidate beats the baseline."""

    @property
    def significant(self) -> bool:
        """The interval excludes zero: the sign of the difference survives resampling."""
        return self.low > 0.0 or self.high < 0.0


def _resampled_means(values: np.ndarray, resamples: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    size = len(values)
    means = np.empty(resamples, dtype=np.float64)
    for start in range(0, resamples, _BLOCK):
        count = min(_BLOCK, resamples - start)
        draws = rng.integers(0, size, size=(count, size))
        means[start : start + count] = values[draws].mean(axis=1)
    return means


def _bounds(means: np.ndarray, confidence: float) -> tuple[float, float]:
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return float(low), float(high)


def _check(confidence: float, resamples: int) -> None:
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")
    if resamples < 1:
        raise ValueError("resamples must be at least 1")


def bootstrap_mean(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> Interval:
    """Percentile bootstrap interval of the mean of per-query scores."""
    _check(confidence, resamples)
    if len(values) == 0:
        raise ValueError("no value to resample")
    array = np.asarray(values, dtype=np.float64)
    low, high = _bounds(_resampled_means(array, resamples, seed), confidence)
    return Interval(
        mean=float(array.mean()), low=low, high=high, confidence=confidence, resamples=resamples
    )


def paired_bootstrap(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> PairedDifference:
    """Interval of the mean per-query difference; both sequences in the same query order."""
    _check(confidence, resamples)
    if len(candidate) != len(baseline):
        raise ValueError("paired comparison needs the same queries on both sides")
    if len(candidate) == 0:
        raise ValueError("no value to resample")
    differences = np.asarray(candidate, dtype=np.float64) - np.asarray(baseline, dtype=np.float64)
    means = _resampled_means(differences, resamples, seed)
    low, high = _bounds(means, confidence)
    return PairedDifference(
        mean=float(differences.mean()),
        low=low,
        high=high,
        confidence=confidence,
        resamples=resamples,
        share_positive=float((means > 0.0).mean()),
    )
