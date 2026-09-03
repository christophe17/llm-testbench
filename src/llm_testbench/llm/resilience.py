"""Ce qui encaisse les pannes : retry avec backoff, circuit breaker, délai (ADR 006).

Trois mécanismes, trois questions différentes :

- **retry** : « cette tentative a échoué, est-ce que la suivante peut réussir ? » — oui pour
  un 429, un 5xx, une coupure ; non pour un 400 ;
- **circuit breaker** : « ce backend est-il en train de tomber ? » — après N échecs
  consécutifs, on arrête de l'appeler pendant un temps, pour ne pas aggraver sa panne ni
  faire attendre nos propres appelants ;
- **délai** : « combien de temps accepte-t-on d'attendre une réponse ? » — un provider
  muet est traité comme une panne, pas comme une attente.

Le temps et le hasard sont injectés (``clock``, ``sleep``, ``rng``) : les tests jouent
des heures en millisecondes et des délais reproductibles.
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
    """Gigue relative (±25 %) : sans elle, tous les clients réessaient à la même seconde."""

    def delay_for(self, attempt: int, retry_after_s: float | None, rng: random.Random) -> float:
        """Délai avant la tentative ``attempt + 1`` (``attempt`` compte à partir de 1).

        Un ``Retry-After`` du provider est respecté, plafonné à ``max_delay_s`` : au-delà,
        on préfère réessayer tôt et échouer vite plutôt que bloquer un appelant.
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
    """Breaker à trois états, par backend.

    ``CLOSED`` : tout passe, on compte les échecs consécutifs. ``OPEN`` : on refuse sans
    appeler, jusqu'à ``recovery_timeout_s``. ``HALF_OPEN`` : on laisse passer un appel
    d'essai ; s'il réussit on referme, s'il échoue on rouvre.

    Seules les erreurs qui parlent de la santé du backend comptent (indisponible, délai) :
    un 400 est notre faute, un 429 est une limite de débit, ni l'un ni l'autre ne dit que
    le backend tombe.
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
    """Un provider muet au-delà de ``timeout_s`` est une panne (réessayable)."""
    if timeout_s is None:
        return await awaitable
    try:
        async with asyncio.timeout(timeout_s):
            return await awaitable
    except TimeoutError:
        raise ProviderTimeoutError(
            f"aucune réponse de {backend!r} en {timeout_s:.1f} s", backend=backend
        ) from None


@dataclass(frozen=True)
class Attempt:
    """Ce qui s'est passé à une tentative : matière première de la trace et du notebook."""

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
    """Appelle ``fn(numéro de tentative)`` jusqu'à succès, erreur non réessayable, ou
    épuisement de ``policy.max_attempts``. Le breaker, s'il est fourni, est consulté avant
    chaque tentative et informé après."""
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
