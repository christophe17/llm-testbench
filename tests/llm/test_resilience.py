import asyncio
import random

import pytest

from llm_testbench.llm.errors import (
    CircuitOpenError,
    InvalidRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from llm_testbench.llm.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    RetryReport,
    retry_call,
    with_timeout,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


class FakeSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


# ------------------------------------------------------------------ RetryPolicy


def test_backoff_grows_then_caps_and_jitter_is_bounded() -> None:
    policy = RetryPolicy(base_delay_s=1.0, max_delay_s=5.0, multiplier=2.0, jitter=0.25)
    rng = random.Random(0)
    delays = [policy.delay_for(attempt, None, rng) for attempt in (1, 2, 3, 4)]
    assert 0.75 <= delays[0] <= 1.25
    assert 1.5 <= delays[1] <= 2.5
    assert 3.0 <= delays[2] <= 5.0
    assert 3.75 <= delays[3] <= 6.25  # 8 s brut, plafonné à 5 s avant la gigue


def test_retry_after_from_provider_is_honoured_but_capped() -> None:
    policy = RetryPolicy(max_delay_s=8.0)
    rng = random.Random(0)
    assert policy.delay_for(1, 3.0, rng) == 3.0
    assert policy.delay_for(1, 60.0, rng) == 8.0


# ------------------------------------------------------------------ retry_call


async def test_retryable_errors_are_retried_then_the_last_one_is_raised() -> None:
    calls: list[int] = []

    async def always_down(attempt: int) -> str:
        calls.append(attempt)
        raise ProviderUnavailableError("503", backend="b", status_code=503)

    sleep = FakeSleep()
    report = RetryReport()
    with pytest.raises(ProviderUnavailableError):
        await retry_call(
            always_down,
            policy=RetryPolicy(max_attempts=3, base_delay_s=0.1, jitter=0.0),
            sleep=sleep,
            rng=random.Random(0),
            report=report,
        )
    assert calls == [1, 2, 3]
    assert sleep.delays == [0.1, 0.2]
    assert [a.error is not None for a in report.attempts] == [True, True, True]


async def test_non_retryable_error_fails_immediately() -> None:
    calls: list[int] = []

    async def bad_request(attempt: int) -> str:
        calls.append(attempt)
        raise InvalidRequestError("400", backend="b", status_code=400)

    sleep = FakeSleep()
    with pytest.raises(InvalidRequestError):
        await retry_call(bad_request, policy=RetryPolicy(max_attempts=5), sleep=sleep)
    assert calls == [1]
    assert sleep.delays == []


async def test_success_after_a_rate_limit_uses_retry_after() -> None:
    async def flaky(attempt: int) -> str:
        if attempt == 1:
            raise RateLimitedError("429", backend="b", retry_after_s=2.5)
        return "ok"

    sleep = FakeSleep()
    report = RetryReport()
    result = await retry_call(flaky, policy=RetryPolicy(), sleep=sleep, report=report)
    assert result == "ok"
    assert sleep.delays == [2.5]
    assert report.count == 2
    assert report.attempts[0].delay_before_next_s == 2.5


# ------------------------------------------------------------------ CircuitBreaker


def test_breaker_opens_after_threshold_and_half_opens_after_timeout() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(backend="b", failure_threshold=2, recovery_timeout_s=30, clock=clock)
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    breaker.before_call()  # encore fermé
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError) as info:
        breaker.before_call()
    assert info.value.retry_in_s == pytest.approx(30.0)

    clock.now += 31
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.before_call()  # l'appel d'essai passe…
    with pytest.raises(CircuitOpenError):
        breaker.before_call()  # …mais un seul à la fois
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.snapshot()["consecutive_failures"] == 0


def test_failure_during_half_open_reopens() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(backend="b", failure_threshold=1, recovery_timeout_s=10, clock=clock)
    breaker.record_failure()
    clock.now += 10
    breaker.before_call()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError) as info:
        breaker.before_call()
    assert info.value.retry_in_s == pytest.approx(10.0)


def test_only_backend_health_errors_count_for_the_breaker() -> None:
    assert CircuitBreaker.counts(ProviderUnavailableError("x", backend="b"))
    assert CircuitBreaker.counts(ProviderTimeoutError("x", backend="b"))
    assert not CircuitBreaker.counts(RateLimitedError("x", backend="b"))
    assert not CircuitBreaker.counts(InvalidRequestError("x", backend="b"))


async def test_retry_call_stops_calling_when_the_circuit_opens() -> None:
    calls: list[int] = []

    async def down(attempt: int) -> str:
        calls.append(attempt)
        raise ProviderUnavailableError("503", backend="b", status_code=503)

    breaker = CircuitBreaker(backend="b", failure_threshold=2, recovery_timeout_s=60)
    with pytest.raises(CircuitOpenError):
        await retry_call(
            down,
            policy=RetryPolicy(max_attempts=5, base_delay_s=0.0, jitter=0.0),
            breaker=breaker,
            sleep=FakeSleep(),
        )
    assert calls == [1, 2]
    assert breaker.state is CircuitState.OPEN


# ------------------------------------------------------------------ with_timeout


async def test_timeout_becomes_a_retryable_provider_error() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.2)
        return "late"

    with pytest.raises(ProviderTimeoutError, match=r"0\.0 s") as info:
        await with_timeout(slow(), 0.01, backend="b")
    assert info.value.retryable

    async def fast() -> str:
        return "ok"

    assert await with_timeout(fast(), None, backend="b") == "ok"
