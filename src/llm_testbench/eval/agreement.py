"""Agreement between two annotators on the same items: Cohen's kappa.

"The judge agrees with me 90% of the time" says little: if 90% of the answers are good, a
judge that says "good" to everything agrees 90% of the time and has judged nothing. Kappa
removes the agreement two annotators would reach by chance given how often each says yes:

    kappa = (observed - expected) / (1 - expected)

0 is chance, 1 is perfect agreement. Usual reading (Landis and Koch): above 0.6
substantial, above 0.8 almost perfect; below 0.4 the judge is not measuring what the human
measures. Kappa is fragile when one answer dominates: with 48 "yes" out of 50, two
disagreements move it by tenths. A calibration set needs both answers in fair numbers, and
that is a property to build into it, not to hope for.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class Agreement(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: int
    observed: float
    """Share of the items on which the two annotators give the same label."""
    expected: float
    """Agreement expected by chance from each annotator's own share of "yes"."""
    kappa: float | None
    """``None`` when both annotators give a single label to everything: nothing to measure."""
    both_yes: int
    both_no: int
    first_only: int
    """First annotator says yes, second says no."""
    second_only: int


def cohen_kappa(first: Sequence[bool], second: Sequence[bool]) -> Agreement:
    if len(first) != len(second):
        raise ValueError("both annotators must label the same items")
    if not first:
        raise ValueError("no item to compare")
    total = len(first)
    both_yes = sum(1 for a, b in zip(first, second, strict=True) if a and b)
    both_no = sum(1 for a, b in zip(first, second, strict=True) if not a and not b)
    first_only = sum(1 for a, b in zip(first, second, strict=True) if a and not b)
    second_only = total - both_yes - both_no - first_only
    observed = (both_yes + both_no) / total
    first_yes, second_yes = (both_yes + first_only) / total, (both_yes + second_only) / total
    expected = first_yes * second_yes + (1 - first_yes) * (1 - second_yes)
    kappa = None if expected >= 1.0 else (observed - expected) / (1 - expected)
    return Agreement(
        items=total,
        observed=observed,
        expected=expected,
        kappa=kappa,
        both_yes=both_yes,
        both_no=both_no,
        first_only=first_only,
        second_only=second_only,
    )
