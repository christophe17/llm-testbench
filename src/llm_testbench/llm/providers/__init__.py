"""Les implémentations concrètes du protocole :class:`LLMProvider` (ADR 006)."""

from llm_testbench.llm.provider import LLMProvider
from llm_testbench.llm.providers.anthropic import AnthropicProvider
from llm_testbench.llm.providers.openai_compatible import OpenAICompatibleProvider
from llm_testbench.llm.registry import BackendConfig, BackendKind


def build_provider(backend: str, config: BackendConfig) -> LLMProvider:
    """Construit le provider d'un backend à partir de sa configuration.

    C'est ici, et seulement ici, qu'un client SDK est créé : les clés sont lues à ce
    moment, jamais stockées dans la configuration.
    """
    if config.kind in (BackendKind.ANTHROPIC, BackendKind.ANTHROPIC_BEDROCK):
        return AnthropicProvider.from_config(backend, config)
    return OpenAICompatibleProvider.from_config(backend, config)


__all__ = ["AnthropicProvider", "OpenAICompatibleProvider", "build_provider"]
