"""Simulateurs pour les tests et les notebooks : le vrai SDK, un faux réseau.

Plutôt que de remplacer nos classes par des doublures, on remplace **le réseau** : un
transport HTTP scripté renvoie les réponses qu'on décide (un message, un flux SSE, un
429 avec ``Retry-After``, un 529, une coupure, un délai). Tout le reste — le SDK
officiel, la traduction des erreurs, le retry, le breaker, le budget, la trace — est le
code de production, exécuté tel quel. C'est ce qui rend les scénarios de panne du
notebook 1 crédibles : on regarde le vrai chemin, pas une maquette.
"""

import asyncio
import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import anthropic
import httpx2

from llm_testbench.llm.embeddings import EmbeddingRequest, EmbeddingResult
from llm_testbench.llm.providers.anthropic import AnthropicProvider
from llm_testbench.llm.types import Usage


@dataclass(frozen=True)
class Step:
    """Une réponse HTTP scriptée. ``exception`` prime sur le reste ; ``delay_s`` attend
    avant de répondre (pour provoquer un délai côté client)."""

    status: int = 200
    json_body: dict[str, Any] | None = None
    sse_body: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    delay_s: float = 0.0
    exception: str | None = None
    """``"connect"`` (connexion refusée) ou ``"timeout"`` (lecture expirée)."""


def anthropic_message(
    text: str = "Bonjour.",
    *,
    model: str = "claude-sonnet-5",
    input_tokens: int = 120,
    output_tokens: int = 8,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    stop_reason: str = "end_turn",
) -> dict[str, Any]:
    return {
        "id": "msg_scripted",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read_tokens,
            "cache_creation_input_tokens": cache_write_tokens,
        },
    }


def anthropic_error(status: int, message: str, *, retry_after_s: float | None = None) -> Step:
    kinds = {429: "rate_limit_error", 529: "overloaded_error", 500: "api_error"}
    body = {
        "type": "error",
        "error": {"type": kinds.get(status, "invalid_request_error"), "message": message},
    }
    headers = {"retry-after": str(retry_after_s)} if retry_after_s is not None else {}
    return Step(status=status, json_body=body, headers=headers)


def anthropic_sse(parts: Sequence[str], *, model: str = "claude-sonnet-5") -> str:
    message = anthropic_message("", model=model)
    events: list[dict[str, Any]] = [
        {"type": "message_start", "message": {**message, "content": [], "stop_reason": None}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        *[
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": p}}
            for p in parts
        ],
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": len(parts) * 2},
        },
        {"type": "message_stop"},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


class ScriptedTransport:
    """Transport httpx2 qui rejoue une liste de :class:`Step` et enregistre chaque requête.

    La dernière étape se répète si le script est épuisé (``repeat_last=True``) : pratique
    pour « le provider est en panne » sans compter les tentatives à l'avance.
    """

    def __init__(self, steps: Sequence[Step], *, repeat_last: bool = True) -> None:
        self._steps = list(steps)
        self._repeat_last = repeat_last
        self.requests: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content or b"{}"))
        self.headers.append(dict(request.headers))
        if not self._steps:
            raise RuntimeError("script épuisé")
        keep_last = self._repeat_last and len(self._steps) == 1
        step = self._steps[0] if keep_last else self._steps.pop(0)
        if step.delay_s:
            await asyncio.sleep(step.delay_s)
        if step.exception == "connect":
            raise httpx2.ConnectError("connexion refusée (simulée)", request=request)
        if step.exception == "timeout":
            raise httpx2.ReadTimeout("lecture expirée (simulée)", request=request)
        if step.sse_body is not None:
            return httpx2.Response(
                step.status,
                content=step.sse_body.encode(),
                headers={"content-type": "text/event-stream", **step.headers},
            )
        return httpx2.Response(step.status, json=step.json_body or {}, headers=step.headers)

    def transport(self) -> httpx2.AsyncBaseTransport:
        outer = self

        class _Transport(httpx2.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
                return await outer.handle_async_request(request)

        return _Transport()


def scripted_anthropic_provider(
    steps: Sequence[Step], *, backend: str = "anthropic", repeat_last: bool = True
) -> tuple[AnthropicProvider, ScriptedTransport]:
    """Un vrai :class:`AnthropicProvider` (SDK officiel) branché sur un réseau scripté."""
    script = ScriptedTransport(steps, repeat_last=repeat_last)
    client = anthropic.AsyncAnthropic(
        api_key="scripted",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=script.transport()),
    )
    return AnthropicProvider(backend=backend, client=client), script


class ToyEmbedder:
    """Embeddings jouets, déterministes, à trois dimensions : assez pour montrer le cache
    sémantique (deux formulations d'une même question tombent au même endroit)."""

    backend = "openai"

    def __init__(self) -> None:
        self.calls: list[EmbeddingRequest] = []

    @staticmethod
    def vector(text: str) -> tuple[float, ...]:
        lowered = text.lower()
        themes = ("capitale", "recette", "météo")
        raw = [1.0 if theme in lowered else 0.05 for theme in themes]
        norm = sum(x * x for x in raw) ** 0.5
        return tuple(x / norm for x in raw)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.calls.append(request)
        return EmbeddingResult(
            vectors=tuple(self.vector(t) for t in request.texts),
            model="toy-embedding-3d",
            backend=self.backend,
            usage=Usage(input_tokens=sum(len(t) // 4 for t in request.texts)),
            latency_ms=0.5,
        )


class HashingEmbedder:
    """Embeddings « sac de mots hachés » : déterministes, hors ligne, lexicaux.

    Chaque mot est haché vers une dimension (avec un signe), le vecteur est normalisé.
    Deux textes qui partagent des mots ont un cosinus élevé ; aucune sémantique (« voiture »
    et « automobile » sont orthogonaux). C'est l'embedding le plus rustique qui soit — et
    c'est exactement ce que les modèles appris viennent améliorer (notebook 2, partie 5).
    """

    backend = "openai"

    def __init__(self, dimensions: int = 256) -> None:
        # Peu de dimensions = collisions (deux mots dans la même case, signes opposés
        # qui s'annulent) : 256 suffit pour des textes courts.
        self.dimensions = dimensions
        self.calls: list[EmbeddingRequest] = []

    def vector(self, text: str) -> tuple[float, ...]:
        values = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text.lower()):
            digest = int(hashlib.sha1(token.encode("utf-8")).hexdigest()[:8], 16)
            sign = 1.0 if digest >> 31 & 1 else -1.0
            values[digest % self.dimensions] += sign
        norm = math.sqrt(sum(v * v for v in values))
        return tuple(v / norm for v in values) if norm else tuple(values)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.calls.append(request)
        return EmbeddingResult(
            vectors=tuple(self.vector(t) for t in request.texts),
            model=f"hashing-{self.dimensions}d",
            backend=self.backend,
            usage=Usage(input_tokens=sum(len(t) // 4 for t in request.texts)),
            latency_ms=0.5,
        )
