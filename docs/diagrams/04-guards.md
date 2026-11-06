# The guards around a call

Everything that stands between `LLMClient.complete` and the provider, in the order the
client applies it. Each guard is an injectable object, which is how notebook 01 knocks them
down one at a time.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction TB
  class LLMClient {
    +retry_policy : RetryPolicy
    +budget : TokenBudget | None
    +cache : CacheBackend | None
    +semantic_cache : SemanticCacheConfig | None
    +pricing : PricingTable
    +default_timeout_s : float
    +breaker_for(backend) CircuitBreaker
  }
  class RetryPolicy {
    +max_attempts : int
    +base_delay_s : float
    +max_delay_s : float
    +multiplier : float
    +jitter : float
    +delay_for(attempt, retry_after_s, rng) float
  }
  class RetryReport {
    +attempts : list~Attempt~
    +count : int
  }
  class Attempt {
    +number : int
    +error : LLMError | None
    +delay_before_next_s : float | None
  }
  class CircuitBreaker {
    +backend : str
    +failure_threshold : int
    +recovery_timeout_s : float
    +state : CircuitState
    +before_call()
    +record_success()
    +record_failure()
    +counts(error) bool$
    +snapshot() dict
  }
  class CircuitState {
    <<enumeration>>
    CLOSED
    OPEN
    HALF_OPEN
  }
  class TokenBudget {
    +max_input_tokens_per_request : int | None
    +max_output_tokens_per_request : int | None
    +max_tokens_per_window : int | None
    +window_s : float
    +check(estimated_input_tokens, max_output_tokens)
    +record(usage)
    +spent_in_window() int
  }
  class PricingTable {
    +verified_on : date
    +source : str
    +models : dict~str, ModelPrice~
    +load(path) PricingTable$
    +price_for(model) ModelPrice | None
    +cost_usd(model, usage) float | None
  }
  class ModelPrice {
    +input_per_mtok : float
    +output_per_mtok : float
    +cache_read_per_mtok : float | None
    +cache_write_per_mtok : float | None
  }
  class CacheBackend {
    <<Protocol>>
    +get(key) Completion | None
    +put(key, completion)
    +find_similar(namespace, vector, min_similarity) tuple~Completion, float~ | None
    +put_vector(namespace, vector, key)
  }
  class InMemoryCache {
    +get(key) Completion | None
    +put(key, completion)
    +find_similar(namespace, vector, min_similarity) tuple~Completion, float~ | None
    +put_vector(namespace, vector, key)
  }
  class SemanticCacheConfig {
    +embedding_model : ModelRef
    +min_similarity : float
  }
  LLMClient --> TokenBudget : 2. budget.check() on an estimate, optional
  LLMClient --> CacheBackend : 3. exact key, then semantic, optional
  LLMClient --> SemanticCacheConfig : which embedding model, which threshold
  LLMClient --> CircuitBreaker : 4. one per backend, breaker_for()
  LLMClient --> RetryPolicy : 5. retry_call() with backoff and jitter
  LLMClient --> PricingTable : 7. cost_usd() from the real usage
  RetryReport *-- Attempt : attempts, one per try
  CircuitBreaker --> CircuitState : state
  PricingTable *-- ModelPrice : models, one per model id
  InMemoryCache ..|> CacheBackend : satisfies
  note for LLMClient "1. governance  2. budget  3. cache  4. breaker  5. retry  6. provider with timeout  7. budget.record and cost  8. trace"
```

## How to read it

- The numbers on the arrows are the order inside `complete`. Governance (1) is drawn in
  [03 governance](03-governance.md); the provider call (6) in
  [02 the client and its providers](02-client-and-providers.md).
- Retry, breaker and timeout answer three different questions. Retry: is it worth trying
  again now? Breaker: has this backend failed so often that we stop calling it for a while?
  Timeout: how long is "not answering" an outage? `RetryReport` is what the trace shows as
  `attempts`.
- The budget refuses twice. `check` before the call, on an estimate of 4 characters per token;
  `record` after it, with the real usage, which feeds the sliding window.
- The cache has two keys. An exact key over the fields that change the answer, and a semantic
  namespace plus a vector of the user message, compared with a deliberately high similarity
  threshold: a false positive serves the answer to another question.
- Prices are a dated file too, like governance facts. `cost_usd` returns `None` for an
  unknown model rather than a wrong number.
- Streaming goes through the breaker and the budget but not through the cache or the retry:
  replaying a started stream would duplicate text already sent.

## In the code

[llm/resilience.py](../../src/llm_testbench/llm/resilience.py),
[llm/budget.py](../../src/llm_testbench/llm/budget.py),
[llm/cache.py](../../src/llm_testbench/llm/cache.py),
[llm/cost.py](../../src/llm_testbench/llm/cost.py), prices in
[config/llm_pricing.toml](../../config/llm_pricing.toml).

## In the notebooks

Notebook 01, parts 3.3, 3.4 and 4.2 to 4.6.
