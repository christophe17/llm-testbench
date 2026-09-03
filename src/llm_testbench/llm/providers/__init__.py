"""Les implémentations concrètes du protocole :class:`LLMProvider` (ADR 006)."""

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
    """Construit le provider d'un backend à partir de sa configuration.

    C'est ici, et seulement ici, qu'un client SDK est créé : les clés sont lues à ce
    moment, jamais stockées dans la configuration.
    """
    if config.kind in (BackendKind.ANTHROPIC, BackendKind.ANTHROPIC_BEDROCK):
        return AnthropicProvider.from_config(backend, config)
    return OpenAICompatibleProvider.from_config(backend, config)


def build_embedding_provider(backend: str, config: BackendConfig) -> EmbeddingProvider:
    """Anthropic n'a pas d'endpoint d'embeddings : seuls les backends compatibles OpenAI
    (et, plus tard, les modèles locaux) en fournissent."""
    if config.kind is not BackendKind.OPENAI_COMPATIBLE:
        raise InvalidRequestError(
            f"le backend {backend!r} ({config.kind.value}) ne fournit pas d'embeddings",
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
