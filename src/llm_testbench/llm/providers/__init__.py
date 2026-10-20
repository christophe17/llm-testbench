"""The concrete implementations of the :class:`LLMProvider` protocol (ADR 006)."""

from llm_testbench.llm.embeddings import EmbeddingProvider
from llm_testbench.llm.errors import InvalidRequestError
from llm_testbench.llm.provider import LLMProvider
from llm_testbench.llm.providers.anthropic import AnthropicProvider
from llm_testbench.llm.providers.openai_compatible import (
    OpenAICompatibleProvider,
    OpenAIEmbeddingProvider,
)
from llm_testbench.llm.registry import BackendConfig, BackendKind


def build_provider(backend: str, config: BackendConfig) -> LLMProvider:
    """Builds the provider of a backend from its configuration.

    It is here, and only here, that an SDK client is created: the keys are read at that
    moment, never stored in the configuration.
    """
    if config.kind in (BackendKind.ANTHROPIC, BackendKind.ANTHROPIC_BEDROCK):
        return AnthropicProvider.from_config(backend, config)
    return OpenAICompatibleProvider.from_config(backend, config)


def build_embedding_provider(backend: str, config: BackendConfig) -> EmbeddingProvider:
    """Anthropic has no embeddings endpoint: only OpenAI-compatible backends
    (and, later, local models) provide them."""
    if config.kind is not BackendKind.OPENAI_COMPATIBLE:
        raise InvalidRequestError(
            f"backend {backend!r} ({config.kind.value}) does not provide embeddings",
            backend=backend,
        )
    return OpenAIEmbeddingProvider.from_config(backend, config)


__all__ = [
    "AnthropicProvider",
    "OpenAICompatibleProvider",
    "OpenAIEmbeddingProvider",
    "build_embedding_provider",
    "build_provider",
]
