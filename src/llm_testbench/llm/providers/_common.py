"""Petits utilitaires partagés par les providers."""

import time
from collections.abc import Mapping


def retry_after_seconds(headers: Mapping[str, str] | None) -> float | None:
    """Lit un en-tête ``Retry-After`` numérique (secondes). Le format date HTTP est ignoré :
    il est rare chez les providers LLM et un mauvais calcul vaudrait pire qu'un backoff."""
    if headers is None:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return None


class Stopwatch:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0
