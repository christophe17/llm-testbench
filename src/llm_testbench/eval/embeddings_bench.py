"""Measured comparison of embedding models on SciFact, via the ``mteb`` library.

Why ``mteb`` here, before our harness (phase 2): it is the reference implementation of
the published scores. The nDCG@10 values obtained become a reference point that **our**
harness will have to reproduce in phase 2 — a free cross-check. Open models go through
the ``mteb`` encoders; the API model goes through **our** ``LLMClient.embed`` (governance,
cost, traces), thanks to an adapter that follows the ``mteb`` encoder protocol.

Heavy dependencies (``torch``, ``sentence-transformers``): uv ``bench`` group, imported
lazily so that the rest of the project does not pay for them.
"""

import argparse
import asyncio
import datetime as dt
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.types import ModelRef

TASK_NAME = "SciFact"
METRIC = "ndcg_at_10"

PUBLISHED_SCIFACT: dict[str, tuple[float | None, str]] = {
    "BM25 (Anserini)": (0.665, "Thakur et al. 2021, BEIR, table 2"),
    "BAAI/bge-base-en-v1.5": (0.7404, "HF model card, MTEB results, read on 2026-09-03"),
    "intfloat/e5-base-v2": (0.7194, "HF model card, MTEB results, read on 2026-09-03"),
    "sentence-transformers/all-MiniLM-L6-v2": (None, "no SciFact score on the HF card"),
    "openai/text-embedding-3-small": (None, "OpenAI does not publish per-task scores"),
}
"""Published nDCG@10 scores, with their source. ``None`` = no reference found, said as is."""


class ModelScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    ndcg_at_10: float
    recall_at_10: float | None = None
    map_at_10: float | None = None
    dimensions: int | None = None
    elapsed_s: float = Field(ge=0)
    cost_usd: float | None = None
    """Cost of the API embeddings (corpus + queries); ``None`` for a local model."""
    published_ndcg_at_10: float | None = None
    published_source: str = ""
    backend: str = "local"

    @property
    def gap_to_published(self) -> float | None:
        if self.published_ndcg_at_10 is None:
            return None
        return self.ndcg_at_10 - self.published_ndcg_at_10


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    task: str = TASK_NAME
    metric: str = METRIC
    generated_at: dt.datetime
    sampled: bool = False
    scores: tuple[ModelScore, ...]

    def table(self) -> str:
        header = (
            f"{'model':<42} {'nDCG@10':>8} {'published':>9} {'gap':>7} {'dim':>5} "
            f"{'time':>7} {'cost':>9}"
        )
        rows = [header]
        for s in self.scores:
            published = (
                f"{s.published_ndcg_at_10:.3f}" if s.published_ndcg_at_10 is not None else "—"
            )
            gap = f"{s.gap_to_published:+.3f}" if s.gap_to_published is not None else "—"
            cost = f"${s.cost_usd:.4f}" if s.cost_usd is not None else "local"
            rows.append(
                f"{s.model:<42} {s.ndcg_at_10:>8.3f} {published:>9} {gap:>7} "
                f"{s.dimensions or '?':>5} {s.elapsed_s:>6.0f}s {cost:>9}"
            )
        return "\n".join(rows)


class ClientEncoder:
    """Adapter: the ``mteb`` encoder protocol on top of ``LLMClient.embed``.

    Each batch goes through the facade: governance checked (data class ``public``: these
    are public datasets), cost computed, span emitted. The total cost is accumulated for
    the report — it is the "how much does indexing SciFact with this model cost" line.
    """

    def __init__(
        self,
        client: LLMClient,
        model: str,
        *,
        data_class: DataClass = DataClass.PUBLIC,
        dimensions: int | None = None,
    ) -> None:
        self._client = client
        self._model = ModelRef.parse(model)
        self._data_class = data_class
        self._dimensions = dimensions
        self.cost_usd: float | None = 0.0
        self.calls = 0
        self.mteb_model_meta = self._model_meta(model, dimensions)

    @staticmethod
    def _model_meta(model: str, dimensions: int | None) -> Any:
        from mteb.models.model_meta import ModelMeta, ScoringFunction

        return ModelMeta(
            loader=None,
            name=model,
            revision="api",
            release_date=None,
            languages=["eng-Latn"],
            n_parameters=None,
            memory_usage_mb=None,
            max_tokens=8191,
            embed_dim=dimensions,
            license="not specified",
            open_weights=False,
            public_training_code=None,
            public_training_data=None,
            framework=["API"],
            similarity_fn_name=ScoringFunction.COSINE,
            use_instructions=False,
            training_datasets=None,
        )

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        request = EmbeddingRequest(
            model=self._model,
            texts=tuple(texts),
            data_class=self._data_class,
            dimensions=self._dimensions,
        )
        result = asyncio.run(self._client.embed(request))
        self.calls += 1
        if self.cost_usd is not None:
            self.cost_usd = None if result.cost_usd is None else self.cost_usd + result.cost_usd
        return np.asarray(result.vectors, dtype=np.float32)

    def encode(self, inputs: Iterable[dict[str, Any]], **_: Any) -> np.ndarray:
        """``inputs`` is a DataLoader of ``{"text": [...], ...}`` batches (mteb protocol)."""
        batches = [self._embed_texts(list(batch["text"])) for batch in inputs]
        return np.concatenate(batches, axis=0) if batches else np.zeros((0, 0), dtype=np.float32)


