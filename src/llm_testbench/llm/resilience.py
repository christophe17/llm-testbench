"""What absorbs failures: retry with backoff, circuit breaker, timeout (ADR 006).

Three mechanisms, three different questions:

- **retry**: "this attempt failed, can the next one succeed?" — yes for
  a 429, a 5xx, an outage; no for a 400;
- **circuit breaker**: "is this backend going down?" — after N consecutive
  failures, we stop calling it for a while, so as not to worsen its outage nor
  keep our own callers waiting;
- **timeout**: "how long do we accept to wait for an answer?" — a silent
  provider is treated as a failure, not as a wait.

Time and randomness are injected (``clock``, ``sleep``, ``rng``): the tests play
hours in milliseconds, with reproducible delays.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from llm_testbench.llm.errors import (
    CircuitOpenError,
    LLMError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0
    multiplier: float = 2.0
    jitter: float = 0.25
    """Relative jitter (±25%): without it, all clients retry in the same second."""

    def delay_for(self, attempt: int, retry_after_s: float | None, rng: random.Random) -> float:
        """Delay before attempt ``attempt + 1`` (``attempt`` counts from 1).

        A ``Retry-After`` from the provider is honored, capped at ``max_delay_s``: beyond that,
        we prefer to retry early and fail fast rather than block a caller.
        """
        if retry_after_s is not None:
            return min(max(retry_after_s, 0.0), self.max_delay_s)
        raw = self.base_delay_s * self.multiplier ** (attempt - 1)
        capped = min(raw, self.max_delay_s)
        return capped * (1.0 + rng.uniform(-self.jitter, self.jitter))


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Three-state breaker, per backend.

    ``CLOSED``: everything goes through, we count consecutive failures. ``OPEN``: we refuse
    without calling, until ``recovery_timeout_s``. ``HALF_OPEN``: we let one trial call
    through; if it succeeds we close again, if it fails we reopen.

    Only the errors that speak to the backend's health count (unavailable, timeout):
    a 400 is our fault, a 429 is a rate limit, neither one says that
    the backend is going down.
    """

    def __init__(
        self,
        *,
        backend: str,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
        clock: Clock = time.monotonic,
    ) -> None:
        self.backend = backend
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._trial_in_flight = False

    @property
    def state(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and self._clock() - self._opened_at >= self.recovery_timeout_s
        ):
            self._state = CircuitState.HALF_OPEN
            self._trial_in_flight = False
        return self._state

    def before_call(self) -> None:
        state = self.state
        if state is CircuitState.OPEN:
            assert self._opened_at is not None
            remaining = self.recovery_timeout_s - (self._clock() - self._opened_at)
            raise CircuitOpenError(backend=self.backend, retry_in_s=max(remaining, 0.0))
        if state is CircuitState.HALF_OPEN:
            if self._trial_in_flight:
                raise CircuitOpenError(backend=self.backend, retry_in_s=0.0)
            self._trial_in_flight = True

    def record_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None
        self._trial_in_flight = False

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state is CircuitState.HALF_OPEN or (
            self._consecutive_failures >= self.failure_threshold
        ):
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()
            self._trial_in_flight = False

    @staticmethod
    def counts(error: BaseException) -> bool:
        return isinstance(error, ProviderUnavailableError | ProviderTimeoutError)

    def snapshot(self) -> dict[str, str | int]:
        return {
            "backend": self.backend,
            "state": self.state.value,
            "consecutive_failures": self._consecutive_failures,
        }


async def with_timeout[T](awaitable: Awaitable[T], timeout_s: float | None, *, backend: str) -> T:
    """A provider silent beyond ``timeout_s`` is a failure (retryable)."""
    if timeout_s is None:
        return await awaitable
    try:
        async with asyncio.timeout(timeout_s):
            return await awaitable
    except TimeoutError:
        raise ProviderTimeoutError(
            f"no response from {backend!r} in {timeout_s:.1f} s", backend=backend
        ) from None


@dataclass(frozen=True)
class Attempt:
    """What happened at one attempt: raw material for the trace and the notebook."""

    number: int
    error: LLMError | None
    delay_before_next_s: float | None = None


@dataclass
class RetryReport:
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.attempts)


async def retry_call[T](
    fn: Callable[[int], Awaitable[T]],
    *,
    policy: RetryPolicy,
    breaker: CircuitBreaker | None = None,
    sleep: Sleeper = asyncio.sleep,
    rng: random.Random | None = None,
    report: RetryReport | None = None,
) -> T:
    """Calls ``fn(attempt number)`` until success, a non-retryable error, or
    exhaustion of ``policy.max_attempts``. The breaker, if provided, is consulted before
    each attempt and informed after."""
    rng = rng if rng is not None else random.Random()
    report = report if report is not None else RetryReport()
    for attempt in range(1, policy.max_attempts + 1):
        if breaker is not None:
            breaker.before_call()
        try:
            result = await fn(attempt)
        except LLMError as error:
            if breaker is not None and CircuitBreaker.counts(error):
                breaker.record_failure()
            last = attempt == policy.max_attempts
            if not error.retryable or last:
                report.attempts.append(Attempt(number=attempt, error=error))
                raise
            retry_after = getattr(error, "retry_after_s", None)
            delay = policy.delay_for(attempt, retry_after, rng)
            report.attempts.append(Attempt(number=attempt, error=error, delay_before_next_s=delay))
            await sleep(delay)
        else:
            if breaker is not None:
                breaker.record_success()
            report.attempts.append(Attempt(number=attempt, error=None))
            return result
    raise AssertionError("unreachable")  # pragma: no cover
