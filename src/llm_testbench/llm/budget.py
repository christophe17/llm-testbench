"""Budget de tokens : par requête et sur une fenêtre glissante (ADR 006).

Un budget refuse **avant** l'appel, sur une estimation ; il comptabilise **après**, sur
l'usage réel. L'estimation d'entrée est grossière (quatre caractères par token, l'ordre de
grandeur de l'anglais) : elle ne sert qu'à décider si l'appel a le droit de partir, jamais
au coût. La réservation de sortie prend ``max_output_tokens`` en entier : on refuse un
appel qui *pourrait* dépasser, pas seulement un appel qui dépassera à coup sûr.

Phase 1 : compteur en mémoire, donc par processus. La phase 5 le rendra partagé
(Postgres) pour qu'un budget vaille pour toutes les réplicas de l'API.
"""

import time
from collections import deque
from collections.abc import Callable

from llm_testbench.llm.errors import BudgetExceededError
from llm_testbench.llm.types import Usage

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimation grossière, volontairement pessimiste (arrondi vers le haut)."""
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
                f"entrée estimée à {estimated_input_tokens} tokens, plafond par requête "
                f"{self.max_input_tokens_per_request}"
            )
        if (
            self.max_output_tokens_per_request is not None
            and max_output_tokens > self.max_output_tokens_per_request
        ):
            raise BudgetExceededError(
                f"max_output_tokens={max_output_tokens}, plafond par requête "
                f"{self.max_output_tokens_per_request}"
            )
        if self.max_tokens_per_window is not None:
            spent = self.spent_in_window()
            reserved = estimated_input_tokens + max_output_tokens
            if spent + reserved > self.max_tokens_per_window:
                raise BudgetExceededError(
                    f"{spent} tokens déjà consommés sur la fenêtre de {self.window_s:.0f} s, "
                    f"{reserved} réservés pour cet appel, plafond {self.max_tokens_per_window}"
                )

    def record(self, usage: Usage) -> None:
        self._ledger.append((self._clock(), usage.total_tokens))
        self._prune()

    def snapshot(self) -> dict[str, int | None]:
        return {
            "spent_in_window": self.spent_in_window(),
            "max_tokens_per_window": self.max_tokens_per_window,
        }
