"""Typed errors of the LLM layer.

Each error carries a ``retryable`` flag: it is this flag, and this flag alone, that the
retry policy consults. An HTTP code is not enough to decide (a 400 is never retryable, a
529 "overloaded" always is), and a provider can fail with no code at all (network
outage, timeout exceeded).
"""

from llm_testbench.llm.governance import DataClass


class LLMError(Exception):
    """Base of all errors of the LLM layer."""

    retryable: bool = False


class ProviderError(LLMError):
    """Provider-side failure: non-2xx HTTP response, network, timeout."""

    def __init__(
        self,
        message: str,
        *,
        backend: str,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message)
        self.backend = backend
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_s = retry_after_s


class RateLimitedError(ProviderError):
    """429: too many requests. Retryable, honoring ``retry_after_s`` if given."""

    def __init__(
        self,
        message: str,
        *,
        backend: str,
        status_code: int | None = 429,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(
            message,
            backend=backend,
            status_code=status_code,
            retryable=True,
            retry_after_s=retry_after_s,
        )


class ProviderUnavailableError(ProviderError):
    """5xx, 529 "overloaded", or connection impossible. Retryable."""

    def __init__(self, message: str, *, backend: str, status_code: int | None = None) -> None:
        super().__init__(message, backend=backend, status_code=status_code, retryable=True)


class ProviderTimeoutError(ProviderError):
    """Timeout exceeded before the response. Retryable (the provider may have received nothing)."""

    def __init__(self, message: str, *, backend: str) -> None:
        super().__init__(message, backend=backend, status_code=None, retryable=True)


class InvalidRequestError(ProviderError):
    """4xx other than 429: the request is wrong, replaying it will change nothing."""

    def __init__(self, message: str, *, backend: str, status_code: int | None = None) -> None:
        super().__init__(message, backend=backend, status_code=status_code, retryable=False)


class MissingCredentialsError(LLMError):
    """API key environment variable missing for a backend we are trying to use."""


class UnknownBackendError(LLMError):
    """Backend absent from ``config/llm_backends.toml``."""


class BackendDisabledError(LLMError):
    """Backend declared but disabled (``enabled = false``)."""


class GovernanceViolation(LLMError):
    """The governance policy refuses this backend for this data class.

    Raised BEFORE any network call. Never converted into a silent fallback: if a fallback
    exists, the caller decides it, and it is traced.
    """

    def __init__(self, *, data_class: DataClass, backend: str, reasons: tuple[str, ...]) -> None:
        detail = "; ".join(reasons) if reasons else "no reason given"
        super().__init__(
            f"backend {backend!r} refused for data class {data_class.value!r}: {detail}"
        )
        self.data_class = data_class
        self.backend = backend
        self.reasons = reasons


class BudgetExceededError(LLMError):
    """Token budget exceeded, per request or over the sliding window."""


class CircuitOpenError(LLMError):
    """The backend circuit breaker is open: we fail fast without calling the provider."""

    def __init__(self, *, backend: str, retry_in_s: float) -> None:
        super().__init__(
            f"circuit open for backend {backend!r}, retry possible in {retry_in_s:.1f} s"
        )
        self.backend = backend
        self.retry_in_s = retry_in_s


class StructuredOutputError(LLMError):
    """Invalid structured output after the repair attempts are exhausted."""

    def __init__(self, message: str, *, attempts: int, raw_text: str, last_error: str) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.raw_text = raw_text
        self.last_error = last_error


class PromptError(LLMError):
    """Prompt not found, invalid header, or rendering impossible (missing variable)."""
