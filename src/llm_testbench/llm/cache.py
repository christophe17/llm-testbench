"""Exact cache and semantic cache for completions (ADR 006).

**Exact**: the key is the canonical fingerprint of *everything* that influences the answer —
backend, model, messages, parameters. Two requests identical down to the character
share an answer; everything else is a miss. Trace metadata does not enter
the key: the same prompt traced under two names remains the same prompt.

**Semantic**: we compare the embedding of the user message with those of past
requests, within a **namespace** that freezes everything else (backend, model, system
prompt, parameters). Without this namespace, the question "summarize this text" served to
another system prompt would return the wrong answer with a perfect similarity.
Reserved for single-turn requests: with a history, the "same question" no longer has
the same answer.

The in-memory backend serves the tests and the notebook; Postgres/pgvector arrives with
ingestion (same database, same extension).
"""

import hashlib
import json
import math
import time
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from llm_testbench.llm.types import Completion, CompletionRequest, Role

_KEY_FIELDS = (
    "max_output_tokens",
    "temperature",
    "stop",
    "seed",
    "json_schema",
    "reasoning_effort",
)


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _params(request: CompletionRequest) -> dict[str, object]:
    return {field: getattr(request, field) for field in _KEY_FIELDS}


def exact_key(request: CompletionRequest) -> str:
    return _digest(
        {
            "model": str(request.model),
            "messages": [(m.role.value, m.content) for m in request.messages],
            **_params(request),
        }
    )


def semantic_namespace(request: CompletionRequest) -> str | None:
    """Namespace of the semantic cache, or ``None`` if the request is not eligible
    (more than one conversation turn)."""
    turns = request.turns
    if len(turns) != 1 or turns[0].role is not Role.USER:
        return None
    return _digest({"model": str(request.model), "system": request.system, **_params(request)})


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"mismatched dimensions: {len(a)} and {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


@runtime_checkable
class CacheBackend(Protocol):
    async def get(self, key: str) -> Completion | None: ...

    async def put(self, key: str, completion: Completion) -> None: ...

    async def find_similar(
        self, namespace: str, vector: Sequence[float], min_similarity: float
    ) -> tuple[Completion, float] | None: ...

    async def put_vector(self, namespace: str, vector: Sequence[float], key: str) -> None: ...


class InMemoryCache:
    def __init__(
        self, *, ttl_s: float | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl_s = ttl_s
        self._clock = clock
        self._entries: dict[str, tuple[float, Completion]] = {}
        self._vectors: dict[str, list[tuple[tuple[float, ...], str]]] = {}

    def _fresh(self, stored_at: float) -> bool:
        return self._ttl_s is None or self._clock() - stored_at < self._ttl_s

    async def get(self, key: str) -> Completion | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, completion = entry
        if not self._fresh(stored_at):
            del self._entries[key]
            return None
        return completion

    async def put(self, key: str, completion: Completion) -> None:
        self._entries[key] = (self._clock(), completion)

    async def find_similar(
        self, namespace: str, vector: Sequence[float], min_similarity: float
    ) -> tuple[Completion, float] | None:
        best: tuple[str, float] | None = None
        for stored, key in self._vectors.get(namespace, ()):
            similarity = cosine_similarity(stored, vector)
            if similarity >= min_similarity and (best is None or similarity > best[1]):
                best = (key, similarity)
        if best is None:
            return None
        completion = await self.get(best[0])
        return (completion, best[1]) if completion is not None else None

    async def put_vector(self, namespace: str, vector: Sequence[float], key: str) -> None:
        self._vectors.setdefault(namespace, []).append((tuple(vector), key))

    def __len__(self) -> int:
        return len(self._entries)