def _score(task_result: Any, split: str = "test") -> dict[str, float]:
    scores = task_result.scores[split][0]
    return {k: float(v) for k, v in scores.items() if isinstance(v, int | float)}


def run_scifact(
    models: Iterable[str],
    *,
    client: LLMClient | None = None,
    device: str | None = None,
    batch_size: int = 64,
    api_dimensions: int | None = None,
) -> BenchmarkReport:
    """Evaluate each model on SciFact (test, 300 queries, 5,183 documents).

    A ``backend/model`` name (e.g. ``openai/text-embedding-3-small``) goes through ``client``;
    any other name is an ``mteb`` model (Hugging Face), loaded locally.
    """
    import mteb

    task = mteb.get_task(TASK_NAME)
    scores: list[ModelScore] = []
    for name in models:
        started = time.perf_counter()
        is_api = "/" in name and name.split("/", 1)[0] in {"openai", "openrouter", "local"}
        if is_api:
            if client is None:
                raise ValueError(f"{name!r} requires an LLMClient (API model)")
            encoder = ClientEncoder(client, name, dimensions=api_dimensions)
            # cast: the mteb encoder protocol is typed more finely than our adapter, and mteb
            # is absent from environments without the `bench` group (CI).
            result = mteb.evaluate(
                cast(Any, encoder),
                [task],
                encode_kwargs={"batch_size": batch_size},
                show_progress_bar=False,
                overwrite_strategy="always",
            )
            cost, backend, dims = encoder.cost_usd, encoder._model.backend, api_dimensions
        else:
            model = mteb.get_model(name, device=device)
            # Always re-encode: mteb caches its results, and a time measured on a cache is
            # not an indexing time.
            result = mteb.evaluate(
                model,
                [task],
                encode_kwargs={"batch_size": batch_size},
                show_progress_bar=False,
                overwrite_strategy="always",
            )
            cost, backend = None, "local"
            meta = getattr(model, "mteb_model_meta", None)
            dims = getattr(meta, "embed_dim", None) if meta is not None else None
        metrics = _score(result.task_results[0])
        published, source = PUBLISHED_SCIFACT.get(name, (None, "no reference recorded"))
        scores.append(
            ModelScore(
                model=name,
                ndcg_at_10=metrics[METRIC],
                recall_at_10=metrics.get("recall_at_10"),
                map_at_10=metrics.get("map_at_10"),
                dimensions=dims if isinstance(dims, int) else None,
                elapsed_s=time.perf_counter() - started,
                cost_usd=cost,
                published_ndcg_at_10=published,
                published_source=source,
                backend=backend,
            )
        )
    return BenchmarkReport(generated_at=dt.datetime.now(dt.UTC), scores=tuple(scores))


def save_report(report: BenchmarkReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_report(path: Path) -> BenchmarkReport:
    return BenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))


DEFAULT_MODELS = (
    "sentence-transformers/all-MiniLM-L6-v2",
    "BAAI/bge-base-en-v1.5",
    "openai/text-embedding-3-small",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare embedding models on SciFact.")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--output", type=Path, default=Path("data/results/embeddings_scifact.json"))
    parser.add_argument("--device", default=None, help="cpu, mps, cuda (local models)")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)
    api_backends = {"openai", "openrouter", "local"}
    needs_client = any(m.split("/", 1)[0] in api_backends for m in args.models if "/" in m)
    client = LLMClient.from_settings() if needs_client else None
    report = run_scifact(args.models, client=client, device=args.device, batch_size=args.batch_size)
    save_report(report, args.output)
    sys.stdout.write(report.table() + f"\n→ {args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
