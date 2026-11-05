import pytest

from llm_testbench.eval.stats import bootstrap_mean, paired_bootstrap


def test_interval_brackets_the_mean_and_is_reproducible() -> None:
    values = [0.0, 1.0] * 50
    first = bootstrap_mean(values, resamples=2_000, seed=3)
    again = bootstrap_mean(values, resamples=2_000, seed=3)
    assert first == again
    assert first.mean == pytest.approx(0.5)
    assert first.low < 0.5 < first.high
    # Standard error of a mean of 100 coin flips is 0.05: the 95% interval is about ±0.10.
    assert first.high - first.low == pytest.approx(0.20, abs=0.03)


def test_constant_scores_give_a_degenerate_interval() -> None:
    interval = bootstrap_mean([0.7] * 20, resamples=500)
    assert (interval.low, interval.mean, interval.high) == pytest.approx((0.7, 0.7, 0.7))


def test_more_queries_narrow_the_interval() -> None:
    small = bootstrap_mean([0.0, 1.0] * 25, resamples=2_000)
    large = bootstrap_mean([0.0, 1.0] * 400, resamples=2_000)
    assert (large.high - large.low) < (small.high - small.low) / 2


def test_paired_difference_sees_a_gain_that_separate_intervals_hide() -> None:
    # Queries of very different difficulty; the candidate is 0.02 better on each of them.
    baseline = [0.1, 0.9] * 100
    candidate = [score + 0.02 for score in baseline]
    paired = paired_bootstrap(candidate, baseline, resamples=2_000)
    assert paired.mean == pytest.approx(0.02)
    assert paired.significant
    assert paired.share_positive == 1.0
    # The two separate intervals overlap widely: read alone, they would say "no difference".
    assert bootstrap_mean(candidate, resamples=2_000).low < bootstrap_mean(baseline).high


def test_paired_difference_on_noise_is_not_significant() -> None:
    baseline = [0.0, 1.0, 0.0, 1.0] * 25
    candidate = [1.0, 0.0, 0.0, 1.0] * 25
    paired = paired_bootstrap(candidate, baseline, resamples=2_000)
    assert paired.mean == pytest.approx(0.0)
    assert not paired.significant


def test_invalid_inputs_are_refused() -> None:
    with pytest.raises(ValueError, match="no value"):
        bootstrap_mean([])
    with pytest.raises(ValueError, match="same queries"):
        paired_bootstrap([1.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="confidence"):
        bootstrap_mean([1.0], confidence=1.0)
