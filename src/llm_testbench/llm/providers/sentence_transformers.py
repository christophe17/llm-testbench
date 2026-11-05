"""Embeddings computed in process with ``sentence-transformers`` (open models).

Why a provider rather than a script on the side: the harness must reproduce published
scores with the very pipeline that serves the API (phase 2.2), and those scores are
published for open models. Behind :class:`EmbeddingProvider`, an open model is ingested,
governed, traced and measured like an API model; the only difference is that the text does
not leave the machine, which the backend's governance metadata says.

Three things a published score depends on, all read from the registry
(``config/llm_backends.toml``, ``embedding_models``), none hidden in code:

- the **revision** of the weights, pinned;
- the **query prompt**: an asymmetric model embeds a question behind an instruction and a
  passage without one. ``mteb`` applies it from its own model table; here it comes with
  ``EmbeddingRequest.input_type``;
- the **window**: beyond ``max_seq_length`` tokens the text is cut without a warning. The
  usage reports the tokens the model actually read.

The library and ``torch`` are heavy: uv ``bench`` group, imported at the first call.
"""

import asyncio
import threading
from collections.abc import Callable, Mapping
from typing import Any

from llm_testbench.llm.embeddings import EmbeddingRequest, EmbeddingResult
from llm_testbench.llm.errors import InvalidRequestError
from llm_testbench.llm.providers._common import Stopwatch
from llm_testbench.llm.registry import BackendConfig, EmbeddingModelConfig
from llm_testbench.llm.types import Usage

ModelLoader = Callable[[str, str | None], Any]
"""(model name, revision) -> an object with ``preprocess`` (``tokenize`` before version 6)
and ``encode``, the two methods of ``SentenceTransformer`` this provider calls. Injectable:
the tests need no ``torch``."""


def _load_sentence_transformer(name: str, revision: str | None) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, revision=revision)


class SentenceTransformerEmbeddingProvider:
    def __init__(
        self,
        *,
        backend: str,
        models: Mapping[str, EmbeddingModelConfig] | None = None,
        loader: ModelLoader = _load_sentence_transformer,
        batch_size: int = 32,
    ) -> None:
        self.backend = backend
        self._models = dict(models or {})
        self._loader = loader
        self._batch_size = batch_size
        self._loaded: dict[str, Any] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_config(
        cls, backend: str, config: BackendConfig
    ) -> "SentenceTransformerEmbeddingProvider":
        return cls(backend=backend, models=config.embedding_models)

    def _model(self, name: str) -> Any:
        # Loading takes seconds and hundreds of megabytes: once per model, even when two
        # batches arrive together.
        with self._lock:
            if name not in self._loaded:
                declared = self._models.get(name)
                revision = declared.revision if declared is not None else None
                try:
                    self._loaded[name] = self._loader(name, revision)
                except ImportError as error:
                    raise InvalidRequestError(
                        "sentence-transformers is not installed: `uv sync --group bench`",
                        backend=self.backend,
                    ) from error
            return self._loaded[name]

    def _encode(self, request: EmbeddingRequest) -> tuple[tuple[tuple[float, ...], ...], int]:
        name = request.model.model
        model = self._model(name)
        declared = self._models.get(name)
        prompt = declared.query_prompt if declared and request.input_type == "query" else ""
        texts = list(request.texts)
        # Same tokenizer and same truncation as the forward pass: the real input size.
        # (`preprocess` replaced `tokenize` in sentence-transformers 6.)
        tokenize = getattr(model, "preprocess", None) or model.tokenize
        features = tokenize([prompt + text for text in texts])
        tokens = int(features["attention_mask"].sum())
        vectors = model.encode(
            texts,
            prompt=prompt or None,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if request.dimensions is not None and vectors.shape[1] != request.dimensions:
            raise InvalidRequestError(
                f"{name} produces vectors of dimension {vectors.shape[1]}, "
                f"{request.dimensions} requested",
                backend=self.backend,
            )
        return tuple(tuple(float(x) for x in row) for row in vectors), tokens

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        watch = Stopwatch()
        # The forward pass holds the CPU or the GPU: in a thread, the event loop stays free.
        vectors, tokens = await asyncio.to_thread(self._encode, request)
        return EmbeddingResult(
            vectors=vectors,
            model=request.model.model,
            backend=self.backend,
            usage=Usage(input_tokens=tokens),
            latency_ms=watch.elapsed_ms,
        )
