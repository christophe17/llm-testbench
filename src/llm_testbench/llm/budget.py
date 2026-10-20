"""Token budget: per request and over a sliding window (ADR 006).

A budget refuses **before** the call, on an estimate; it accounts **after**, on actual
usage. The input estimate is rough (four characters per token, the order of magnitude
for English): it only serves to decide whether the call is allowed to go out, never
for cost. The output reservation takes ``max_output_tokens`` in full: we refuse a
call that *could* exceed, not only a call that will exceed for sure.

Phase 1: in-memory counter, hence per process. Phase 5 will make it shared
(Postgres) so that a budget holds across all API replicas.
"""

import time
from collections import deque
from collections.abc import Callable

from llm_testbench.llm.errors import BudgetExceededError
from llm_testbench.llm.types import Usage

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough estimate, deliberately pessimistic (rounded up)."""
    return -(-len(text) // _CHARS_PER_TOKEN) if text else 0


class TokenBudget:
    def __init__(
        self,
        *,
        max_input_tokens_per_request: int | None = None,
        max_output_tokens_per_request: int | None = None,
        max_tokens_per_window: int | None = None,
        window_s: float = 86_400.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_input_tokens_per_request = max_input_tokens_per_request
        self.max_output_tokens_per_request = max_output_tokens_per_request
        self.max_tokens_per_window = max_tokens_per_window
        self.window_s = window_s
        self._clock = clock
        self._ledger: deque[tuple[float, int]] = deque()

    def _prune(self) -> None:
        horizon = self._clock() - self.window_s
        while self._ledger and self._ledger[0][0] < horizon:
            self._ledger.popleft()

    def spent_in_window(self) -> int:
        self._prune()
        return sum(tokens for _, tokens in self._ledger)

    def check(self, *, estimated_input_tokens: int, max_output_tokens: int) -> None:
        if (
            self.max_input_tokens_per_request is not None
            and estimated_input_tokens > self.max_input_tokens_per_request
        ):
            raise BudgetExceededError(
                f"input estimated at {estimated_input_tokens} tokens, per-request cap "
                f"{self.max_input_tokens_per_request}"
            )
        if (
            self.max_output_tokens_per_request is not None
            and max_output_tokens > self.max_output_tokens_per_request
        ):
            raise BudgetExceededError(
                f"max_output_tokens={max_output_tokens}, per-request cap "
                f"{self.max_output_tokens_per_request}"
            )
        if self.max_tokens_per_window is not None:
            spent = self.spent_in_window()
            reserved = estimated_input_tokens + max_output_tokens
            if spent + reserved > self.max_tokens_per_window:
                raise BudgetExceededError(
                    f"{spent} tokens already spent in the {self.window_s:.0f} s window, "
                    f"{reserved} reserved for this call, cap {self.max_tokens_per_window}"
                )

    def record(self, usage: Usage) -> None:
        self._ledger.append((self._clock(), usage.total_tokens))
        self._prune()

    def snapshot(self) -> dict[str, int | None]:
        return {
            "spent_in_window": self.spent_in_window(),
            "max_tokens_per_window": self.max_tokens_per_window,
        }
