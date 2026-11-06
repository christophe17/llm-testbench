# The client and its providers

One facade, `LLMClient`, and behind it one provider object per backend. The point of this
picture is the dashed arrows: the providers satisfy a `Protocol`, they do not inherit from
anything, so no generated diagram can draw this relation.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction TB
  class LLMClient {
    <<facade>>
    +registry : Registry
    +policy : GovernancePolicy
    +pricing : PricingTable
    +from_settings(settings) LLMClient$
    +complete(request) Completion
    +stream(request) AsyncIterator~StreamChunk~
    +embed(request) EmbeddingResult
    +provider_for(backend, config) LLMProvider
    +embedder_for(backend, config) EmbeddingProvider
    +register_provider(backend, provider)
    +register_embedder(backend, provider)
  }
  class Registry {
    +defaults : Defaults
    +backends : dict~str, BackendConfig~
    +load(path) Registry$
    +resolve(ref) tuple~ModelRef, BackendConfig~
  }
  class Defaults {
    +generator : ModelRef
    +judge : ModelRef | None
    +embeddings : ModelRef | None
  }
  class BackendConfig {
    +kind : BackendKind
    +api_key_env : str | None
    +base_url : str | None
    +region : str | None
    +enabled : bool
    +structured_output : StructuredOutputMode
    +governance : BackendGovernance
    +api_key() str | None
  }
  class BackendKind {
    <<enumeration>>
    ANTHROPIC
    ANTHROPIC_BEDROCK
    OPENAI_COMPATIBLE
  }
  class LLMProvider {
    <<Protocol>>
    +backend : str
    +native_json_schema : bool
    +complete(request) Completion
    +stream(request) AsyncIterator~StreamChunk~
  }
  class EmbeddingProvider {
    <<Protocol>>
    +backend : str
    +embed(request) EmbeddingResult
  }
  class AnthropicProvider {
    +from_config(backend, config) AnthropicProvider$
    +build_params(request) dict
    +translate_error(error) LLMError
    +complete(request) Completion
    +stream(request) AsyncIterator~StreamChunk~
  }
  class OpenAICompatibleProvider {
    +from_config(backend, config) OpenAICompatibleProvider$
    +build_params(request) dict
    +translate_error(error) LLMError
    +complete(request) Completion
    +stream(request) AsyncIterator~StreamChunk~
  }
  class OpenAIEmbeddingProvider {
    +from_config(backend, config) OpenAIEmbeddingProvider$
    +embed(request) EmbeddingResult
  }
  class AsyncAnthropic {
    <<external>>
  }
  class AsyncOpenAI {
    <<external>>
  }
  LLMClient --> Registry : resolve(model) comes first
  Registry *-- BackendConfig : backends, one per name in llm_backends.toml
  Registry --> Defaults : defaults
  BackendConfig --> BackendKind : kind selects the provider class
  LLMClient --> LLMProvider : one per backend, built on first use
  LLMClient --> EmbeddingProvider : one per backend
  AnthropicProvider ..|> LLMProvider : satisfies, no inheritance
  OpenAICompatibleProvider ..|> LLMProvider : satisfies, no inheritance
  OpenAIEmbeddingProvider ..|> EmbeddingProvider : satisfies
  AnthropicProvider --> AsyncAnthropic : wraps the anthropic SDK, Bedrock included
  OpenAICompatibleProvider --> AsyncOpenAI : wraps the openai SDK
  OpenAIEmbeddingProvider --> AsyncOpenAI : wraps the openai SDK
```

## How to read it

- `..|>` is UML realization: "implements the interface". In Python with
  `typing.Protocol` the relation is structural, checked by mypy on the method signatures.
  Nothing in `AnthropicProvider` mentions `LLMProvider`. That is also why a simulated
  provider in a test or a notebook is a plain class with the right two methods.
- `LLMClient` never constructs a provider itself. `provider_for` asks a factory, keyed by
  `BackendConfig.kind`, and caches the result per backend. `register_provider` bypasses the
  factory: this is the injection point used to knock links down in notebook 01.
- The same `OpenAICompatibleProvider` class serves OpenAI, OpenRouter, Mistral, vLLM and
  Ollama. Only `base_url` and the API key variable change, in the registry file, not in code.
- The registry is a file, `config/llm_backends.toml`, validated at load time: the defaults
  must point to known backends.
- The client also holds the guards drawn in [04 the guards around a call](04-guards.md) and
  the policy of [03 governance](03-governance.md). They are left out here on purpose.

## In the code

[llm/client.py](../../src/llm_testbench/llm/client.py),
[llm/provider.py](../../src/llm_testbench/llm/provider.py),
[llm/registry.py](../../src/llm_testbench/llm/registry.py),
[llm/providers/anthropic.py](../../src/llm_testbench/llm/providers/anthropic.py),
[llm/providers/openai_compatible.py](../../src/llm_testbench/llm/providers/openai_compatible.py),
[llm/embeddings.py](../../src/llm_testbench/llm/embeddings.py).

## In the notebooks

Notebook 01, parts 3.2 and 3.5.
