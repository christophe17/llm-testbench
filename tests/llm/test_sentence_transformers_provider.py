"""The in-process embedding provider, on a stand-in model: no ``torch`` needed."""

from typing import Any

import numpy as np
import pytest

from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.errors import InvalidRequestError
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.providers import build_embedding_provider, build_provider
from llm_testbench.llm.providers.sentence_transformers import SentenceTransformerEmbeddingProvider
from llm_testbench.llm.registry import EmbeddingModelConfig, Registry
from llm_testbench.llm.types import ModelRef
from tests.llm.test_registry import BACKENDS_TOML

MODEL = "BAAI/bge-base-en-v1.5"
PROMPT = "Represent this sentence for searching relevant passages: "


class StandInModel:
    """The two methods of ``SentenceTransformer`` the provider calls."""

    def __init__(self) -> None:
        self.encoded: list[tuple[list[str], str | None]] = []
        self.tokenized: list[list[str]] = []

    def tokenize(self, texts: list[str]) -> dict[str, Any]:
        self.tokenized.append(texts)
        return {"attention_mask": np.ones((len(texts), 4), dtype=np.int64)}

    def encode(self, texts: list[str], *, prompt: str | None = None, **_: Any) -> np.ndarray:
        self.encoded.append((texts, prompt))
        return np.tile(np.asarray([0.6, 0.8], dtype=np.float32), (len(texts), 1))


def provider(model: StandInModel) -> tuple[SentenceTransformerEmbeddingProvider, list[Any]]:
    loads: list[Any] = []

    def loader(name: str, revision: str | None) -> StandInModel:
        loads.append((name, revision))
        return model

    built = SentenceTransformerEmbeddingProvider(
        backend="hf",
        models={MODEL: EmbeddingModelConfig(dimensions=2, revision="abc123", query_prompt=PROMPT)},
        loader=loader,
    )
    return built, loads


def request(*texts: str, **overrides: Any) -> EmbeddingRequest:
    return EmbeddingRequest(
        model=ModelRef(backend="hf", model=MODEL),
        texts=texts,
        data_class=DataClass.PUBLIC,
        **overrides,
    )


async def test_documents_are_embedded_without_the_query_prompt() -> None:
    model = StandInModel()
    embedder, loads = provider(model)
    result = await embedder.embed(request("a passage", "another"))
    assert model.encoded == [(["a passage", "another"], None)]
    assert result.vectors == ((pytest.approx(0.6), pytest.approx(0.8)),) * 2
    assert (result.model, result.backend) == (MODEL, "hf")
    # 2 texts of 4 tokens each, as counted by the model's own tokenizer.
    assert result.usage.input_tokens == 8
    assert result.usage_reported
    assert loads == [(MODEL, "abc123")]


async def test_a_query_gets_the_declared_prompt() -> None:
    model = StandInModel()
    embedder, _ = provider(model)
    await embedder.embed(request("what is a chunk?", input_type="query"))
    assert model.encoded == [(["what is a chunk?"], PROMPT)]
    # The prompt is part of what the model reads, so part of what is counted.
    assert model.tokenized == [[PROMPT + "what is a chunk?"]]


async def test_the_model_is_loaded_once() -> None:
    embedder, loads = provider(StandInModel())
    await embedder.embed(request("one"))
    await embedder.embed(request("two"))
    assert len(loads) == 1


async def test_a_missing_library_is_a_typed_error_that_says_what_to_install() -> None:
    def loader(name: str, revision: str | None) -> Any:
        raise ImportError("No module named 'sentence_transformers'")

    embedder = SentenceTransformerEmbeddingProvider(backend="hf", loader=loader)
    with pytest.raises(InvalidRequestError, match="uv sync --group bench"):
        await embedder.embed(request("text"))


async def test_a_dimension_the_model_does_not_produce_is_refused() -> None:
    embedder, _ = provider(StandInModel())
    with pytest.raises(InvalidRequestError, match="dimension 2, 768 requested"):
        await embedder.embed(request("text", dimensions=768))
    assert (await embedder.embed(request("text", dimensions=2))).dimensions == 2


def test_the_registry_declares_the_backend_and_its_models() -> None:
    registry = Registry.load(BACKENDS_TOML)
    _, config = registry.resolve(f"hf/{MODEL}")
    assert config.governance.inference_region.value == "self"
    assert config.embedding_models[MODEL].query_prompt == PROMPT
    assert registry.embedding_dimensions(f"hf/{MODEL}") == 768
    assert registry.embedding_dimensions("openai/text-embedding-3-small") == 1536
    assert registry.embedding_dimensions("openai/unknown-model") is None
    assert isinstance(build_embedding_provider("hf", config), SentenceTransformerEmbeddingProvider)
    with pytest.raises(InvalidRequestError, match="only provides embeddings"):
        build_provider("hf", config)
